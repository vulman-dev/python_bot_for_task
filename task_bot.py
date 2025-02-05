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
        """Отмечает задачу как выполненной"""
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

    def delete_task(self, task_id, user_id):
        """Удаляет задачу"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""DELETE FROM tasks 
                        WHERE id = ? AND user_id = ?""",
                     (task_id, user_id))
            conn.commit()
            return c.rowcount > 0

    def update_task(self, task_id, user_id, **kwargs):
        """Обновляет параметры задачи"""
        allowed_fields = {'task_text', 'category', 'deadline', 'priority', 'status', 'reminder_time'}
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            return False
            
        with self.get_connection() as conn:
            c = conn.cursor()
            query = """UPDATE tasks SET """ + \
                    ", ".join([f"{field} = ?" for field in update_fields.keys()]) + \
                    """ WHERE id = ? AND user_id = ?"""
            
            values = list(update_fields.values()) + [task_id, user_id]
            c.execute(query, values)
            conn.commit()
            return c.rowcount > 0

    def get_task_by_id(self, task_id, user_id):
        """Получает задачу по ID"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, task_text, category, deadline, priority, status, reminder_time
                        FROM tasks 
                        WHERE id = ? AND user_id = ?""",
                     (task_id, user_id))
            return c.fetchone()

    def get_tasks_by_category(self, user_id, category, status='active'):
        """Получает задачи определенной категории"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, task_text, category, deadline, priority 
                        FROM tasks 
                        WHERE user_id = ? AND category = ? AND status = ?
                        ORDER BY priority DESC, deadline ASC""",
                     (user_id, category, status))
            return c.fetchall()

    def get_tasks_by_priority(self, user_id, priority, status='active'):
        """Получает задачи определенного приоритета"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, task_text, category, deadline, priority 
                        FROM tasks 
                        WHERE user_id = ? AND priority = ? AND status = ?
                        ORDER BY deadline ASC""",
                     (user_id, priority, status))
            return c.fetchall()

    def get_overdue_tasks(self, user_id):
        """Получает просроченные задачи"""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:00")
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, task_text, category, deadline, priority 
                        FROM tasks 
                        WHERE user_id = ? AND status = 'active' AND deadline < ?
                        ORDER BY deadline ASC""",
                     (user_id, current_time))
            return c.fetchall()

    def get_tasks_count(self, user_id, status='active'):
        """Получает количество задач пользователя"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT COUNT(*) 
                        FROM tasks 
                        WHERE user_id = ? AND status = ?""",
                     (user_id, status))
            return c.fetchone()[0]

    def get_categories(self, user_id):
        """Получает список всех категорий пользователя"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT DISTINCT category 
                        FROM tasks 
                        WHERE user_id = ?""",
                     (user_id,))
            return [row[0] for row in c.fetchall()]