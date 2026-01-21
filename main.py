import os
import asyncio
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def _openweather_api_key() -> str:
    # поддержка обоих вариантов имен переменной, чтобы не ломать существующие .env
    return os.getenv("OPENWEATHER_API_KEY") or _require_env("WEATHER_API_KEY")


def load_env_file(path: str = ".env") -> None:
    """
    Мини-замена python-dotenv без зависимостей.
    Поддерживает строки KEY=VALUE, пустые строки и комментарии #.
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # если .env повреждён/в другой кодировке — просто игнорируем
        return


load_env_file()


# Setup logging
def setup_logging():
    """Configure logging for the bot."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'bot.log'), encoding='utf-8'),
            logging.StreamHandler()  # Also log to console
        ]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


class DB:
    def __init__(self, path: str):
        self.path = path
        # SQLite is sync; keep it off the event loop.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="db")

    async def _run(self, fn, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: fn(*args))

    async def init(self) -> None:
        def _init_sync(path: str) -> None:
            with sqlite3.connect(path) as db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        city TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        UNIQUE(user_id, city)
                    )
                    """
                )
                db.commit()

        await self._run(_init_sync, self.path)

    async def add_city(self, user_id: int, city: str) -> None:
        city = city.strip()
        if not city:
            return

        def _add_sync(path: str, uid: int, c: str) -> None:
            with sqlite3.connect(path) as db:
                db.execute(
                    "INSERT OR IGNORE INTO cities(user_id, city) VALUES(?, ?)",
                    (uid, c),
                )
                db.commit()

        await self._run(_add_sync, self.path, int(user_id), city)

    async def list_cities(self, user_id: int) -> list[tuple[int, str]]:
        def _list_sync(path: str, uid: int) -> list[tuple[int, str]]:
            with sqlite3.connect(path) as db:
                cur = db.execute(
                    "SELECT id, city FROM cities WHERE user_id = ? ORDER BY created_at ASC, id ASC",
                    (uid,),
                )
                rows = cur.fetchall()
                return [(int(r[0]), str(r[1])) for r in rows]

        return await self._run(_list_sync, self.path, int(user_id))

    async def get_city_by_id(self, user_id: int, city_id: int) -> Optional[str]:
        def _get_sync(path: str, uid: int, cid: int) -> Optional[str]:
            with sqlite3.connect(path) as db:
                cur = db.execute(
                    "SELECT city FROM cities WHERE user_id = ? AND id = ?",
                    (uid, cid),
                )
                row = cur.fetchone()
                return str(row[0]) if row else None

        return await self._run(_get_sync, self.path, int(user_id), int(city_id))

def cities_keyboard(cities: list[tuple[int, str]]) -> dict:
    # Telegram Bot API inline keyboard format
    rows: list[list[dict]] = []
    row: list[dict] = []
    for city_id, city in cities:
        row.append({"text": city, "callback_data": f"city_id:{city_id}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "Мой город", "callback_data": "add_city"}])
    return {"inline_keyboard": rows}


async def get_forecast(city: str) -> tuple[bool, str]:
    """
    Прогноз на ближайшие ~18 часов (6 точек по 3 часа) через OpenWeatherMap /forecast.
    """
    api_key = _openweather_api_key()
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": api_key, "units": "metric", "lang": "ru"}

    def _fetch_forecast_sync() -> tuple[int, dict]:
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            full_url,
            headers={"Accept": "application/json", "User-Agent": "weather-bot/1.0"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = int(getattr(resp, "status", 200))
                body = resp.read()
        except urllib.error.HTTPError as e:
            status = int(getattr(e, "code", 500))
            body = e.read()
        except Exception:
            return 0, {"message": "network_error"}

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {"message": "bad_json"}
        return status, data

    status, data = await asyncio.to_thread(_fetch_forecast_sync)

    if status != 200:
        msg = data.get("message", "Неизвестная ошибка API")
        return False, f"Ошибка OpenWeatherMap: {msg}"

    city_name = data.get("city", {}).get("name") or city
    items = data.get("list") or []
    if not items:
        return False, f"Не удалось получить прогноз для {city_name}."

    lines: list[str] = [f"Прогноз для {city_name} (ближайшие часы):"]
    for item in items[:6]:
        dt_txt = item.get("dt_txt", "")
        time_part = dt_txt[11:16] if len(dt_txt) >= 16 else dt_txt
        main = item.get("main") or {}
        temp = main.get("temp")
        feels = main.get("feels_like")
        wind = (item.get("wind") or {}).get("speed")
        desc = ((item.get("weather") or [{}])[0]).get("description", "")

        t = f"{round(temp)}°C" if isinstance(temp, (int, float)) else "—"
        f = f"{round(feels)}°C" if isinstance(feels, (int, float)) else "—"
        w = f"{wind} м/с" if isinstance(wind, (int, float)) else "—"
        d = desc.capitalize() if isinstance(desc, str) and desc else "—"

        lines.append(f"{time_part}: {t} (ощущается {f}), {d}, ветер {w}")

    return True, "\n".join(lines)


class TelegramAPI:
    def __init__(self, token: str):
        self.base_url = f"https://api.telegram.org/bot{token}/"

    async def call(self, method: str, payload: dict) -> dict:
        def _call_sync() -> dict:
            url = self.base_url + method
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=35) as resp:
                    raw = resp.read()
            except urllib.error.HTTPError as e:
                raw = e.read()
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {"ok": False, "description": "bad_json"}

        return await asyncio.to_thread(_call_sync)

    async def get_updates(self, offset: int, timeout: int = 30) -> list[dict]:
        res = await self.call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": ["message", "callback_query"],
            },
        )
        if not res.get("ok"):
            return []
        return res.get("result") or []

    async def send_message(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        await self.call("sendMessage", payload)

    async def answer_callback(self, callback_query_id: str, text: Optional[str] = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self.call("answerCallbackQuery", payload)


def _command_name(text: str) -> str:
    # /start, /start@BotName, "/start arg"
    if not text:
        return ""
    first = text.strip().split()[0]
    if not first.startswith("/"):
        return ""
    return first.split("@", 1)[0]


async def run_bot() -> None:
    try:
        token = _require_env("TELEGRAM_TOKEN")
        logger.info("Starting Telegram Weather Bot...")
        api = TelegramAPI(token)
        db_path = os.getenv("DB_PATH") or "cities.db"
        db = DB(path=db_path)
        await db.init()
        logger.info(f"Database initialized at {db_path}")

        awaiting_city: set[int] = set()
        offset = 0
        logger.info("Bot is running and waiting for updates...")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}", exc_info=True)
        raise

    async def send_menu(chat_id: int, user_id: int, title: str = "Выберите город:") -> None:
        cities = await db.list_cities(user_id)
        if not cities:
            awaiting_city.add(user_id)
            await api.send_message(chat_id, "Напишите город, для которого нужен прогноз. Я сохраню его.")
            return
        await api.send_message(chat_id, title, reply_markup=cities_keyboard(cities))

    async def send_forecast(chat_id: int, user_id: int, text: str) -> None:
        cities = await db.list_cities(user_id)
        markup = cities_keyboard(cities) if cities else None
        await api.send_message(chat_id, text, reply_markup=markup)

    while True:
        try:
            updates = await api.get_updates(offset=offset, timeout=30)
            for upd in updates:
                offset = max(offset, int(upd.get("update_id", 0)) + 1)

                if "message" in upd:
                    msg = upd["message"] or {}
                    text = (msg.get("text") or "").strip()
                    chat_id = int((msg.get("chat") or {}).get("id"))
                    user_id = int((msg.get("from") or {}).get("id"))

                    cmd = _command_name(text)
                    if cmd in ("/start",):
                        await send_menu(chat_id, user_id)
                        continue
                    if cmd in ("/help",):
                        await api.send_message(chat_id, "Команды:\n/start — выбрать/добавить город\n/weather — показать список городов")
                        continue
                    if cmd in ("/weather",):
                        await send_menu(chat_id, user_id, title="Ваши города:")
                        continue

                    # обычный текст = город (если ждём ввода или пользователь просто написал город)
                    city = text
                    if not city:
                        continue

                    ok, forecast = await get_forecast(city)
                    if ok:
                        cities_before = await db.list_cities(user_id)
                        should_save = (user_id in awaiting_city) or (len(cities_before) == 0)
                        if should_save:
                            await db.add_city(user_id, city)
                            awaiting_city.discard(user_id)

                    await send_forecast(chat_id, user_id, forecast)
                    await send_menu(chat_id, user_id)

                elif "callback_query" in upd:
                    cq = upd["callback_query"] or {}
                    data = (cq.get("data") or "").strip()
                    callback_id = str(cq.get("id") or "")
                    user_id = int((cq.get("from") or {}).get("id"))
                    chat_id = int((((cq.get("message") or {}).get("chat") or {}).get("id")))

                    if data == "add_city":
                        awaiting_city.add(user_id)
                        await api.send_message(chat_id, "Введите название вашего города:")
                        await api.answer_callback(callback_id)
                        continue

                    if data.startswith("city_id:"):
                        raw = data.split("city_id:", 1)[-1].strip()
                        try:
                            city_id = int(raw)
                        except ValueError:
                            await api.answer_callback(callback_id, "Некорректная кнопка")
                            continue

                        city = await db.get_city_by_id(user_id, city_id)
                        if not city:
                            await api.answer_callback(callback_id, "Город не найден")
                            continue

                        _, forecast = await get_forecast(city)
                        await send_forecast(chat_id, user_id, forecast)
                        await send_menu(chat_id, user_id)
                        await api.answer_callback(callback_id)
                        continue

                    await api.answer_callback(callback_id)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            raise
        except Exception as e:
            logger.error(f"Error processing update: {e}", exc_info=True)
            # небольшая пауза на случай временных сетевых ошибок
            await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise