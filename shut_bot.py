"""
shut_bot.py
Основной бот «Шут-Надзиратель».
Работает с Supabase через REST API (supabase-py).
Запуск: python shut_bot.py
"""
import asyncio
import logging
import sys
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold, hcode
from aiogram.exceptions import TelegramBadRequest

from config import AppConfig, setup_logging
from database import (
    init_pool, get_or_create_profile, update_balance_atomic,
    cleanup_old_logs, update_heartbeat, get_client
)
from ui_menus import (
    main_menu_kb, games_menu_kb, shop_menu_kb,
    moderation_menu_kb, settings_menu_kb, confirm_kb
)
from games import play_roulette, play_dice, play_coin, play_wheel, _cleanup_cooldowns
from moderation import warn_user, mute_user, ban_user, can_perform_action, ROLE_HIERARCHY

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

logger = logging.getLogger("shut_bot")

# Инициализация
cfg = AppConfig()
cfg.validate()
setup_logging(cfg.log_level)

# Переключаем event loop на Windows для стабильности
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def ensure_profile(user_id: int, username: Optional[str], first_name: str) -> dict:
    """Проверяет/создаёт профиль пользователя."""
    return await get_or_create_profile(user_id, username, first_name)

def is_muted_or_banned(profile: dict) -> Optional[str]:
    """Проверяет статус пользователя на наличие блокировок."""
    if profile["status"] == "banned":
        return "🚫 Ваш аккаунт заблокирован. Обратитесь к администратору."
    if profile["status"] == "muted" and profile.get("muted_until"):
        muted_until = profile["muted_until"]
        if isinstance(muted_until, str):
            muted_until = datetime.fromisoformat(muted_until.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < muted_until:
            remaining = int((muted_until - datetime.now(timezone.utc)).total_seconds() / 60)
            return f"🔇 Вы в муте. Осталось: {remaining} мин."
        # Время вышло — сбрасываем статус (асинхронно, без блокировки)
        asyncio.create_task(_reset_mute_status(profile["telegram_id"]))
    return None

async def _reset_mute_status(tg_id: int) -> None:
    """Сбрасывает статус мута при истечении времени."""
    client = await get_client()
    client.table("profiles").update({
        "status": "active",
        "muted_until": None
    }).eq("telegram_id", tg_id).execute()

def format_balance(balance: float) -> str:
    return f"💰 {balance:,.0f} 🪙"

async def _get_user_stats(tg_id: int) -> dict:
    """Получает статистику игр пользователя."""
    client = await get_client()
    games = client.table("transactions").select("id", count="exact").eq("telegram_id", tg_id).like("type", "game_%").execute()
    wins = client.table("transactions").select("id", count="exact").eq("telegram_id", tg_id).eq("type", "game_win").execute()
    return {"games": games.count or 0, "wins": wins.count or 0}

async def _update_xp(tg_id: int, amount: int):
    """Начисляет опыт пользователю."""
    client = await get_client()
    # Получаем текущий XP
    res = client.table("profiles").select("xp").eq("telegram_id", tg_id).execute()
    if res.data:
        new_xp = (res.data[0].get("xp") or 0) + amount
        client.table("profiles").update({"xp": new_xp}).eq("telegram_id", tg_id).execute()

# --- ОБРАБОТЧИКИ НАВИГАЦИИ ---
@router.message(CommandStart())
async def cmd_start(message: Message):
    profile = await ensure_profile(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )
    block = is_muted_or_banned(profile)
    if block:
        await message.answer(block, parse_mode="HTML")
        return
    await message.answer(
        f"{hbold('Добро пожаловать в Шут-Надзиратель!')}\n"
        f"Ваш баланс: {format_balance(profile['balance'])} | Роль: {profile['role'].capitalize()}\n"
        "Используйте меню ниже для навигации.",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data.startswith("nav:"))
async def nav_handler(cb: CallbackQuery):
    await cb.answer()
    section = cb.data.split(":")[1]
    profile = await ensure_profile(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    block = is_muted_or_banned(profile)
    if block:
        await cb.message.edit_text(block, parse_mode="HTML")
        return

    if section == "main":
        await cb.message.edit_text(f"🏠 Главное меню\n{format_balance(profile['balance'])}", reply_markup=main_menu_kb())
    elif section == "profile":
        stats = await _get_user_stats(cb.from_user.id)
        txt = (
            f"👤 {hbold(profile['display_name'])}\n"
            f"ID: {hcode(profile['telegram_id'])} | Роль: {profile['role'].capitalize()}\n"
            f"{format_balance(profile['balance'])} | ✨ XP: {profile['xp']}\n"
            f"📊 Игр сыграно: {stats['games']} | 🏆 Побед: {stats['wins']}"
        )
        await cb.message.edit_text(txt, parse_mode="HTML", reply_markup=main_menu_kb())
    elif section == "games":
        await cb.message.edit_text("🎲 Выберите игру. Кулдаун: 10 секунд.", reply_markup=games_menu_kb())
    elif section == "shop":
        await cb.message.edit_text("🛒 Магазин. Валюта не имеет реальной ценности.", reply_markup=shop_menu_kb())
    elif section == "moderation":
        if profile["role"] not in ("moderator", "admin", "owner"):
            await cb.answer("❌ Доступно только модераторам.", show_alert=True)
            return
        await cb.message.edit_text("🛡️ Панель модерации.", reply_markup=moderation_menu_kb())
    elif section == "settings":
        await cb.message.edit_text("⚙️ Настройки.", reply_markup=settings_menu_kb())

@router.callback_query(F.data == "nav:daily")
async def claim_daily(cb: CallbackQuery):
    await cb.answer()
    client = await get_client()
    tg_id = cb.from_user.id
    # Проверяем последний бонус
    last = client.table("transactions").select("created_at").eq("telegram_id", tg_id).eq("type", "daily_bonus").order("created_at", desc=True).limit(1).execute()
    if last.data:
        last_time = datetime.fromisoformat(last.data[0]["created_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - last_time < timedelta(hours=18):
            await cb.answer("⏳ Бонус раз в сутки.", show_alert=True)
            return
    await update_balance_atomic(tg_id, 50.0, "daily_bonus")
    await cb.answer("✅ +50 🪙 получено!", show_alert=True)
    await nav_handler(cb)  # Возврат в профиль

# --- ОБРАБОТЧИКИ ИГР ---
@router.callback_query(F.data.startswith("game:"))
async def start_game(cb: CallbackQuery):
    await cb.answer()
    game = cb.data.split(":")[1]
    from ui_menus import InlineKeyboardBuilder, InlineKeyboardButton
    b = InlineKeyboardBuilder()
    for a in [10, 50, 100, 200, 500]:
        b.row(InlineKeyboardButton(text=f"{a} 🪙", callback_data=f"play:{game}:{a}"))
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="nav:games"))
    await cb.message.edit_text(f"🎮 {game.capitalize()}. Выберите ставку:", reply_markup=b.as_markup())

@router.callback_query(F.data.startswith("play:"))
async def execute_game(cb: CallbackQuery):
    await cb.answer()
    _, game, bet_str = cb.data.split(":")
    bet = float(bet_str)
    profile = await ensure_profile(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    if profile["balance"] < bet:
        await cb.answer(f"💸 Недостаточно средств: {profile['balance']}", show_alert=True)
        return

    try:
        if game == "roulette":
            res = await play_roulette(cb.from_user.id, bet)
        elif game == "dice":
            res = await play_dice(cb.from_user.id, bet)
        elif game == "coin":
            res = await play_coin(cb.from_user.id, bet, "орёл")
        elif game == "wheel":
            res = await play_wheel(cb.from_user.id, bet)
        else:
            res = {"success": False, "msg": "❌ Игра не найдена."}
    except Exception as e:
        logger.error(f"Ошибка игры {game}: {e}")
        res = {"success": False, "msg": "⚠️ Ошибка. Попробуйте позже."}

    await cb.message.edit_text(res["msg"], reply_markup=main_menu_kb())
    if res.get("success"):
        await _update_xp(cb.from_user.id, 1)

# --- МАГАЗИН ---
@router.callback_query(F.data.startswith("shop:"))
async def buy_item(cb: CallbackQuery):
    await cb.answer()
    item = cb.data.split(":")[1]
    prices = {"pin": 200, "unmute": 300, "analytics": 150}
    if item not in prices:
        await cb.answer("❌ Недоступно.", show_alert=True)
        return
    profile = await ensure_profile(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    if profile["balance"] < prices[item]:
        await cb.answer(f"💸 Нужно {prices[item]} 🪙", show_alert=True)
        return
    msg = f"🛒 {item} | Цена: {prices[item]} 🪙\nПодтвердить?"
    await cb.message.edit_text(msg, reply_markup=confirm_kb(f"buy:{item}"))

@router.callback_query(F.data.startswith("confirm:buy:"))
async def confirm_purchase(cb: CallbackQuery):
    await cb.answer()
    item = cb.data.replace("confirm:buy:", "")
    prices = {"pin": 200, "unmute": 300, "analytics": 150}
    await update_balance_atomic(cb.from_user.id, -prices[item], "shop_purchase", {"item": item})
    if item == "unmute":
        await _reset_mute_status(cb.from_user.id)
        await cb.message.edit_text("✅ Мут снят.", reply_markup=shop_menu_kb())
    elif item == "analytics":
        client = await get_client()
        rows = client.table("transactions").select("type,amount,created_at").eq("telegram_id", cb.from_user.id).order("created_at", desc=True).limit(5).execute()
        txt = "📊 История:\n" + "\n".join([f"• {r['type']} | {r['amount']:+} 🪙" for r in (rows.data or [])])
        await cb.message.edit_text(txt, reply_markup=shop_menu_kb())
    else:
        await cb.answer("📌 Функция в разработке.", show_alert=True)

# --- МОДЕРАЦИЯ ---
@router.callback_query(F.data.startswith("qmod:"))
async def quick_mod(cb: CallbackQuery):
    await cb.answer()
    executor_profile = await ensure_profile(cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    if executor_profile["role"] not in ("moderator", "admin", "owner"):
        await cb.answer("❌ Нет прав.", show_alert=True)
        return
    parts = cb.data.split(":")
    action, target_id = parts[1], int(parts[2])
    target_profile = await ensure_profile(target_id, None, "User")
    if not can_perform_action(executor_profile["role"], target_profile["role"], {"warn":1, "mute":2, "ban":3}.get(action, 99)):
        await cb.answer("❌ Недостаточно прав для этого действия.", show_alert=True)
        return
    if action == "warn":
        res = await warn_user(cb.from_user.id, target_id, "Быстрое предупреждение")
        await cb.message.edit_text(res["msg"])
    elif action.startswith("mute"):
        mins = int(action[4:]) if action[4:].isdigit() else 60
        res = await mute_user(cb.from_user.id, target_id, mins, "Быстрый мут")
        await cb.message.edit_text(res["msg"])
    elif action == "ban":
        res = await ban_user(cb.from_user.id, target_id, "Быстрый бан")
        await cb.message.edit_text(res["msg"])
    elif action == "del":
        try:
            await cb.bot.delete_message(cb.message.chat.id, cb.message.message_id)
        except:
            await cb.answer("❌ Не удалось удалить.", show_alert=True)

# --- ФОНОВЫЕ ЗАДАЧИ ---
async def background_tasks():
    """Heartbeat + очистка логов + кулдауны."""
    while True:
        await asyncio.sleep(60)
        try:
            await update_heartbeat()
            await cleanup_old_logs()
            _cleanup_cooldowns()
        except Exception as e:
            logger.error(f"Ошибка фоновой задачи: {e}")

# --- ЗАПУСК ---
async def main():
    """Точка входа основного бота «Шут»."""
    
    # 🧪 ТЕСТОВЫЙ РЕЖИМ: демонстрация без подключения к Telegram API
    if cfg.test_mode:
        logger.warning("🧪 ТЕСТОВЫЙ РЕЖИМ: бот работает без подключения к Telegram API")
        logger.warning("📋 Для демонстрации: покажи логи, структуру БД, меню через скриншоты")
        
        # Инициализируем только БД для демонстрации работы с данными
        await init_pool(cfg.supabase_url, cfg.supabase_key)
        
        # Запускаем фоновые задачи (очистка логов, кулдауны)
        asyncio.create_task(background_tasks())
        
        logger.info("✅ Бот «Шут» готов к демонстрации (тестовый режим)")
        logger.info("📊 Доступные команды для демонстрации:")
        logger.info("   • Проверка профиля: вручную через базу данных")
        logger.info("   • Игры: логика работает, баланс обновляется в БД")
        logger.info("   • Модерация: функции доступны, действия логируются")
        
        # Бесконечное ожидание для демонстрации
        await asyncio.Event().wait()
        return
    
    # 🚀 Обычный запуск с подключением к Telegram
    logger.info("🚀 Запуск «Шута»...")
    await init_pool(cfg.supabase_url, cfg.supabase_key)
    asyncio.create_task(background_tasks())
    
    # Создаём бота с поддержкой прокси
    bot = await create_bot_with_proxy(cfg.shut_token, cfg)
    
    await dp.start_polling(bot)

   