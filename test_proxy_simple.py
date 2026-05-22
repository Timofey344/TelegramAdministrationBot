"""
test_proxy_simple.py — упрощённый тест с отключённым SSL
"""
import asyncio
import ssl
import os
from dotenv import load_dotenv
from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector

load_dotenv()

async def test_connection():
    proxy_url = os.getenv("PROXY_URL")
    if not proxy_url:
        print("❌ PROXY_URL не задан")
        return
    
    # Отключаем проверку сертификатов (только для тестов!)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    print(f"🔍 Тест: {proxy_url} (SSL-проверка отключена)")
    
    try:
        connector = ProxyConnector.from_url(proxy_url, ssl=ssl_ctx)
        async with ClientSession(connector=connector) as session:
            async with session.get("https://api.telegram.org", timeout=15) as resp:
                print(f"✅ Успех! Статус: {resp.status}")
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())