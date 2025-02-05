FROM python:3.9-slim

# Создаем нового пользователя
RUN useradd -m botuser

# Создаем и настраиваем рабочую директорию
WORKDIR /app
COPY . .

# Создаем и активируем виртуальное окружение
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Устанавливаем зависимости в виртуальное окружение
RUN pip install --no-cache-dir -r requirements.txt

# Меняем владельца файлов
RUN chown -R botuser:botuser /app

# Переключаемся на пользователя botuser
USER botuser

# Добавляем STOPSIGNAL
STOPSIGNAL SIGTERM

# Запускаем бота
CMD ["python", "task_bot.py"]