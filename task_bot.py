import telebot
import logging
import sys
from telebot import types
import datetime
import time
import os
import threading
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

class TelegramBot:
    def __init__(self):
        self.bot = telebot.TeleBot(TOKEN)
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
            self.bot.send_message(
                message.chat.id,
                "Привет! Я бот-органайзер задач.",
                reply_markup=self.get_main_keyboard()
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
                for task in tasks:
                    task_id, text, category, deadline, priority = task
                    response = "<b>📋 Задача:</b>\n\n"
                    response += f"<b>🔹 Текст:</b> {text}\n"
                    response += f"<b>📁 Категория:</b> {category}\n"
                    response += f"<b>⚡️ Приоритет:</b> {priority}\n"
                    response += f"<b>⏰ Дедлайн:</b> {deadline}\n"
                    
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    buttons = [
                        types.InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task_id}"),
                        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{task_id}")
                    ]
                    markup.add(*buttons)
                    
                    self.bot.send_message(
                        message.chat.id,
                        response,
                        parse_mode='HTML',
                        reply_markup=markup
                    )
            else:
                self.bot.send_message(
                    message.chat.id,
                    "У вас пока нет активных задач."
                )

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('complete_'))
        def complete_task_callback(call):
            task_id = int(call.data.split('_')[1])
            if self.db.complete_task(task_id, call.from_user.id):
                self.bot.answer_callback_query(call.id, "✅ Задача выполнена!")
                self.bot.delete_message(call.message.chat.id, call.message.message_id)
            else:
                self.bot.answer_callback_query(call.id, "❌ Ошибка при выполнении задачи")
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
        def edit_task_callback(call):
            data_parts = call.data.split('_')

            if len(data_parts) == 3:
                action = data_parts[1]
                task_id = int(data_parts[2])
                
                if action == 'text':
                    self.user_states[call.from_user.id] = {
                        'state': 'waiting_edit_text',
                        'task_id': task_id
                    }
                    msg = self.bot.send_message(call.message.chat.id, "Введите новый текст задачи:")
                    self.bot.register_next_step_handler(msg, self.process_edit_text)
                            
                elif action == 'deadline':
                    self.user_states[call.from_user.id] = {
                        'state': 'waiting_edit_deadline',
                        'task_id': task_id
                    }
                    msg = self.bot.send_message(
                        call.message.chat.id,
                        "Введите новый дедлайн в формате ДД.ММ.ГГГГ ЧЧ:ММ:"
                    )
                    self.bot.register_next_step_handler(msg, self.process_edit_deadline)

                elif action == 'priority':
                    self.user_states[call.from_user.id] = {
                        'state': 'waiting_edit_priority',
                        'task_id': task_id
                    }
                    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                    priorities = ["1 - Высокий", "2 - Средний", "3 - Низкий"]
                    for priority in priorities:
                        markup.add(types.KeyboardButton(priority))
                    msg = self.bot.send_message(
                        call.message.chat.id,
                        "Выберите новый приоритет:",
                        reply_markup=markup
                    )
                    self.bot.register_next_step_handler(msg, self.process_edit_priority)
                return
            # Если это просто edit_ID
            task_id = int(data_parts[1])
            markup = types.InlineKeyboardMarkup(row_width=1)
            buttons = [
                types.InlineKeyboardButton("📝 Изменить текст", callback_data=f"edit_text_{task_id}"),
                types.InlineKeyboardButton("📅 Изменить дедлайн", callback_data=f"edit_deadline_{task_id}"),
                types.InlineKeyboardButton("📊 Изменить приоритет", callback_data=f"edit_priority_{task_id}"),
                types.InlineKeyboardButton("🗑 Удалить задачу", callback_data=f"delete_{task_id}")
            ]
            markup.add(*buttons)
            
            self.bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('edit_text_'))
        def edit_text_callback(call):
            task_id = int(call.data.split('_')[2])
            self.user_states[call.from_user.id] = {
                'state': 'waiting_edit_text',
                'task_id': task_id
            }
            msg = self.bot.send_message(call.message.chat.id, "Введите новый текст задачи:")
            self.bot.register_next_step_handler(msg, self.process_edit_text)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
        def delete_task_callback(call):
            task_id = int(call.data.split('_')[1])
            if self.db.delete_task(task_id, call.from_user.id):
                self.bot.answer_callback_query(call.id, "✅ Задача удалена!")
                self.bot.delete_message(call.message.chat.id, call.message.message_id)
            else:
                self.bot.answer_callback_query(call.id, "❌ Ошибка при удалении задачи")

        @self.bot.message_handler(func=lambda message: message.text == "✅ Завершенные задачи")
        def show_completed_tasks(message):
            tasks = self.db.get_tasks(message.from_user.id, status='completed')
            if tasks:
                response = "<b>✅ Завершенные задачи:</b>\n\n"
                for task in tasks:
                    task_id, text, category, deadline, priority = task
                    response += f"<b>🔹 Задача:</b> {text}\n"
                    response += f"<b>📁 Категория:</b> {category}\n"
                    response += f"<b>⚡️ Приоритет:</b> {priority}\n"
                    response += f"<b>⏰ Выполнено:</b> {deadline}\n"
                    response += "─────────────────\n"
                
                self.bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='HTML'
                )
            else:
                self.bot.send_message(
                    message.chat.id,
                    "У вас пока нет завершенных задач."
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
        
        msg = self.bot.send_message(
            message.chat.id,
            "Выберите категорию:",
            reply_markup=markup
        )
        self.bot.register_next_step_handler(msg, self.process_category)

    def process_category(self, message):
        user_id = message.from_user.id
        self.user_states[user_id]['category'] = message.text
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        priorities = ["1 - Высокий", "2 - Средний", "3 - Низкий"]
        for priority in priorities:
            markup.add(types.KeyboardButton(priority))
        
        msg = self.bot.send_message(
            message.chat.id,
            "Выберите приоритет:",
            reply_markup=markup
        )
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
        try:
            deadline = datetime.datetime.strptime(message.text, "%d.%m.%Y %H:%M")
            user_id = message.from_user.id
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
                "✅ Задача успешно добавлена!",
                reply_markup=self.get_main_keyboard()
            )
            
        except ValueError:
            msg = self.bot.send_message(
                message.chat.id,
                "❌ Неверный формат даты. Попробуйте еще раз.\nФормат: ДД.ММ.ГГГГ ЧЧ:ММ"
            )
            self.bot.register_next_step_handler(msg, self.process_deadline)

    def check_reminders(self):
        """Проверяет и отправляет напоминания о задачах"""
        while True:
            try:
                tasks = self.db.get_tasks_for_reminder()
                for task in tasks:
                    task_id, user_id, text, deadline = task
                    deadline_dt = datetime.datetime.strptime(deadline, "%Y-%m-%d %H:%M:00")
                    time_left = deadline_dt - datetime.datetime.now()
                    minutes_left = time_left.total_seconds() / 60

                    message = f"⚠️ <b>Напоминание о задаче!</b>\n\n"
                    message += f"<b>Задача:</b> {text}\n"
                    message += f"<b>Дедлайн:</b> {deadline}\n"
                    message += f"<b>Осталось времени:</b> {int(minutes_left)} мин."

                    try:
                        self.bot.send_message(user_id, message, parse_mode='HTML')
                        self.db.mark_reminder_sent(task_id)
                    except Exception as e:
                        logger.error(f"Error sending reminder: {e}")

                time.sleep(30)  # Проверяем каждые 5 минут
            except Exception as e:
                logger.error(f"Error in reminder check: {e}")
                time.sleep(60)
    
    def run(self):
        logger.info("Starting bot...")
        self.db.init_db()
        reminder_thread = threading.Thread(target=self.check_reminders)
        reminder_thread.daemon = True
        reminder_thread.start()

        logger.info("Bot is running...")
        self.bot.infinity_polling()

    def process_edit_text(self, message):
        user_id = message.from_user.id
        task_id = self.user_states[user_id]['task_id']
        
        if self.db.update_task(task_id, user_id, task_text=message.text):
            self.bot.send_message(
                message.chat.id,
                "✅ Текст задачи обновлен!",
                reply_markup=self.get_main_keyboard()
            )
        else:
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при обновлении задачи",
                reply_markup=self.get_main_keyboard()
            )

    def process_edit_deadline(self, message):
        try:
            deadline = datetime.datetime.strptime(message.text, "%d.%m.%Y %H:%M")
            user_id = message.from_user.id
            task_id = self.user_states[user_id]['task_id']
            
            if self.db.update_task(task_id, user_id, deadline=deadline.strftime("%Y-%m-%d %H:%M:00")):
                self.bot.send_message(
                    message.chat.id,
                    "✅ Дедлайн обновлен!",
                    reply_markup=self.get_main_keyboard()
                )
            else:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Ошибка при обновлении дедлайна",
                    reply_markup=self.get_main_keyboard()
                )
        except ValueError:
            msg = self.bot.send_message(
                message.chat.id,
                "❌ Неверный формат даты. Попробуйте еще раз (ДД.ММ.ГГГГ ЧЧ:ММ):"
            )
            self.bot.register_next_step_handler(msg, self.process_edit_deadline)

    def process_edit_priority(self, message):
        try:
            priority = int(message.text[0])
            user_id = message.from_user.id
            task_id = self.user_states[user_id]['task_id']
            
            if self.db.update_task(task_id, user_id, priority=priority):
                self.bot.send_message(
                    message.chat.id,
                    "✅ Приоритет обновлен!",
                    reply_markup=self.get_main_keyboard()
                )
            else:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Ошибка при обновлении приоритета",
                    reply_markup=self.get_main_keyboard()
                )
        except (ValueError, IndexError):
            msg = self.bot.send_message(
                message.chat.id,
                "❌ Неверный формат. Выберите приоритет из списка:"
            )
            self.bot.register_next_step_handler(msg, self.process_edit_priority)

        def check_reminders(self):
            """Проверяет и отправляет напоминания о задачах"""
            while True:
                try:
                    tasks = self.db.get_tasks_for_reminder()
                    for task in tasks:
                        task_id, user_id, text, deadline = task
                        deadline_dt = datetime.datetime.strptime(deadline, "%Y-%m-%d %H:%M:00")
                        time_left = deadline_dt - datetime.datetime.now()
                        hours_left = time_left.total_seconds() / 3600

                        message = f"⚠️ <b>Напоминание о задаче!</b>\n\n"
                        message += f"<b>Задача:</b> {text}\n"
                        message += f"<b>Дедлайн:</b> {deadline}\n"
                        message += f"<b>Осталось времени:</b> {int(hours_left)} ч."

                        try:
                            self.bot.send_message(user_id, message, parse_mode='HTML')
                            self.db.mark_reminder_sent(task_id)
                        except Exception as e:
                            logger.error(f"Error sending reminder: {e}")

                    time.sleep(300)  # Проверяем каждые 5 минут
                except Exception as e:
                    logger.error(f"Error in reminder check: {e}")
                    time.sleep(60)
    
def main():
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    main()