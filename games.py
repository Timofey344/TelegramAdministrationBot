"""
games.py
Логика 4 мини-игр. Использует криптографически стойкий ГПСЧ secrets.SystemRandom.
Все финансовые операции проходят через атомарные транзакции БД.
Реализован in-memory кэш кулдаунов с TTL для защиты от спама.
"""
import secrets
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from database import update_balance_atomic, add_moderation_log

logger = logging.getLogger(__name__)

# Простой in-memory кэш кулдаунов: {user_id: (timestamp, ttl)}
_cooldowns: Dict[int, float] = {}

def check_cooldown(user_id: int, ttl_sec: int = 10) -> bool:
    """Возвращает True, если пользователь может играть. Иначе False."""
    now = time.time()
    if user_id in _cooldowns:
        if now < _cooldowns[user_id]:
            return False
    _cooldowns[user_id] = now + ttl_sec
    return True

def _cleanup_cooldowns() -> None:
    """Удаляет истёкшие записи кэша. Вызывается фоновой задачей."""
    now = time.time()
    _cooldowns.update((k, v) for k, v in list(_cooldowns.items()) if v > now)

rng = secrets.SystemRandom()

async def play_roulette(telegram_id: int, bet: float) -> Dict[str, Any]:
    """Русская рулетка: 1/6 шанс проигрыша. Проигрыш = ставка + мут 30 мин."""
    if not check_cooldown(telegram_id):
        return {"success": False, "msg": "⏳ Подождите 10 секунд перед следующей игрой."}
    try:
        await update_balance_atomic(telegram_id, -bet, "game_lose", {"game": "roulette", "status": "bet_placed"})
    except ValueError as e:
        return {"success": False, "msg": f"💸 {e}"}

    result = rng.randint(1, 6)
    if result == 1:
        # Проигрыш: мут на 30 мин
        muted_until = datetime.utcnow() + timedelta(minutes=30)
        await add_moderation_log(0, telegram_id, "mute", "Проигрыш в рулетке", 30, muted_until)
        return {"success": True, "msg": "🔫 *БАХ!* Вы проиграли. Ставка списана, мут на 30 минут.", "muted": True}
    else:
        # Возврат ставки + бонус 20% за риск
        win_amount = bet * 0.2
        await update_balance_atomic(telegram_id, bet + win_amount, "game_win", {"game": "roulette", "multiplier": 1.2})
        return {"success": True, "msg": f"🔫 Выстрел пустой! Ставка возвращена + {win_amount:.0f} монет бонусом.", "won": True}

async def play_dice(telegram_id: int, bet: float) -> Dict[str, Any]:
    """Кубики: игрок vs бот. Кто больше — получает x2 ставку."""
    if not check_cooldown(telegram_id):
        return {"success": False, "msg": "⏳ Подождите 10 секунд перед следующей игрой."}
    try:
        await update_balance_atomic(telegram_id, -bet, "game_lose", {"game": "dice"})
    except ValueError as e:
        return {"success": False, "msg": f"💸 {e}"}

    player_roll = rng.randint(1, 6)
    bot_roll = rng.randint(1, 6)

    if player_roll > bot_roll:
        win_amount = bet * 2
        await update_balance_atomic(telegram_id, win_amount, "game_win", {"game": "dice", "rolls": f"{player_roll} vs {bot_roll}"})
        return {"success": True, "msg": f"🎲 Победа! Вы: {player_roll}, Бот: {bot_roll}. Баланс: +{win_amount:.0f} монет."}
    elif player_roll < bot_roll:
        return {"success": True, "msg": f"🎲 Проигрыш. Вы: {player_roll}, Бот: {bot_roll}. Ставка ушла."}
    else:
        await update_balance_atomic(telegram_id, bet, "game_refund", {"game": "dice"})
        return {"success": True, "msg": f"🎲 Ничья ({player_roll} vs {bot_roll}). Ставка возвращена."}

async def play_coin(telegram_id: int, bet: float, choice: str) -> Dict[str, Any]:
    """Орёл/Решка. Угадал = x2."""
    if not check_cooldown(telegram_id):
        return {"success": False, "msg": "⏳ Подождите 10 секунд перед следующей игрой."}
    choice = choice.lower()
    if choice not in ("heads", "tails", "орёл", "решка"):
        return {"success": False, "msg": "❌ Выберите 'орёл' или 'решка'."}
    try:
        await update_balance_atomic(telegram_id, -bet, "game_lose", {"game": "coin"})
    except ValueError as e:
        return {"success": False, "msg": f"💸 {e}"}

    result = rng.choice(["орёл", "решка"])
    normalized_choice = "орёл" if choice in ("орёл", "heads") else "решка"

    if result == normalized_choice:
        win_amount = bet * 2
        await update_balance_atomic(telegram_id, win_amount, "game_win", {"game": "coin", "choice": result})
        return {"success": True, "msg": f"🪙 Угадали! Выпало: {result}. Баланс: +{win_amount:.0f} монет."}
    else:
        return {"success": True, "msg": f"🪙 Мимо. Выпало: {result}. Ставка списана."}

async def play_wheel(telegram_id: int, bet: float) -> Dict[str, Any]:
    """Колесо фортуны: 8 секторов."""
    if not check_cooldown(telegram_id):
        return {"success": False, "msg": "⏳ Подождите 10 секунд перед следующей игрой."}
    try:
        await update_balance_atomic(telegram_id, -bet, "game_lose", {"game": "wheel"})
    except ValueError as e:
        return {"success": False, "msg": f"💸 {e}"}

    sectors = [
        ("x0.0", 0.0), ("x0.5", 0.5), ("x1.0", 1.0), ("x1.5", 1.5),
        ("x2.0", 2.0), ("x3.0", 3.0), ("🔥 x5.0", 5.0), ("💀 Мут 15м", -1.0)
    ]
    label, multiplier = rng.choice(sectors)

    if multiplier == -1.0:
        muted_until = datetime.utcnow() + timedelta(minutes=15)
        await add_moderation_log(0, telegram_id, "mute", "Сектор колеса фортуны", 15, muted_until)
        return {"success": True, "msg": "🎡 Крутим... 💀 Сектор 'Мут 15 минут'! Ставка списана, ограничение на чат.", "muted": True}
    
    win_amount = bet * multiplier
    await update_balance_atomic(telegram_id, win_amount, "game_win", {"game": "wheel", "sector": label})
    return {"success": True, "msg": f"🎡 Крутим... 🎉 Сектор {label}! Баланс: +{win_amount:.0f} монет."}