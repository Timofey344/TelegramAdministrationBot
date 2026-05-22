"""
test_proxy.py — проверка подключения к Telegram через прокси
Запуск: python test_proxy.py
"""
import asyncio
import os
from dotenv import load_dotenv
from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector

load_dotenv()

async def test_connection():
    proxy_url = os.getenv("PROXY_URL")
    
    if not proxy_url:
        print("❌ PROXY_URL не задан в .env")
        return
    
    print(f"🔍 Тест подключения через: {proxy_url}")
    
    try:
        connector = ProxyConnector.from_url(proxy_url, ssl=True)
        async with ClientSession(connector=connector) as session:
            async with session.get("https://api.telegram.org", timeout=10) as resp:
                print(f"✅ Успех! Статус: {resp.status}")
                print(f"📡 Заголовки: {dict(resp.headers)}")
    except Exception as e:
        print(f"❌ Ошибка: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())