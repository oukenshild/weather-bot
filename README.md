# weather-bot

Telegram-бот на Python (без зависимостей), который:
- при первом запуске просит **город** и сохраняет его в SQLite;
- затем показывает **сохранённые города кнопками** + кнопку **«Мой город»**;
- отдаёт прогноз через **OpenWeatherMap**.

## Настройка

Создайте `.env` рядом с `main.py`:

```env
TELEGRAM_TOKEN=...
OPENWEATHER_API_KEY=...
# DB_PATH=cities.db
```

## Локальный запуск

```bash
python main.py
```

## Развертывание на Beget

Для развертывания на сервере Beget смотрите:

- **[QUICK_START.md](QUICK_START.md)** — быстрая инструкция (5 минут)
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — подробная пошаговая инструкция
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** — чеклист для проверки

### Быстрый старт

1. Получите токены (Telegram Bot Token, OpenWeatherMap API Key)
2. Загрузите файлы на сервер через SFTP
3. Создайте `.env` с токенами
4. Настройте systemd сервис
5. Запустите бота

Подробности в `QUICK_START.md`.

## Команды бота

- `/start` — показать меню (или попросить город при первом запуске)
- `/weather` — показать меню городов
- `/help` — справка

## Структура проекта

```
weather-bot/
├── main.py                    # Основной файл бота
├── config.py                  # Конфигурация
├── start.sh                   # Скрипт запуска
├── weather-bot.service        # Systemd сервис
├── .env                       # Переменные окружения (не в Git)
├── cities.db                  # База данных (создается автоматически)
└── logs/                      # Логи (создается автоматически)
```

## Требования

- Python 3.7+
- Telegram Bot Token
- OpenWeatherMap API Key
- Доступ к серверу с Python (для развертывания)
