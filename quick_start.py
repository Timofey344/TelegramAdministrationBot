#!/usr/bin/env python3
"""
Быстрый старт системы "Шут-Надзиратель"
Запускает оба бота и показывает статус
"""
import os
import sys
import asyncio
import time
from pathlib import Path

print("=" * 60)
print("🎭 СИСТЕМА 'ШУТ-НАДЗИРАТЕЛЬ' - ЗАПУСК")
print("=" * 60)
print(f"📁 Рабочая папка: {os.getcwd()}")
print(f"🐍 Python версия: {sys.version}")
print()

# Проверка .env
env_file = Path(".env")
if not env_file.exists():
    print("❌ ОШИБКА: Файл .env не найден!")
    print("📝 Создайте файл .env с необходимыми переменными")
    sys.exit(1)

print("✅ Файл .env найден")

# Проверка переменных
from dotenv import load_dotenv
load_dotenv()

test_mode = os.getenv("TEST_MODE", "False").lower() == "true"
print(f"🧪 Тестовый режим: {'ВКЛЮЧЁН' if test_mode else 'ВЫКЛЮЧЕН'}")

if not test_mode:
    if not os.getenv("SHUT_TOKEN"):
        print("⚠️  Предупреждение: SHUT_TOKEN не задан")
    if not os.getenv("SUPABASE_URL"):
        print("❌ ОШИБКА: SUPABASE_URL не задан!")
        sys.exit(1)

print()
print("=" * 60)
print("ЗАПУСК БОТОВ...")
print("=" * 60)
print()

# Запуск основного бота
print("📡 Запуск 'Шут' (основной бот)...")
try:
    import shut_bot
    print("✅ Модуль 'shut_bot' загружен")
except Exception as e:
    print(f"❌ Ошибка загрузки shut_bot: {e}")
    import traceback
    traceback.print_exc()

print()
print("💡 Для запуска в отдельных окнах используйте:")
print("   Окно 1: python shut_bot.py")
print("   Окно 2: python strazh_bot.py")
print()
print("📊 Для демонстрации статистики запустите:")
print("   python show_stats.py")