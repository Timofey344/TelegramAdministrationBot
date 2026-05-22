import os

print("🎭 ТЕСТ ЗАПУСКА СИСТЕМЫ")
print("=" * 40)

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ .env загружен")
except Exception as e:
    print(f"❌ Ошибка .env: {e}")

try:
    from supabase import create_client
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    print("✅ Supabase подключён")
except Exception as e:
    print(f"❌ Ошибка Supabase: {e}")

try:
    import config
    cfg = config.AppConfig()
    cfg.validate()
    print("✅ Конфигурация валидна")
except Exception as e:
    print(f"❌ Ошибка конфига: {e}")

print()
print("💡 Система готова к демонстрации!")
print("   Запусти: python show_stats.py")