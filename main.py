import os
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

class WeatherBot:
    def __init__(self):
        self.bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
        self.dp = Dispatcher()
        
        # Регистрация обработчиков
        self.dp.message.register(self.start_handler, Command("start"))
        self.dp.message.register(self.weather_handler)

    async def get_weather(self, city: str) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={os.getenv('WEATHER_API_KEY')}&units=metric&lang=ru"
                async with session.get(url) as resp:
                    data = await resp.json()
                    return (
                        f"🌡 Температура: {data['main']['temp']}°C\n"
                        f"💨 Ветер: {data['wind']['speed']} м/с\n"
                        f"☁ {data['weather'][0]['description']}"
                    )
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"

    async def start_handler(self, message: types.Message):
        await message.answer("Привет! Отправь мне название города")

    async def weather_handler(self, message: types.Message):
        weather_report = await self.get_weather(message.text)
        await message.answer(weather_report)

    async def run(self):
        await self.dp.start_polling(self.bot)

if __name__ == "__main__":
    bot = WeatherBot()
    asyncio.run(bot.run())