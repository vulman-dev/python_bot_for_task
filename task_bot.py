import telebot
import logging
import sys
from telebot import types
import datetime
import threading
import time
import schedule
import atexit
import signal
import os
import fcntl
from config import *
from database import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

class SingleInstanceBot:
    def __init__(self):
        self.lockfile = 'bot.lock'
        self.lock_fd = None
        
    def __enter__(self):
        try:
            self.lock_fd = open(self.lockfile, 'w')
            fcntl.lockf(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self
        except IOError:
            if self.lock_fd:
                self.lock_fd.close()
            logger.error("Another instance is already running")
            sys.exit(1)
            
    def __exit__(self, *args):
        if self.lock_fd:
            fcntl.lockf(self.lock_fd, fcntl.LOCK_UN)
            self.lock_fd.close()
            try:
                os.remove(self.lockfile)
            except OSError:
                pass

class TelegramBot:
    def __init__(self):
        self.bot = telebot.TeleBot(TOKEN, threaded=False) 
        self.db = Database(DB_FILE)
        self.user_states = {}
        self.setup_handlers()

    def get_main_keyboard(self):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = types.KeyboardButton("📝 Добавить задачу")
        item2 = types.KeyboardButton("📋 Мои задачи")
        item3 = types.KeyboardButton("✅ Завершенные задачи")
        markup.add(item1, item2)
        markup.add(item3)
        return markup

    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            self.bot.reply_to(message, 
                            "Привет! Я бот-органайзер задач. Помогу тебе управлять твоими делами.",
                            reply_markup=self.get_main_keyboard())

        @self.bot.message_handler(func=lambda message: message.text == "📝 Добавить задачу")
        def add_task(message):
            msg = self.bot.send_message(message.chat.id, "Введите текст задачи:")
            self.user_states[message.from_user.id] = {'state': 'waiting_task_text'}
            self.bot.register_next_step_handler(msg, self.process_task_text)

        @self.bot.message_handler(func=lambda message: message.text == "📋 Мои задачи")
        def show_tasks(message):
            tasks = self.db.get_tasks(message.from_user.id)
            if tasks:
                response = "Ваши активные задачи:\n\n"
                for task in tasks:
                    task_id, text, category, deadline, priority = task
                    response += f"🔹 {text}\n"
                    response += f"Категория: {category}\n"
                    response += f"Приоритет: {priority}\n"
                    response += f"Дедлайн: {deadline}\n\n"
            else:
                response = "У вас пока нет активных задач."
            
            self.bot.send_message(message.chat.id, response)

        @self.bot.message_handler(func=lambda message: message.text == "✅ Завершенные задачи")
        def show_completed_tasks(message):
            tasks = self.db.get_tasks(message.from_user.id, 'completed')
            if tasks:
                response = "Ваши завершенные задачи:\n\n"
                for task in tasks:
                    task_id, text, category, deadline, priority = task
                    response += f"✅ {text}\n"
                    response += f"Категория: {category}\n"
                    response += f"Выполнено: {deadline}\n\n"
            else:
                response = "У вас пока нет завершенных задач."
            
            self.bot.send_message(message.chat.id, response)

    def process_task_text(self, message):
        user_id = message.from_user.id
        self.user_states[user_id] = {
            'state': 'waiting_category',
            'task_text': message.text
        }
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        categories = ["Работа", "Личное", "Покупки", "Учёба", "Другое"]
        for category in categories:
            markup.add(types.KeyboardButton(category))
        
        msg = self.bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=markup)
        self.bot.register_next_step_handler(msg, self.process_category)

    def process_category(self, message):
        user_id = message.from_user.id
        self.user_states[user_id]['category'] = message.text
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        priorities = ["1 - Высокий", "2 - Средний", "3 - Низкий"]
        for priority in priorities:
            markup.add(types.KeyboardButton(priority))
        
        msg = self.bot.send_message(message.chat.id, "Выберите приоритет:", reply_markup=markup)
        self.bot.register_next_step_handler(msg, self.process_priority)

    def process_priority(self, message):
        user_id = message.from_user.id
        priority = int(message.text[0])
        self.user_states[user_id]['priority'] = priority
        
        msg = self.bot.send_message(message.chat.id, 
                                  "Введите дедлайн в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
                                  "Например: 31.12.2024 15:00")
        self.bot.register_next_step_handler(msg, self.process_deadline)

    def process_deadline(self, message):
        user_id = message.from_user.id
        try:
            deadline = datetime.datetime.strptime(message.text, "%d.%m.%Y %H:%M")
            state = self.user_states[user_id]
            
            self.db.add_task(
                user_id=user_id,
                task_text=state['task_text'],
                category=state['category'],
                deadline=deadline.strftime("%Y-%m-%d %H:%M:00"),
                priority=state['priority']
            )
            
            self.bot.send_message(message.chat.id, 
                                "Задача успешно добавлена!",
                                reply_markup=self.get_main_keyboard())
            
        except ValueError:
            msg = self.bot.send_message(message.chat.id, 
                                      "Неверный формат даты. Попробуйте еще раз.\n"
                                      "Формат: ДД.ММ.ГГГГ ЧЧ:ММ")
            self.bot.register_next_step_handler(msg, self.process_deadline)

    def check_reminders_loop(self):
        while True:
            try:
                now = datetime.datetime.now()
                ahead_time = now + datetime.timedelta(seconds=REMINDER_AHEAD_TIME)
                
                reminders = self.db.get_upcoming_reminders(
                    now.strftime("%Y-%m-%d %H:%M:00"),
                    ahead_time.strftime("%Y-%m-%d %H:%M:00")
                )
                
                for reminder in reminders:
                    user_id, task_text, deadline = reminder
                    self.bot.send_message(
                        user_id,
                        f"⚠️ Напоминание!\nЧерез час дедлайн задачи:\n{task_text}\n"
                        f"Дедлайн: {deadline}"
                    )
                
                time.sleep(REMINDER_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error in check_reminders: {e}")
                time.sleep(60)

    def run(self):
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                logger.info("Starting bot...")
                self.db.init_db()
                
                # Принудительно очищаем обновления
                self.bot.remove_webhook()
                self.bot.get_updates(offset=-1)

                # Запускаем проверку напоминаний
                reminder_thread = threading.Thread(target=self.check_reminders_loop)
                reminder_thread.daemon = True
                reminder_thread.start()
                
                logger.info("Bot is running...")
                self.bot.polling(none_stop=True, 
                               timeout=POLLING_TIMEOUT,
                               long_polling_timeout=LONG_POLLING_TIMEOUT,
                               allowed_updates=["message", "callback_query"])
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Error occurred: {e}")
                if retry_count < MAX_RETRIES:
                    logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error("Max retries reached. Shutting down.")
                    sys.exit(1)

def main():
    with SingleInstanceBot():
        bot = TelegramBot()
        
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            bot.bot.stop_polling()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        bot.run()

if __name__ == "__main__":
    main()