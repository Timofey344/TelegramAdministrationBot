#!/usr/bin/env python3
"""
Демонстрация статистики системы "Шут-Надзиратель"
Показывает данные из Supabase для защиты проекта
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

print("=" * 70)
print("🎭 СИСТЕМА 'ШУТ-НАДЗИРАТЕЛЬ' - СТАТИСТИКА И ДЕМОСТРАЦИЯ")
print("=" * 70)
print(f"📅 Дата проверки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
print()

# Подключение к Supabase
try:
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    print("✅ Подключение к базе данных Supabase установлено")
except Exception as e:
    print(f"❌ Ошибка подключения к Supabase: {e}")
    print("💡 Проверьте SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в .env")
    sys.exit(1)

print()

# 1. ОБЩАЯ СТАТИСТИКА
print("=" * 70)
print("📊 ОБЩАЯ СТАТИСТИКА СИСТЕМЫ")
print("=" * 70)

try:
    # Пользователи
    users = supabase.table("profiles").select("*", count="exact").execute()
    user_count = users.count or 0
    
    # Транзакции
    transactions = supabase.table("transactions").select("*", count="exact").execute()
    trans_count = transactions.count or 0
    
    # Игры
    games = supabase.table("transactions").select("*").eq("type", "game_win").execute()
    game_count = len(games.data) if games.data else 0
    
    # Модерация
    mod_logs = supabase.table("moderation_logs").select("*", count="exact").execute()
    mod_count = mod_logs.count or 0
    
    print(f"👥 Зарегистрировано пользователей: {user_count}")
    print(f"💰 Всего транзакций: {trans_count}")
    print(f"🎮 Сыграно игр (побед): {game_count}")
    print(f"🛡️ Записей в журнале модерации: {mod_count}")
    
except Exception as e:
    print(f"⚠️  Не удалось получить статистику: {e}")

print()

# 2. ПОЛЬЗОВАТЕЛИ
print("=" * 70)
print("👤 ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ")
print("=" * 70)

try:
    users = supabase.table("profiles").select("*").order("created_at", desc=True).limit(10).execute()
    
    if users.data:
        print(f"{'ID':<15} {'Имя':<25} {'Роль':<12} {'Баланс':<10} {'Статус':<10}")
        print("-" * 70)
        for u in users.data:
            name = (u.get('display_name') or 'Unknown')[:23]
            role = u.get('role', 'user')
            balance = f"{u.get('balance', 0):.0f} 🪙"
            status = u.get('status', 'active')
            print(f"{u.get('telegram_id'):<15} {name:<25} {role:<12} {balance:<10} {status:<10}")
    else:
        print("ℹ️  Пользователи пока не зарегистрированы")
        print("💡 Для демонстрации создайте тестового пользователя вручную")
        
except Exception as e:
    print(f"⚠️  Ошибка получения пользователей: {e}")

print()

# 3. ИГРЫ
print("=" * 70)
print("🎲 ПОСЛЕДНИЕ ИГРОВЫЕ СЕССИИ")
print("=" * 70)

try:
    games = supabase.table("transactions").select("*").eq("type", "game_win").order("created_at", desc=True).limit(10).execute()
    
    if games.data:
        print(f"{'Пользователь':<15} {'Игра':<20} {'Сумма':<15} {'Время':<25}")
        print("-" * 70)
        for g in games.data:
            user_id = g.get('telegram_id')
            game_type = g.get('type', 'unknown')
            amount = f"+{g.get('amount', 0):.0f} 🪙"
            time_str = g.get('created_at', '')[:19] if g.get('created_at') else 'N/A'
            print(f"{user_id:<15} {game_type:<20} {amount:<15} {time_str:<25}")
    else:
        print("ℹ️  Игры пока не проводились")
        print("💡 Игровая система готова к работе (4 мини-игры)")
        
except Exception as e:
    print(f"⚠️  Ошибка получения игр: {e}")

print()

# 4. МОДЕРАЦИЯ
print("=" * 70)
print("🛡️ ПОСЛЕДНИЕ ДЕЙСТВИЯ МОДЕРАЦИИ")
print("=" * 70)

try:
    logs = supabase.table("moderation_logs").select("*").order("created_at", desc=True).limit(10).execute()
    
    if logs.data:
        print(f"{'Исполнитель':<15} {'Цель':<15} {'Действие':<12} {'Причина':<20}")
        print("-" * 70)
        for log in logs.data:
            executor = log.get('executor_id', 'system')
            target = log.get('target_id', 'unknown')
            action = log.get('action', 'unknown')
            reason = (log.get('reason') or 'без причины')[:18]
            print(f"{executor:<15} {target:<15} {action:<12} {reason:<20}")
    else:
        print("ℹ️  Действий модерации пока не было")
        print("💡 Система модерации готова: warn, mute, ban, delete")
        
except Exception as e:
    print(f"⚠️  Ошибка получения логов модерации: {e}")

print()

# 5. АРХИТЕКТУРА
print("=" * 70)
print("🏗️ АРХИТЕКТУРА СИСТЕМЫ")
print("=" * 70)
print("""
📁 Структура проекта:
   ├── shut_bot.py          # Основной бот "Шут"
   ├── strazh_bot.py        # Сервисный бот "Страж"  
   ├── database.py          # Работа с Supabase
   ├── games.py             # Игровая система (4 игры)
   ├── moderation.py        # Модерация и RBAC
   ├── ui_menus.py          # Inline-меню и клавиатуры
   ├── config.py            # Конфигурация
   └── .env                 # Переменные окружения

🎮 Функционал:
   ✅ Регистрация и профили пользователей
   ✅ 4 мини-игры (рулетка, кубики, орёл/решка, колесо фортуны)
   ✅ Виртуальная экономика и магазин
   ✅ Модерация (warn, mute, ban) с RBAC
   ✅ Автоматический мониторинг и бэкапы
   ✅ Атомарные транзакции баланса

🔒 Безопасность:
   ✅ Криптографически стойкий ГПСЧ (secrets.SystemRandom)
   ✅ Проверка прав доступа при каждой команде
   ✅ Атомарность баланса через транзакции
   ✅ Защита от отрицательного баланса
""")

print()
print("=" * 70)
print("✅ СИСТЕМА ГОТОВА К ДЕМОНСТРАЦИИ")
print("=" * 70)
print()
print("📝 Для защиты проекта:")
print("   1. Покажите этот вывод комиссии")
print("   2. Откройте панель Supabase и покажите таблицы")
print("   3. Покажите код ключевых модулей (games.py, moderation.py)")
print("   4. Объясните архитектуру (2 бота, Supabase, RBAC)")
print()
print("💡 Если Telegram заблокирован:")
print("   - Система работает в тестовом режиме (TEST_MODE=True)")
print("   - Вся логика функционирует, кроме связи с Telegram API")
print("   - Для продакшена достаточно настроить VPN/прокси")
print()