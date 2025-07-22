import os
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()

class WeatherBot:
    def __init__(self):
        self.bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
        self.dp = Dispatcher()
        
        # Регистрация обработчиков
        self.dp.message.register(self.cmd_start, Command("start", "help"))
        self.dp.message.register(self.handle_city_button, self.city_filter)
        self.dp.message.register(self.handle_other_cities)

    # Создаем клавиатуру с городами
        self.city_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Екатеринбург"), KeyboardButton(text="Сочи")],
                [KeyboardButton(text="Арамиль"), KeyboardButton(text="Калининград")],
                [KeyboardButton(text="Мой город")]  # Для ручного ввода
            ],
            resize_keyboard=True,
            input_field_placeholder="Выберите город"
        )

    def city_filter(self, message: types.Message) -> bool:
        """Фильтр для обработки кнопок городов"""
        return message.text in ["Екатеринбург", "Сочи", "Арамиль", "Калининград"]

    async def get_weather(self, city: str) -> str:
        """Запрос погоды через OpenWeatherMap API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={os.getenv('WEATHER_API_KEY')}&units=metric&lang=ru"
                async with session.get(url) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        return f"Ошибка: {data.get('message', 'Неизвестная ошибка API')}"
                    temp = data["main"]["temp"]
                    feels_like = data["main"]["feels_like"]
                    wind = data["wind"]["speed"]
                    description = data["weather"][0]["description"]
                    return (
                        f"🌤 Погода в {city}:\n"
                        f"• {description.capitalize()}\n"
                        f"• Температура: {temp}°C (ощущается как {feels_like}°C)\n"
                        f"• Ветер: {wind} м/с"
                    )
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"

    async def cmd_start(self, message: types.Message):
        """Обработчик команд /start и /help"""
        await message.answer(
            "Выберите город из списка или введите название вручную:",
            reply_markup=self.city_keyboard
        )

    async def handle_city_button(self, message: types.Message):
        """Обработчик кнопок с городами"""
        try:
            weather = await self.get_weather(message.text)
            await message.answer(weather, reply_markup=self.city_keyboard)
        except Exception as e:
            await message.answer(f"🚫 Ошибка: {str(e)}")

    async def handle_other_cities(self, message: types.Message):
        """Обработчик ручного ввода города"""
        if message.text == "Мой город":
            await message.answer("Введите название вашего города:")
            return
        
        try:
            weather = await self.get_weather(message.text)
            await message.answer(weather, reply_markup=self.city_keyboard)
        except Exception as e:
            await message.answer(f"🚫 Ошибка: {str(e)}")

    async def run(self):
        await self.dp.start_polling(self.bot)

if __name__ == "__main__":
    bot = WeatherBot()
    asyncio.run(bot.run())