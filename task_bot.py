import telebot
import logging
import os
import sys
from telebot import types
import datetime
import sqlite3
import threading
import time
import schedule

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Создание базы данных
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, 
                  task_text TEXT,
                  category TEXT,
                  deadline TEXT,
                  priority INTEGER,
                  status TEXT DEFAULT 'active',
                  reminder_time TEXT)''')
    conn.commit()
    conn.close()

# Словарь для хранения состояния пользователя
user_states = {}

# Клавиатура главного меню
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("📝 Добавить задачу")
    item2 = types.KeyboardButton("📋 Мои задачи")
    item3 = types.KeyboardButton("✅ Завершенные задачи")
    item4 = types.KeyboardButton("📊 Категории")
    item5 = types.KeyboardButton("⚡ Приоритеты")
    markup.add(item1, item2)
    markup.add(item3, item4)
    markup.add(item5)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
                 "Привет! Я бот-органайзер задач. Помогу тебе управлять твоими делами.",
                 reply_markup=get_main_keyboard())

# Добавление новой задачи
@bot.message_handler(func=lambda message: message.text == "📝 Добавить задачу")
def add_task(message):
    msg = bot.send_message(message.chat.id, "Введите текст задачи:")
    user_states[message.from_user.id] = {'state': 'waiting_task_text'}
    bot.register_next_step_handler(msg, process_task_text)

def process_task_text(message):
    user_id = message.from_user.id
    user_states[user_id] = {
        'state': 'waiting_category',
        'task_text': message.text
    }
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    categories = ["Работа", "Личное", "Покупки", "Учёба", "Другое"]
    for category in categories:
        markup.add(types.KeyboardButton(category))
    
    msg = bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_category)

def process_category(message):
    user_id = message.from_user.id
    user_states[user_id]['category'] = message.text
    user_states[user_id]['state'] = 'waiting_priority'
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    priorities = ["1 - Высокий", "2 - Средний", "3 - Низкий"]
    for priority in priorities:
        markup.add(types.KeyboardButton(priority))
    
    msg = bot.send_message(message.chat.id, "Выберите приоритет:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_priority)

def process_priority(message):
    user_id = message.from_user.id
    priority = int(message.text[0])
    user_states[user_id]['priority'] = priority
    user_states[user_id]['state'] = 'waiting_deadline'
    
    msg = bot.send_message(message.chat.id, 
                          "Введите дедлайн в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
                          "Например: 31.12.2024 15:00")
    bot.register_next_step_handler(msg, process_deadline)

def process_deadline(message):
    user_id = message.from_user.id
    try:
        deadline = datetime.datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        user_states[user_id]['deadline'] = deadline.strftime("%Y-%m-%d %H:%M:00")
        
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("""INSERT INTO tasks 
                    (user_id, task_text, category, deadline, priority, status) 
                    VALUES (?, ?, ?, ?, ?, ?)""",
                 (user_id,
                  user_states[user_id]['task_text'],
                  user_states[user_id]['category'],
                  user_states[user_id]['deadline'],
                  user_states[user_id]['priority'],
                  'active'))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, 
                        "Задача успешно добавлена!",
                        reply_markup=get_main_keyboard())
        
    except ValueError:
        msg = bot.send_message(message.chat.id, 
                             "Неверный формат даты. Попробуйте еще раз (ДД.ММ.ГГГГ ЧЧ:ММ):")
        bot.register_next_step_handler(msg, process_deadline)

# Просмотр активных задач
@bot.message_handler(func=lambda message: message.text == "📋 Мои задачи")
def show_tasks(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("""SELECT id, task_text, category, deadline, priority 
                 FROM tasks 
                 WHERE user_id=? AND status='active'
                 ORDER BY priority, deadline""", (user_id,))
    tasks = c.fetchall()
    conn.close()
    
    if tasks:
        markup = types.InlineKeyboardMarkup()
        response = "Ваши активные задачи:\n\n"
        for task in tasks:
            task_id, text, category, deadline, priority = task
            deadline_dt = datetime.datetime.strptime(deadline, "%Y-%m-%d %H:%M:00")
            response += f"🔸 {text}\n"
            response += f"Категория: {category}\n"
            response += f"Приоритет: {'❗' * (4 - priority)}\n"
            response += f"Дедлайн: {deadline_dt.strftime('%d.%m.%Y %H:%M')}\n"
            
            complete_btn = types.InlineKeyboardButton(
                "✅ Выполнено", 
                callback_data=f"complete_{task_id}"
            )
            edit_btn = types.InlineKeyboardButton(
                "✏️ Изменить", 
                callback_data=f"edit_{task_id}"
            )
            delete_btn = types.InlineKeyboardButton(
                "❌ Удалить", 
                callback_data=f"delete_{task_id}"
            )
            markup.add(complete_btn, edit_btn, delete_btn)
            response += "\n"
    else:
        response = "У вас пока нет активных задач."
        markup = None
    
    bot.send_message(message.chat.id, response, reply_markup=markup)

# Просмотр завершенных задач
@bot.message_handler(func=lambda message: message.text == "✅ Завершенные задачи")
def show_completed_tasks(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("""SELECT task_text, category, deadline 
                 FROM tasks 
                 WHERE user_id=? AND status='completed'
                 ORDER BY deadline DESC""", (user_id,))
    tasks = c.fetchall()
    conn.close()
    
    if tasks:
        response = "Ваши завершенные задачи:\n\n"
        for task in tasks:
            text, category, deadline = task
            deadline_dt = datetime.datetime.strptime(deadline, "%Y-%m-%d %H:%M:00")
            response += f"✅ {text}\n"
            response += f"Категория: {category}\n"
            response += f"Выполнено: {deadline_dt.strftime('%d.%m.%Y %H:%M')}\n\n"
    else:
        response = "У вас пока нет завершенных задач."
    
    bot.send_message(message.chat.id, response)

# Обработка нажатий на инлайн-кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    action, task_id = call.data.split('_')
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    if action == "complete":
        c.execute("UPDATE tasks SET status='completed' WHERE id=?", (task_id,))
        bot.answer_callback_query(call.id, "Задача отмечена как выполненная!")
        
    elif action == "delete":
        c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        bot.answer_callback_query(call.id, "Задача удалена!")
        
    elif action == "edit":
        user_states[call.from_user.id] = {
            'state': 'editing',
            'task_id': task_id
        }
        msg = bot.send_message(call.message.chat.id, 
                             "Введите новый текст задачи:")
        bot.register_next_step_handler(msg, process_edit_task)
    
    conn.commit()
    conn.close()
    
    # Обновляем сообщение со списком задач
    show_tasks(call.message)

def process_edit_task(message):
    user_id = message.from_user.id
    task_id = user_states[user_id]['task_id']
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("UPDATE tasks SET task_text=? WHERE id=?", 
             (message.text, task_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, 
                    "Задача обновлена!",
                    reply_markup=get_main_keyboard())

# Функция для проверки и отправки напоминаний
def check_reminders():
    while True:
        try:
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            now = datetime.datetime.now()
            
            # Получаем задачи, дедлайн которых наступает через час
            c.execute("""SELECT user_id, task_text, deadline 
                        FROM tasks 
                        WHERE status='active' 
                        AND deadline BETWEEN ? AND ?""",
                     (now.strftime("%Y-%m-%d %H:%M:00"),
                      (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:00")))
            
            tasks = c.fetchall()
            for task in tasks:
                user_id, task_text, deadline = task
                bot.send_message(
                    user_id,
                    f"⚠️ Напоминание!\nЧерез час дедлайн задачи:\n{task_text}\n"
                    f"Дедлайн: {deadline}"
                )
            
            conn.close()
            time.sleep(300)  # Проверяем каждые 5 минут
        except Exception as e:
            logger.error(f"Error in check_reminders: {e}")
            time.sleep(60)  # При ошибке ждем минуту перед повторной попыткой

# Добавьте эту функцию для безопасного выхода
def safe_exit(signum, frame):
    logger.info("Received signal for shutdown...")
    bot.stop_polling()
    sys.exit(0)

if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        init_db()
        
        # Запускаем проверку напоминаний в отдельном потоке
        reminder_thread = threading.Thread(target=check_reminders)
        reminder_thread.daemon = True
        reminder_thread.start()
        
        logger.info("Bot is running...")
        # Изменяем параметры polling
        bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        sys.exit(1)