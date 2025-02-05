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
        self.bot = telebot.TeleBot(TOKEN)
        self.db = Database(DB_FILE)
        self.user_states = {}
        self.setup_handlers()
        
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            self.bot.reply_to(message, 
                            "Привет! Я бот-органайзер задач.",
                            reply_markup=self.get_main_keyboard())

        @self.bot.message_handler(func=lambda message: message.text == "📝 Добавить задачу")
        def add_task(message):
            msg = self.bot.send_message(message.chat.id, "Введите текст задачи:")
            self.user_states[message.from_user.id] = {'state': 'waiting_task_text'}
            self.bot.register_next_step_handler(msg, self.process_task_text)

    def get_main_keyboard(self):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = types.KeyboardButton("📝 Добавить задачу")
        item2 = types.KeyboardButton("📋 Мои задачи")
        markup.add(item1, item2)
        return markup

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
                
                # Запускаем проверку напоминаний
                reminder_thread = threading.Thread(target=self.check_reminders_loop)
                reminder_thread.daemon = True
                reminder_thread.start()
                
                logger.info("Bot is running...")
                self.bot.polling(none_stop=True, 
                               timeout=POLLING_TIMEOUT,
                               long_polling_timeout=LONG_POLLING_TIMEOUT)
                
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