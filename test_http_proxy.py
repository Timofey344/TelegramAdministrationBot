"""
test_http_proxy.py — проверка HTTP-прокси
Запуск: python test_http_proxy.py
"""
import os
import asyncio
import ssl
from dotenv import load_dotenv
import aiohttp

load_dotenv()

async def test_proxy():
    proxy = os.getenv("PROXY_URL")
    if not proxy:
        print("❌ PROXY_URL не задан в .env")
        return
    
    # Отключаем SSL для тестов
    ssl._create_default_https_context = ssl._create_unverified_context
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    
    print(f"🔍 Тест подключения через: {proxy}")
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(
                "https://api.telegram.org",
                proxy=proxy,
                timeout=15
            ) as resp:
                print(f"✅ Успех! Статус: {resp.status}")
        except Exception as e:
            print(f"❌ Ошибка: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_proxy())