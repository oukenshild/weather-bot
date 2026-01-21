# Инструкция по развертыванию Telegram Weather Bot на Beget

## Подготовка проекта

### 1. Структура файлов для загрузки

Загрузите на сервер Beget следующие файлы:
```
weather-bot/
├── main.py              # Основной файл бота
├── config.py            # Файл конфигурации
├── .env                 # Файл с переменными окружения (создайте на сервере)
├── env.example          # Пример файла конфигурации
├── start.sh             # Скрипт запуска
├── weather-bot.service  # Файл systemd сервиса
└── cities.db            # База данных (создастся автоматически)
```

**НЕ загружайте:**
- `.env` (создайте на сервере)
- `cities.db` (создастся автоматически)
- `logs/` (создастся автоматически)

---

## Пошаговая инструкция развертывания

### Шаг 1: Получение токенов и ключей

1. **Telegram Bot Token:**
   - Откройте [@BotFather](https://t.me/BotFather) в Telegram
   - Отправьте команду `/newbot`
   - Следуйте инструкциям для создания бота
   - Скопируйте полученный токен (формат: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **OpenWeatherMap API Key:**
   - Зарегистрируйтесь на [OpenWeatherMap](https://openweathermap.org/api)
   - Перейдите в раздел API Keys
   - Создайте новый ключ или используйте существующий
   - Скопируйте API ключ

### Шаг 2: Подключение к серверу Beget

1. Войдите в панель управления Beget
2. Откройте **"SSH доступ"** или используйте SSH клиент (PuTTY, WinSCP, терминал)
3. Подключитесь к серверу:
   ```bash
   ssh YOUR_USERNAME@YOUR_DOMAIN.beget.app
   ```

### Шаг 3: Создание директории проекта

```bash
# Перейдите в домашнюю директорию
cd ~

# Создайте директорию для бота
mkdir weather-bot
cd weather-bot
```

### Шаг 4: Загрузка файлов на сервер

**Вариант A: Через SFTP (WinSCP, FileZilla)**
1. Подключитесь к серверу через SFTP
2. Перейдите в `/home/YOUR_USERNAME/weather-bot/`
3. Загрузите файлы: `main.py`, `config.py`, `start.sh`, `env.example`

**Вариант B: Через Git**
```bash
# Если у вас есть Git репозиторий
git clone YOUR_REPO_URL weather-bot
cd weather-bot
```

**Вариант C: Через wget/curl (если файлы на GitHub)**
```bash
# Скачайте файлы по отдельности
wget https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/main.py
wget https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/config.py
# и т.д.
```

### Шаг 5: Создание файла .env

```bash
# Создайте файл .env
nano .env
```

Добавьте следующие строки (замените значения на свои):
```env
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
OPENWEATHER_API_KEY=your_openweather_api_key_here
DB_PATH=cities.db
```

Сохраните файл: `Ctrl+O`, `Enter`, `Ctrl+X`

**Важно:** Убедитесь, что файл `.env` имеет правильные права доступа:
```bash
chmod 600 .env
```

### Шаг 6: Проверка версии Python

```bash
# Проверьте версию Python (нужна 3.7+)
python3 --version

# Если Python3 не найден, попробуйте:
python --version
```

### Шаг 7: Тестовый запуск

```bash
# Сделайте скрипт исполняемым
chmod +x start.sh

# Создайте директорию для логов
mkdir -p logs

# Запустите бота вручную для проверки
python3 main.py
```

Если всё работает, остановите бота: `Ctrl+C`

### Шаг 8: Настройка systemd сервиса

1. **Отредактируйте файл `weather-bot.service`:**
   ```bash
   nano weather-bot.service
   ```
   
   Замените `YOUR_BEGET_USERNAME` на ваш реальный username в двух местах:
   - `User=YOUR_BEGET_USERNAME`
   - `/home/YOUR_BEGET_USERNAME/weather-bot`

2. **Скопируйте файл сервиса в systemd:**
   ```bash
   # Создайте директорию для пользовательских сервисов (если нужно)
   mkdir -p ~/.config/systemd/user
   
   # Скопируйте файл сервиса
   cp weather-bot.service ~/.config/systemd/user/
   
   # Или используйте системную директорию (требует sudo)
   sudo cp weather-bot.service /etc/systemd/system/
   ```

3. **Перезагрузите systemd:**
   ```bash
   # Для пользовательского сервиса:
   systemctl --user daemon-reload
   
   # Для системного сервиса:
   sudo systemctl daemon-reload
   ```

### Шаг 9: Запуск сервиса

**Для пользовательского сервиса:**
```bash
# Включите автозапуск
systemctl --user enable weather-bot.service

# Запустите сервис
systemctl --user start weather-bot.service

# Проверьте статус
systemctl --user status weather-bot.service
```

**Для системного сервиса:**
```bash
# Включите автозапуск
sudo systemctl enable weather-bot.service

# Запустите сервис
sudo systemctl start weather-bot.service

# Проверьте статус
sudo systemctl status weather-bot.service
```

### Шаг 10: Проверка работы бота

1. **Проверьте логи:**
   ```bash
   # Логи работы
   tail -f logs/bot.log
   
   # Логи ошибок
   tail -f logs/bot_error.log
   ```

2. **Проверьте статус сервиса:**
   ```bash
   systemctl --user status weather-bot.service
   # или
   sudo systemctl status weather-bot.service
   ```

3. **Протестируйте бота в Telegram:**
   - Найдите вашего бота в Telegram
   - Отправьте команду `/start`
   - Проверьте, что бот отвечает

---

## Управление ботом

### Полезные команды

```bash
# Остановить бота
systemctl --user stop weather-bot.service
# или
sudo systemctl stop weather-bot.service

# Перезапустить бота
systemctl --user restart weather-bot.service
# или
sudo systemctl restart weather-bot.service

# Просмотр логов в реальном времени
tail -f logs/bot.log

# Просмотр последних 50 строк логов
tail -n 50 logs/bot.log

# Просмотр логов ошибок
tail -f logs/bot_error.log
```

---

## Решение проблем

### Бот не запускается

1. **Проверьте логи ошибок:**
   ```bash
   cat logs/bot_error.log
   ```

2. **Проверьте переменные окружения:**
   ```bash
   cat .env
   ```

3. **Проверьте права доступа:**
   ```bash
   ls -la
   chmod +x start.sh
   chmod 600 .env
   ```

4. **Проверьте путь к Python:**
   ```bash
   which python3
   # Если путь отличается, обновите ExecStart в weather-bot.service
   ```

### Бот не отвечает в Telegram

1. Проверьте, что токен правильный в файле `.env`
2. Проверьте логи: `tail -f logs/bot.log`
3. Убедитесь, что сервис запущен: `systemctl --user status weather-bot.service`

### Проблемы с базой данных

1. Проверьте права на запись в директории:
   ```bash
   ls -la cities.db
   chmod 664 cities.db
   ```

2. Если база повреждена, удалите и пересоздайте:
   ```bash
   rm cities.db
   # Бот создаст новую при следующем запуске
   ```

---

## Обновление бота

1. Остановите сервис:
   ```bash
   systemctl --user stop weather-bot.service
   ```

2. Загрузите новые файлы (через SFTP или Git)

3. Перезапустите сервис:
   ```bash
   systemctl --user start weather-bot.service
   ```

---

## Безопасность

1. **Никогда не публикуйте файл `.env`** - он содержит секретные ключи
2. Убедитесь, что `.env` имеет права `600` (только владелец может читать)
3. Регулярно проверяйте логи на подозрительную активность
4. Используйте сильные пароли для SSH доступа

---

## Дополнительная информация

- **Документация Beget:** https://beget.com/ru/kb
- **Telegram Bot API:** https://core.telegram.org/bots/api
- **OpenWeatherMap API:** https://openweathermap.org/api

---

## Контакты и поддержка

Если возникли проблемы:
1. Проверьте логи: `logs/bot_error.log`
2. Убедитесь, что все шаги выполнены правильно
3. Проверьте документацию Beget
