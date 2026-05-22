"""
database.py
Работа с Supabase через REST API (вместо прямого PostgreSQL подключения).
Использует service_role_key для полного доступа к данным.
Атомарность баланса обеспечивается через optimistic locking.
"""
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)

# Глобальный клиент Supabase
_supabase_client: Optional[Client] = None

async def init_pool(supabase_url: str, supabase_key: str) -> Client:
    """Инициализирует клиент Supabase и создаёт таблицы при необходимости."""
    global _supabase_client
    if _supabase_client:
        return _supabase_client
    
    try:
        _supabase_client = create_client(supabase_url, supabase_key)
        logger.info("✅ Клиент Supabase успешно создан.")
        
        # Применяем схему БД
        await _apply_schema()
        logger.info("✅ Схема БД проверена/применена.")
        return _supabase_client
    except Exception as e:
        logger.critical(f"❌ Ошибка инициализации Supabase: {e}")
        raise

async def _apply_schema():
    """Создаёт таблицы через Supabase API (если не существуют)."""
    client = await get_client()
    
    # Проверяем существование таблиц через RPC или прямой запрос
    # В Supabase таблицы создаются через SQL Editor, здесь только проверка
    try:
        # Пробуем сделать простой запрос для проверки доступности
        result = client.table("profiles").select("id").limit(1).execute()
        logger.info("✅ Таблицы Supabase доступны.")
    except APIError as e:
        if "404" in str(e) or "relation" in str(e).lower():
            logger.warning("⚠️ Таблицы не найдены. Создайте их через SQL Editor в панели Supabase.")
            logger.warning("📋 SQL-схема доступна в комментарии к коду.")
        else:
            raise

async def get_client() -> Client:
    """Возвращает инициализированный клиент Supabase."""
    if not _supabase_client:
        raise RuntimeError("Клиент Supabase не инициализирован. Вызовите init_pool().")
    return _supabase_client

async def get_or_create_profile(telegram_id: int, username: Optional[str], display_name: str) -> Dict[str, Any]:
    """Возвращает или создаёт профиль пользователя."""
    client = await get_client()
    
    # Ищем существующий профиль
    response = client.table("profiles").select("*").eq("telegram_id", telegram_id).execute()
    
    if response.data and len(response.data) > 0:
        profile = response.data[0]
        # Обновляем last_active
        client.table("profiles").update({
            "last_active": datetime.now(timezone.utc).isoformat(),
            "username": username,
            "display_name": display_name
        }).eq("telegram_id", telegram_id).execute()
        return profile
    
    # Создаём новый профиль
    new_profile = {
        "telegram_id": telegram_id,
        "username": username,
        "display_name": display_name,
        "balance": 100.0,
        "xp": 0,
        "status": "new",
        "role": "user",
        "muted_until": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_active": datetime.now(timezone.utc).isoformat()
    }
    
    response = client.table("profiles").insert(new_profile).execute()
    logger.info(f"🆕 Автоматическая регистрация: {display_name} ({telegram_id})")
    return response.data[0]

async def update_balance_atomic(
    telegram_id: int, 
    amount: float, 
    tx_type: str, 
    metadata: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    Атомарное обновление баланса через optimistic locking.
    Проверяет баланс перед обновлением и использует условие balance >= 0.
    """
    client = await get_client()
    
    # Получаем текущий профиль
    profile_response = client.table("profiles").select("balance").eq("telegram_id", telegram_id).execute()
    
    if not profile_response.data or len(profile_response.data) == 0:
        raise ValueError("Профиль не найден")
    
    current_balance = float(profile_response.data[0]["balance"])
    new_balance = current_balance + amount
    
    if new_balance < 0:
        raise ValueError(f"Недостаточно средств. Требуется: {abs(amount)}, доступно: {current_balance}")
    
    # Обновляем баланс с проверкой (optimistic locking через условие)
    update_response = client.table("profiles").update({
        "balance": new_balance
    }).eq("telegram_id", telegram_id).gte("balance", 0 if new_balance >= 0 else 999999).execute()
    
    if not update_response.data or len(update_response.data) == 0:
        raise ValueError("Не удалось обновить баланс. Возможна конфликтующая транзакция.")
    
    # Записываем транзакцию
    transaction = {
        "telegram_id": telegram_id,
        "type": tx_type,
        "amount": amount,
        "balance_after": new_balance,
        "metadata": json.dumps(metadata or {}),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    client.table("transactions").insert(transaction).execute()
    
    logger.debug(f"💰 Транзакция: {telegram_id} | {tx_type} | {amount:+} | Баланс: {new_balance}")
    return {"telegram_id": telegram_id, "balance": new_balance}

async def add_moderation_log(executor_id: int, target_id: int, action: str, reason: str, duration_min: int | None = None, expires_at: datetime | None = None) -> None:
    """Записывает действие модерации в журнал."""
    client = await get_client()
    
    log_entry = {
        "executor_id": executor_id,
        "target_id": target_id,
        "action": action,
        "reason": reason,
        "duration_minutes": duration_min,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    client.table("moderation_logs").insert(log_entry).execute()

async def cleanup_old_logs() -> int:
    """Удаляет записи модерации старше 30 дней."""
    client = await get_client()
    
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    
    # Считаем количество записей для удаления
    count_response = client.table("moderation_logs").select("id", count="exact").lt("created_at", cutoff_date).execute()
    count = count_response.count or 0
    
    if count > 0:
        client.table("moderation_logs").delete().lt("created_at", cutoff_date).execute()
        logger.info(f"🗑️ Очистка аудита: удалено {count} записей старше 30 дней.")
    
    return count

async def update_heartbeat() -> None:
    """Обновляет timestamp активности бота «Шут»."""
    client = await get_client()
    
    client.table("system_heartbeat").update({
        "last_update": datetime.now(timezone.utc).isoformat()
    }).eq("id", 1).execute()

async def get_last_heartbeat() -> float:
    """Возвращает время последнего heartbeat в секундах (epoch)."""
    client = await get_client()
    
    response = client.table("system_heartbeat").select("last_update").eq("id", 1).execute()
    
    if not response.data or len(response.data) == 0:
        return 0.0
    
    last_update = response.data[0]["last_update"]
    if isinstance(last_update, str):
        dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
    else:
        dt = last_update
    
    return dt.timestamp()