FROM python:3.9-slim

# Создаем нового пользователя
RUN useradd -m botuser

# Устанавливаем необходимые пакеты
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Создаем и настраиваем рабочую директорию
WORKDIR /app
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для логов и БД
RUN mkdir -p /app/data
RUN chown -R botuser:botuser /app

# Переключаемся на пользователя botuser
USER botuser

# Запускаем бота
CMD ["python", "task_bot.py"]