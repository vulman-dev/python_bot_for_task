import telebot
import logging
import sys
from telebot import types
import datetime
import time
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

# ... (предыдущий код с импортами и настройкой логирования)

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
        self.bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
        self.db = Database(DB_FILE)
        self.user_states = {}
        self.setup_handlers()

    def get_main_keyboard(self):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = [
            types.KeyboardButton("📝 Добавить задачу"),
            types.KeyboardButton("📋 Мои задачи"),
            types.KeyboardButton("✅ Завершенные задачи")
        ]
        markup.add(*buttons)
        return markup

    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            keyboard = self.get_main_keyboard()
            self.bot.send_message(
                message.chat.id,
                "Привет! Я бот-органайзер задач. Помогу тебе управлять твоими делами.",
                reply_markup=keyboard
            )

        @self.bot.message_handler(func=lambda message: message.text == "📝 Добавить задачу")
        def add_task(message):
            msg = self.bot.send_message(message.chat.id, "Введите текст задачи:")
            self.user_states[message.from_user.id] = {'state': 'waiting_task_text'}
            self.bot.register_next_step_handler(msg, self.process_task_text)

        @self.bot.message_handler(func=lambda message: message.text == "📋 Мои задачи")
        def show_tasks(message):
            tasks = self.db.get_tasks(message.from_user.id)
            if tasks:
                response = "<b>📋 Ваши активные задачи:</b>\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for task in tasks:
                    task_id, text, category, deadline, priority = task
                    response += f"<b>🔹 Задача:</b> {text}\n"
                    response += f"<b>📁 Категория:</b> {category}\n"
                    response += f"<b>⚡️ Приоритет:</b> {priority}\n"
                    response += f"<b>⏰ Дедлайн:</b> {deadline}\n"
                    response += "─────────────────\n"
                    
                    markup.add(types.InlineKeyboardButton(
                        f"✅ Отметить выполненной: {text[:30]}...",
                        callback_data=f"complete_{task_id}"
                    ))
            else:
                response = "У вас пока нет активных задач."
                markup = None
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='HTML',
                reply_markup=markup
            )

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('complete_'))
        def complete_task_callback(call):
            task_id = int(call.data.split('_')[1])
            if self.db.complete_task(task_id, call.from_user.id):
                self.bot.answer_callback_query(
                    call.id,
                    "✅ Задача отмечена как выполненная!"
                )
                self.bot.delete_message(call.message.chat.id, call.message.message_id)
                show_tasks(call.message)
            else:
                self.bot.answer_callback_query(
                    call.id,
                    "❌ Ошибка при выполнении задачи"
                )

        @self.bot.message_handler(func=lambda message: message.text == "✅ Завершенные задачи")
        def show_completed_tasks(message):
            tasks = self.db.get_tasks(message.from_user.id, 'completed')
            if tasks:
                response = "<b>✅ Завершенные задачи:</b>\n\n"
                for task in tasks:
                    task_id, text, category, deadline, priority = task
                    response += f"<b>✓ Задача:</b> {text}\n"
                    response += f"<b>📁 Категория:</b> {category}\n"
                    response += f"<b>📅 Выполнено:</b> {deadline}\n"
                    response += "─────────────────\n"
            else:
                response = "У вас пока нет завершенных задач."
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='HTML',
                reply_markup=self.get_main_keyboard()
            )

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
        
        msg = self.bot.send_message(
            message.chat.id,
            "Введите дедлайн в формате ДД.ММ.ГГГГ ЧЧ:ММ\nНапример: 31.12.2024 15:00"
        )
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
            
            self.bot.send_message(
                message.chat.id,
                "Задача успешно добавлена!",
                reply_markup=self.get_main_keyboard()
            )
            
        except ValueError:
            msg = self.bot.send_message(
                message.chat.id,
                "Неверный формат даты. Попробуйте еще раз.\nФормат: ДД.ММ.ГГГГ ЧЧ:ММ"
            )
            self.bot.register_next_step_handler(msg, self.process_deadline)

    def run(self):
        logger.info("Starting bot...")
        self.db.init_db()
        logger.info("Bot is running...")
        self.bot.infinity_polling(interval=3)

def main():
    with SingleInstanceBot():
        bot = TelegramBot()
        bot.run()

if __name__ == "__main__":
    main()