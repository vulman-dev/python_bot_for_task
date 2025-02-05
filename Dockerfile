FROM python:3.9-slim

# Создаем нового пользователя
RUN useradd -m botuser

# Устанавливаем необходимые пакеты
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создаем и настраиваем рабочую директорию
WORKDIR /app
COPY . .

# Создаем и активируем виртуальное окружение
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для логов и БД
RUN mkdir -p /app/data
RUN chown -R botuser:botuser /app

# Переключаемся на пользователя botuser
USER botuser

# Добавляем healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('https://api.telegram.org/bot${TELEGRAM_TOKEN}/getMe')"

# Добавляем STOPSIGNAL
STOPSIGNAL SIGTERM

# Запускаем бота
CMD ["python", "task_bot.py"]