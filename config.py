import os
import logging
from typing import List
from dataclasses import dataclass, field
from dotenv import load_dotenv

# 1. Базовая настройка логирования (чтобы видеть ошибки до старта бота)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler()]
)

def setup_logging(level="INFO"):
    """Перенастраивает логирование согласно конфигам (добавляет файл system.log)."""
    # Удаляем старые хендлеры, чтобы не дублировать логи
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s",
        handlers=[
            logging.FileHandler("system.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logging.getLogger("aiogram").setLevel(logging.WARNING)

# Загружаем переменные окружения из .env
load_dotenv()

@dataclass
class AppConfig:
    """Контейнер настроек."""
    shut_token: str | None = field(default_factory=lambda: os.getenv("SHUT_TOKEN"))
    strazh_token: str | None = field(default_factory=lambda: os.getenv("STRAZH_TOKEN"))
    supabase_url: str | None = field(default_factory=lambda: os.getenv("SUPABASE_URL"))
    supabase_key: str | None = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    owner_ids: List[int] = field(default_factory=lambda: [
        int(x) for x in os.getenv("OWNER_IDS", "").split(",") if x.strip().isdigit()
    ])
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    use_proxy: bool = field(default_factory=lambda: os.getenv("USE_PROXY", "False").lower() == "true")
    proxy_url: str | None = field(default_factory=lambda: os.getenv("PROXY_URL"))
    proxy_verify_ssl: bool = field(default_factory=lambda: os.getenv("PROXY_VERIFY_SSL", "True").lower() == "true")
    test_mode: bool = field(default_factory=lambda: os.getenv("TEST_MODE", "False").lower() == "true")

    def validate(self) -> None:
        """Проверка обязательных параметров."""
        if not self.test_mode and (not self.shut_token or not self.strazh_token):
            raise EnvironmentError("❌ В режиме не-теста обязательны SHUT_TOKEN и STRAZH_TOKEN")
        if not self.supabase_url or not self.supabase_key:
            raise EnvironmentError(" Обязательны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY")
        if not self.owner_ids:
            raise EnvironmentError("❌ Обязателен хотя бы один OWNER_IDS")
        logging.getLogger(__name__).info("✅ Конфигурация валидна.")