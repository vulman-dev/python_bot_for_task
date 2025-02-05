import sqlite3
import logging
import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_file):
        self.db_file = db_file

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            yield conn
        except Exception as e:
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def init_db(self):
        with self.get_connection() as conn:
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

    def add_task(self, user_id, task_text, category, deadline, priority):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO tasks 
                        (user_id, task_text, category, deadline, priority, status) 
                        VALUES (?, ?, ?, ?, ?, 'active')""",
                     (user_id, task_text, category, deadline, priority))
            conn.commit()

    def get_tasks(self, user_id, status='active'):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, task_text, category, deadline, priority 
                        FROM tasks 
                        WHERE user_id=? AND status=?
                        ORDER BY priority DESC, deadline ASC""",
                     (user_id, status))
            return c.fetchall()

    def get_upcoming_reminders(self, current_time, ahead_time):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT user_id, task_text, deadline 
                        FROM tasks 
                        WHERE status='active' 
                        AND deadline BETWEEN ? AND ?""",
                     (current_time, ahead_time))
            return c.fetchall()

    def complete_task(self, task_id, user_id):
        """Отмечает задачу как выполненную"""
        with self.get_connection() as conn:
            c = conn.cursor()
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:00")
            c.execute("""UPDATE tasks 
                        SET status = 'completed', 
                            deadline = ? 
                        WHERE id = ? AND user_id = ? AND status = 'active'""",
                     (current_time, task_id, user_id))
            conn.commit()
            return c.rowcount > 0