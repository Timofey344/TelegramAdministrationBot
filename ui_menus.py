"""
ui_menus.py
Генераторы Inline-клавиатур и кнопок навигации.
Использует InlineKeyboardBuilder из aiogram 3.x.
Все callback_data имеют единый префикс для удобной фильтрации в роутерах.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню: профиль, игры, магазин, модерация, настройки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="nav:profile"),
        InlineKeyboardButton(text="🎲 Игры", callback_data="nav:games")
    )
    builder.row(
        InlineKeyboardButton(text="🛒 Магазин", callback_data="nav:shop"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="nav:settings")
    )
    builder.row(InlineKeyboardButton(text="🛡️ Модерация", callback_data="nav:moderation"))
    return builder.as_markup()

def games_menu_kb() -> InlineKeyboardMarkup:
    """Меню выбора мини-игры."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔫 Русская рулетка", callback_data="game:roulette"))
    builder.row(InlineKeyboardButton(text="🎲 Кубики (vs Бот)", callback_data="game:dice"))
    builder.row(InlineKeyboardButton(text="🪙 Орёл или Решка", callback_data="game:coin"))
    builder.row(InlineKeyboardButton(text="🎡 Колесо фортуны", callback_data="game:wheel"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="nav:main"))
    return builder.as_markup()

def shop_menu_kb() -> InlineKeyboardMarkup:
    """Магазин: 3 позиции из ТЗ."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📌 Закреп сообщения (30 мин)", callback_data="shop:pin"))
    builder.row(InlineKeyboardButton(text="🔓 Снять мут", callback_data="shop:unmute"))
    builder.row(InlineKeyboardButton(text="📊 Расширенная аналитика", callback_data="shop:analytics"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="nav:main"))
    return builder.as_markup()

def moderation_menu_kb(target_id: int | None = None, msg_id: int | None = None) -> InlineKeyboardMarkup:
    """Панель модератора/админа. Если переданы target_id/msg_id — генерирует быстрые действия."""
    builder = InlineKeyboardBuilder()
    if target_id and msg_id:
        builder.row(
            InlineKeyboardButton(text="⚠️ Warn", callback_data=f"qmod:warn:{target_id}"),
            InlineKeyboardButton(text="🔇 1ч", callback_data=f"qmod:mute60:{target_id}"),
            InlineKeyboardButton(text="🚫 Бан", callback_data=f"qmod:ban:{target_id}")
        )
        builder.row(InlineKeyboardButton(text="🗑️ Удалить сообщение", callback_data=f"qmod:del:{msg_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="nav:main"))
    return builder.as_markup()

def settings_menu_kb() -> InlineKeyboardMarkup:
    """Меню настроек."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📖 Помощь и команды", url="https://t.me/your_help_link"))
    builder.row(InlineKeyboardButton(text="📜 Правила чата", callback_data="settings:rules"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="nav:main"))
    return builder.as_markup()

def confirm_kb(action_cb: str) -> InlineKeyboardMarkup:
    """Подтверждение критических действий (покупка, бан, ставка)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{action_cb}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
    )
    return builder.as_markup()