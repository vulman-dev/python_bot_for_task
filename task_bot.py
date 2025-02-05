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
        # Добавьте все ваши обработчики здесь
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            self.bot.reply_to(message, 
                            "Привет! Я бот-органайзер задач.",
                            reply_markup=self.get_main_keyboard())

        # ... [все остальные обработчики из предыдущего кода] ...

    def run(self):
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                logger.info("Starting bot...")
                self.db.init_db()
                
                # Запускаем проверку напоминаний
                reminder_thread = threading.Thread(target=self.check_reminders)
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