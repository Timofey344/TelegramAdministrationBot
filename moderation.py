"""
moderation.py
Инструменты модерации: проверка ролей, выдача предупреждений, мутов, банов.
Атомарно обновляет статусы пользователей и логирует действия.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from database import get_or_create_profile, add_moderation_log

logger = logging.getLogger(__name__)

ROLE_HIERARCHY = {"user": 0, "moderator": 1, "admin": 2, "owner": 3}

def can_perform_action(actor_role: str, target_role: str, action_level: int) -> bool:
    """
    Проверяет RBAC. action_level: 1=warn, 2=mute, 3=ban.
    Модератор(1) может предупреждать(1), но не банить(3).
    """
    actor_lvl = ROLE_HIERARCHY.get(actor_role, 0)
    target_lvl = ROLE_HIERARCHY.get(target_role, 0)
    return actor_lvl >= action_level and actor_lvl > target_lvl

async def warn_user(executor_id: int, target_id: int, reason: str) -> Dict[str, Any]:
    """Выдаёт предупреждение. Логирует в аудит."""
    profile = await get_or_create_profile(target_id, None, "User")
    if not can_perform_action(await _get_role(executor_id), profile["role"], 1):
        return {"success": False, "msg": "❌ Недостаточно прав для предупреждения."}
    
    await add_moderation_log(executor_id, target_id, "warn", reason)
    logger.info(f"⚠️ Warn: {executor_id} -> {target_id} | {reason}")
    return {"success": True, "msg": f"⚠️ Пользователю выдано предупреждение.\n📝 Причина: {reason}"}

async def mute_user(executor_id: int, target_id: int, duration_min: int, reason: str) -> Dict[str, Any]:
    """Накладывает мут. Обновляет статус и expires_at."""
    if not (1 <= duration_min <= 1440):
        return {"success": False, "msg": "❌ Длительность мута: от 1 до 1440 минут."}
    
    profile = await get_or_create_profile(target_id, None, "User")
    if not can_perform_action(await _get_role(executor_id), profile["role"], 2):
        return {"success": False, "msg": "❌ Недостаточно прав для наложения мута."}
    
    muted_until = datetime.now(timezone.utc) + timedelta(minutes=duration_min)
    await add_moderation_log(executor_id, target_id, "mute", reason, duration_min, muted_until)
    # Здесь в реальном боте вызывается API мута чата. Логика статуса обновляется при запросе профиля.
    logger.info(f"🔇 Mute: {executor_id} -> {target_id} | {duration_min} мин | {reason}")
    return {"success": True, "msg": f"🔇 Пользователь заглушен на {duration_min} минут.\n📝 Причина: {reason}"}

async def ban_user(executor_id: int, target_id: int, reason: str) -> Dict[str, Any]:
    """Полная блокировка. Устанавливает status='banned'."""
    profile = await get_or_create_profile(target_id, None, "User")
    if not can_perform_action(await _get_role(executor_id), profile["role"], 3):
        return {"success": False, "msg": "❌ Недостаточно прав для бана."}
    
    await add_moderation_log(executor_id, target_id, "ban", reason)
    logger.info(f"🚫 Ban: {executor_id} -> {target_id} | {reason}")
    return {"success": True, "msg": f"🚫 Пользователь заблокирован.\n📝 Причина: {reason}"}

async def _get_role(telegram_id: int) -> str:
    """Вспомогательная функция получения роли (кэшируется в памяти при необходимости)."""
    profile = await get_or_create_profile(telegram_id, None, "User")
    return profile["role"]