"""
strazh_bot.py
Сервисный бот «Страж».
Мониторинг, бэкапы, рестарты через Supabase REST API.
Запуск: python strazh_bot.py
"""
import asyncio
import json
import logging
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import AppConfig, setup_logging
from database import init_pool, get_client, get_last_heartbeat, cleanup_old_logs

# Глобальная настройка SSL для обхода самоподписанных сертификатов (только тест!)
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

async def create_bot_with_proxy(token: str, cfg: AppConfig) -> Bot:
    """Создаёт Bot с поддержкой HTTP/HTTPS прокси через env-переменные."""
    from aiogram.client.bot import DefaultBotProperties
    from aiogram.client.session.aiohttp import AiohttpSession
    import os
    import ssl
    
    # Настраиваем прокси через стандартные переменные окружения
    if cfg.use_proxy and cfg.proxy_url:
        proxy = cfg.proxy_url
        
        # aiohttp автоматически подхватывает HTTP_PROXY/HTTPS_PROXY
        os.environ['HTTP_PROXY'] = proxy
        os.environ['HTTPS_PROXY'] = proxy
        os.environ['ALL_PROXY'] = proxy  # Для совместимости
        
        # Отключаем проверку SSL только для тестов с самоподписанными сертификатами
        if not cfg.proxy_verify_ssl:
            os.environ['PYTHONHTTPSVERIFY'] = '0'
            ssl._create_default_https_context = ssl._create_unverified_context
            logger.warning("⚠️ SSL-проверка отключена (только для тестов!)")
        
        logger.info(f"🔐 HTTP-прокси настроен: {proxy}")
    else:
        logger.info("🌐 Прямое подключение к Telegram API")
    
    # Создаём стандартную сессию — aiohttp сам использует прокси из env
    aiogram_session = AiohttpSession()
    
    return Bot(
        token=token,
        session=aiogram_session,
        default=DefaultBotProperties(parse_mode="HTML")
    )

logger = logging.getLogger("strazh_bot")
cfg = AppConfig()
cfg.validate()
setup_logging(cfg.log_level)

dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- ФИЛЬТРЫ ---
async def owner_only(message: Message) -> bool:
    if message.from_user.id in cfg.owner_ids:
        return True
    logger.warning(f"⛔ Отказано: {message.from_user.id}")
    return False

# --- КОМАНДЫ ---
@router.message(Command("start"), F.from_user.id.in_(cfg.owner_ids))
async def cmd_start(message: Message):
    await message.answer(
        "🛡️ «Страж» онлайн.\n"
        "/status — проверка «Шута»\n"
        "/backup — ручной бэкап\n"
        "/restart — перезапуск «Шута»\n"
        "/clean — очистка логов"
    )

@router.message(Command("status"), F.from_user.id.in_(cfg.owner_ids))
async def cmd_status(message: Message):
    last_hb = await get_last_heartbeat()
    now = datetime.now(timezone.utc).timestamp()
    diff = now - last_hb
    status = "🟢 Онлайн" if diff < 120 else "🔴 Нет ответа"
    await message.answer(f"📡 {status}\n⏱️ Задержка: {int(diff)} сек.")

@router.message(Command("backup"), F.from_user.id.in_(cfg.owner_ids))
async def cmd_backup(message: Message):
    await message.answer("💾 Запуск бэкапа...")
    path = await _export_backup()
    await message.answer(f"✅ Сохранено: {path}")

@router.message(Command("restart"), F.from_user.id.in_(cfg.owner_ids))
async def cmd_restart(message: Message):
    await message.answer("🔄 Перезапуск «Шута»...")
    try:
        subprocess.Popen(
            [sys.executable, "shut_bot.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=os.getcwd()
        )
        await message.answer("✅ Процесс запущен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("clean"), F.from_user.id.in_(cfg.owner_ids))
async def cmd_clean(message: Message):
    count = await cleanup_old_logs()
    await message.answer(f"🗑️ Удалено: {count} записей")

# --- ФОНОВЫЕ ЦИКЛЫ ---
async def health_monitor(bot: Bot):
    """Проверка heartbeat каждые 60 сек."""
    while True:
        await asyncio.sleep(60)
        try:
            last = await get_last_heartbeat()
            diff = datetime.now(timezone.utc).timestamp() - last
            if diff > 120:
                logger.critical(f"🚨 «Шут» не отвечает {int(diff)} сек.")
                for oid in cfg.owner_ids:
                    try:
                        await bot.send_message(oid, "🚨 АЛАРТ: «Шут» упал. Рестарт...")
                    except: pass
                try:
                    subprocess.Popen([sys.executable, "shut_bot.py"], start_new_session=True, cwd=os.getcwd())
                except Exception as e:
                    logger.error(f"❌ Авто-рестарт: {e}")
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")

async def daily_backup():
    """Ежедневный бэкап в 03:00 UTC."""
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        sleep_sec = (target - now).total_seconds()
        if sleep_sec > 0:
            await asyncio.sleep(sleep_sec)
        await _export_backup()
        logger.info("📅 Авто-бэкап выполнен")

async def _export_backup() -> str:
    """Экспорт данных в JSON."""
    Path("backups").mkdir(exist_ok=True)
    filename = f"backups/backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    client = await get_client()
    data = {}
    for table in ["profiles", "transactions", "moderation_logs"]:
        rows = client.table(table).select("*").execute()
        data[table] = rows.data or []
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return filename

# --- ЗАПУСК ---
async def main():
    """Точка входа сервисного бота «Страж»."""
    
    # 🧪 ТЕСТОВЫЙ РЕЖИМ
    if cfg.test_mode:
        logger.warning("🧪 ТЕСТОВЫЙ РЕЖИМ: «Страж» работает без подключения к Telegram")
        await init_pool(cfg.supabase_url, cfg.supabase_key)
        
        logger.info("✅ Бот «Страж» готов к демонстрации (тестовый режим)")
        logger.info("📊 Доступные функции:")
        logger.info("   • Heartbeat: обновляется в БД каждые 60 сек")
        logger.info("   • Бэкапы: можно запустить вручную через консоль")
        logger.info("   • Мониторинг: логи пишутся в system.log")
        
        await asyncio.Event().wait()
        return
    
    # 🛡️ Обычный запуск
    logger.info("🛡️ Запуск «Стража»...")
    await init_pool(cfg.supabase_url, cfg.supabase_key)
    
    bot = await create_bot_with_proxy(cfg.strazh_token, cfg)
    
    asyncio.create_task(health_monitor(bot))
    asyncio.create_task(daily_backup())
    
    await dp.start_polling(bot)