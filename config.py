import os
from typing import Dict, List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =========================
# LLM settings
# =========================

# Возможные значения: gigachat, fallback
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fallback").strip().lower()

# GigaChat credentials
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "").strip()

# Модель и параметры генерации
LLM_MODEL = os.getenv("LLM_MODEL", "GigaChat-3-Ultra").strip()

try:
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
except ValueError:
    LLM_TEMPERATURE = 0.0

GIGACHAT_VERIFY_SSL = os.getenv("GIGACHAT_VERIFY_SSL", "false").strip().lower() != "false"

# Маппинг операций
OPERATION_MAP: Dict[str, str] = {
    "приход": "receipt",
    "расход": "consume",
    "списание": "writeoff",
    "возврат": "return",
    "корректировка": "correction"
}

# Коэффициенты приведения к базовым единицам
UNIT_CONVERSIONS: Dict[str, float] = {
    "мл": 0.001,
    "л": 1.0,
    "г": 0.001,
    "кг": 1.0,
    "шт": 1.0,
    "пар": 1.0,
    "уп": 1.0, # Умножается на pack_size внутри логики
    "канистра": 1.0, # Умножается на объем внутри логики
    "канистры": 1.0
}

# Маппинг названий товаров к SKU (для M8)
NAME_TO_SKU: Dict[str, str] = {
    "тапочек одноразовых": "CONS-051",
    "тапочки одноразовые": "CONS-051",
    "масло базовое": "OIL-001",
    "масло ароматическое": "OIL-002",
    "скраб": "SCRB-020",
    "маска": "WRAP-030",
    "шапочки": "CONS-052"
}

# Локации
KNOWN_LOCATIONS: List[str] = ["MS-01", "MS-02", "СОЧИ", "КРАСНАЯ ПОЛЯНА"]

# Параметры прогнозирования
FORECAST_CONFIG = {
    "confidence_threshold": 0.6,  # Порог, ниже которого "требуется уточнение"
    "outlier_multiplier": 1.8,    # Множитель для определения выброса (от медианы)
    "min_weeks_for_trend": 6      # Минимум недель для применения тренда
}

# Интенты для Части 3
INTENTS = {
    "forecast_purchase": ["закупить", "закупка", "объем закупки", "сколько купить"],
    "reorder_list": ["заказать", "нужно заказать", "что заказать"],
    "budget": ["бюджет", "стоимость", "сколько будет стоить", "лимит"],
    "deficit_risk": ["закончится", "дефицит", "риск дефицита", "хватит ли"],
    "expiry_risk": ["сгорят", "срок годности", "испортится", "партии"],
    "price_dynamics": ["подорожало", "цена", "динамика цен", "выросла цена"],
    "unknown": []
}

PERIOD_MAP = {
    "месяц": 30,
    "два месяца": 60,
    "три месяца": 90,
    "квартал": 90,
    "полгода": 180,
    "14 дней": 14,
    "ближайшие 14 дней": 14
}