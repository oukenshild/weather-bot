import os
import aiohttp
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def _openweather_api_key() -> str:
    # поддержка обоих вариантов имен переменной, чтобы не ломать существующие .env
    return os.getenv("OPENWEATHER_API_KEY") or _require_env("WEATHER_API_KEY")


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

    async def get_city_by_id(self, user_id: int, city_id: int) -> str | None:
        def _get_sync(path: str, uid: int, cid: int) -> str | None:
            with sqlite3.connect(path) as db:
                cur = db.execute(
                    "SELECT city FROM cities WHERE user_id = ? AND id = ?",
                    (uid, cid),
                )
                row = cur.fetchone()
                return str(row[0]) if row else None

        return await self._run(_get_sync, self.path, int(user_id), int(city_id))


class AddCity(StatesGroup):
    waiting_for_city = State()


def cities_keyboard(cities: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for city_id, city in cities:
        kb.button(text=city, callback_data=f"city_id:{city_id}")
    kb.button(text="Мой город", callback_data="add_city")
    kb.adjust(2)
    return kb.as_markup()


async def get_forecast(city: str) -> str:
    """
    Прогноз на ближайшие ~18 часов (6 точек по 3 часа) через OpenWeatherMap /forecast.
    """
    api_key = _openweather_api_key()
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": api_key, "units": "metric", "lang": "ru"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            data = await resp.json()

    if resp.status != 200:
        msg = data.get("message", "Неизвестная ошибка API")
        return f"Ошибка OpenWeatherMap: {msg}"

    city_name = data.get("city", {}).get("name") or city
    items = data.get("list") or []
    if not items:
        return f"Не удалось получить прогноз для {city_name}."

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

    return "\n".join(lines)


class WeatherBot:
    def __init__(self):
        self.bot = Bot(token=_require_env("TELEGRAM_TOKEN"))
        self.dp = Dispatcher(storage=MemoryStorage())
        self.db = DB(path=os.getenv("DB_PATH") or "cities.db")

        self.dp.message.register(self.start, CommandStart())
        self.dp.message.register(self.help, Command("help"))
        self.dp.message.register(self.weather_menu, Command("weather"))

        self.dp.callback_query.register(self.on_add_city, F.data == "add_city")
        self.dp.callback_query.register(self.on_city_selected, F.data.startswith("city_id:"))

        self.dp.message.register(self.on_city_text, AddCity.waiting_for_city)

    async def start(self, message: Message, state: FSMContext):
        await state.clear()
        cities = await self.db.list_cities(message.from_user.id)
        if not cities:
            await state.set_state(AddCity.waiting_for_city)
            await message.answer("Привет! Напиши город, для которого нужен прогноз. Я сохраню его для следующих запросов.")
            return

        await message.answer("Выберите город:", reply_markup=cities_keyboard(cities))

    async def help(self, message: Message):
        await message.answer("Команды:\n/start — выбрать/добавить город\n/weather — показать список городов")

    async def weather_menu(self, message: Message, state: FSMContext):
        await state.clear()
        cities = await self.db.list_cities(message.from_user.id)
        if not cities:
            await state.set_state(AddCity.waiting_for_city)
            await message.answer("У вас пока нет сохранённых городов. Напишите город, и я сохраню его.")
            return
        await message.answer("Ваши города:", reply_markup=cities_keyboard(cities))

    async def on_add_city(self, cq: CallbackQuery, state: FSMContext):
        await state.set_state(AddCity.waiting_for_city)
        await cq.message.answer("Введите название вашего города:")
        await cq.answer()

    async def on_city_selected(self, cq: CallbackQuery, state: FSMContext):
        await state.clear()
        raw = (cq.data or "").split("city_id:", 1)[-1].strip()
        try:
            city_id = int(raw)
        except ValueError:
            await cq.answer("Некорректная кнопка", show_alert=True)
            return

        city = await self.db.get_city_by_id(cq.from_user.id, city_id)
        if not city:
            await cq.answer("Город не найден (возможно, список устарел)", show_alert=True)
            return

        text = await get_forecast(city)
        cities = await self.db.list_cities(cq.from_user.id)
        await cq.message.answer(text, reply_markup=cities_keyboard(cities))
        await cq.answer()

    async def on_city_text(self, message: Message, state: FSMContext):
        city = (message.text or "").strip()
        if not city:
            await message.answer("Пожалуйста, введите название города текстом.")
            return

        await self.db.add_city(message.from_user.id, city)
        await state.clear()

        text = await get_forecast(city)
        cities = await self.db.list_cities(message.from_user.id)
        await message.answer(text, reply_markup=cities_keyboard(cities))

    async def run(self):
        await self.db.init()
        await self.dp.start_polling(self.bot)


if __name__ == "__main__":
    asyncio.run(WeatherBot().run())