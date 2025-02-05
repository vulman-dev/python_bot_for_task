import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TOKEN = os.getenv('BOT_TOKEN')

# Database
DB_FILE = 'tasks.db'

# Reminder settings
REMINDER_AHEAD_TIME = 3600  # 1 hour in seconds
REMINDER_CHECK_INTERVAL = 60  # 1 minute in seconds

# Retry settings
MAX_RETRIES = 5
RETRY_DELAY = 5  # seconds