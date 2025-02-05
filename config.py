import os

# Токен бота
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Настройки базы данных
DB_FILE = 'tasks.db'

# Настройки для повторных попыток подключения
MAX_RETRIES = 5
RETRY_DELAY = 5  # секунд

# Настройки для проверки напоминаний
REMINDER_CHECK_INTERVAL = 300  # 5 минут
REMINDER_AHEAD_TIME = 3600    # 1 час

# Настройки для polling
POLLING_TIMEOUT = 60
LONG_POLLING_TIMEOUT = 60