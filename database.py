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
        """Инициализация базы данных"""
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
                         reminder_sent INTEGER DEFAULT 0)''')
            
            # Проверяем, существует ли колонка reminder_sent
            c.execute("PRAGMA table_info(tasks)")
            columns = [column[1] for column in c.fetchall()]
            
            # Если колонки нет, добавляем её
            if 'reminder_sent' not in columns:
                c.execute('''ALTER TABLE tasks 
                           ADD COLUMN reminder_sent INTEGER DEFAULT 0''')
            
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
        
    def update_task(self, task_id, user_id, **kwargs):
        """Обновляет задачу"""
        allowed_fields = {'task_text', 'category', 'deadline', 'priority'}
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
        
    def get_statistics(self, user_id):
        """Получает статистику по задачам пользователя"""
        with self.get_connection() as conn:
            c = conn.cursor()
            stats = {}

            # Общее количество задач
            c.execute("""SELECT COUNT(*) FROM tasks WHERE user_id = ?""", (user_id,))
            stats['total'] = c.fetchone()[0]
            
            # Активные задачи
            c.execute("""SELECT COUNT(*) FROM tasks 
                        WHERE user_id = ? AND status = 'active'""", (user_id,))
            stats['active'] = c.fetchone()[0]
            
            # Выполненные задачи
            c.execute("""SELECT COUNT(*) FROM tasks 
                        WHERE user_id = ? AND status = 'completed'""", (user_id,))
            stats['completed'] = c.fetchone()[0]
            
            # Статистика по категориям
            c.execute("""SELECT category, COUNT(*) 
                        FROM tasks 
                        WHERE user_id = ?
                        GROUP BY category""", (user_id,))
            stats['by_category'] = dict(c.fetchall())
            
            return stats
        
    def get_upcoming_deadlines(self, user_id, hours=24):
        """Получает задачи с приближающимися дедлайнами"""
        current_time = datetime.datetime.now()
        deadline_time = current_time + datetime.timedelta(hours=hours)

        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, task_text, category, deadline, priority 
                        FROM tasks 
                        WHERE user_id = ? 
                        AND status = 'active'
                        AND deadline BETWEEN ? AND ?
                        ORDER BY deadline ASC""",
                     (user_id, 
                      current_time.strftime("%Y-%m-%d %H:%M:00"),
                      deadline_time.strftime("%Y-%m-%d %H:%M:00")))
            return c.fetchall()
        
    def delete_task(self, task_id, user_id):
        """"Удаляет задачу"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", 
                     (task_id, user_id))
            conn.commit()
            return c.rowcount > 0
        
    def set_reminder(self, task_id, user_id, reminder_time):
        """"Устанавливает напоминание для задачи"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""UPDATE tasks 
                        SET reminder_time = ? 
                        WHERE id = ? AND user_id = ?""",
                     (reminder_time, task_id, user_id))
            conn.commit()
            return c.rowcount > 0
        
    def get_task_by_id(self, task_id, user_id):
        """"Получает задау по ID"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT id, task_text, category, deadline, priority 
                        FROM tasks 
                        WHERE id = ? AND user_id = ?""",
                     (task_id, user_id))
            return c.fetchone()
        
    def get_tasks_for_reminder(self):
        """Получает задачи для напоминания"""
        current_time = datetime.datetime.now()
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, user_id, task_text, deadline 
                FROM tasks 
                WHERE status = 'active' 
                AND deadline > ? 
                AND deadline <= ?
                AND (reminder_sent IS NULL OR reminder_sent = 0)
            """, (
                current_time.strftime("%Y-%m-%d %H:%M:00"),
                (current_time + datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:00")
            ))
            return c.fetchall()

    def mark_reminder_sent(self, task_id):
        """Отмечает, что напоминание было отправлено"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE tasks SET reminder_sent = 1 WHERE id = ?", (task_id,))
            conn.commit()