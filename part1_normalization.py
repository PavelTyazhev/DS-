import re
from typing import Optional, List, Dict, Any
import config

MONTHS_RU = {
    "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
    "мая": "05", "июня": "06", "июля": "07", "августа": "08",
    "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12"
}

def _parse_date(text: str) -> Optional[str]:
    text_clean = text.replace("г.", "").replace("г", "").strip()
    
    match = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text_clean)
    if match: return match.group(0)
        
    match = re.search(r'\b(\d{2})\.(\d{2})\.(\d{2,4})\b', text_clean)
    if match:
        d, m, y = match.groups()
        y = f"20{y}" if len(y) == 2 else y
        return f"{y}-{m}-{d}"

    match = re.search(r'\b(\d{2})/(\d{2})/(\d{2})\b', text_clean)
    if match:
        d, m, y = match.groups()
        return f"20{y}-{m}-{d}"

    for month_ru, month_num in MONTHS_RU.items():
        pattern = rf'\b(\d{{1,2}})\s+{month_ru}\s+(\d{{4}})\b'
        match = re.search(pattern, text_clean.lower())
        if match:
            d, y = match.groups()
            return f"{y}-{month_num}-{int(d):02d}"
            
    return None

def _parse_operation(text: str) -> Optional[str]:
    text_lower = text.lower()
    for ru_word, en_op in config.OPERATION_MAP.items():
        if re.search(rf'\b{ru_word}\b', text_lower): return en_op
    if "cons" in text_lower or "consume" in text_lower: return "consume"
    if "receipt" in text_lower: return "receipt"
    return None

def _parse_sku(text: str, catalog: list) -> Optional[str]:
    match = re.search(r'\b([A-Z]+-\d{2,3})\b', text.upper())
    if match:
        sku = match.group(1)
        if any(item["sku"] == sku for item in catalog): return sku
            
    match = re.search(r'\b([A-Z]+)\s*(\d{2,3})\b', text.upper())
    if match:
        sku = f"{match.group(1)}-{match.group(2)}"
        if any(item["sku"] == sku for item in catalog): return sku
            
    text_lower = text.lower()
    for name_part, sku in config.NAME_TO_SKU.items():
        if name_part in text_lower: return sku
    return None

def _parse_qty_and_unit(text: str, sku: Optional[str], catalog: list) -> tuple[Optional[float], Optional[str]]:
    text_lower = text.lower().replace(",", ".")
    
    base_unit = None
    if sku:
        for item in catalog:
            if item["sku"] == sku:
                base_unit = item["unit"]
                break

    # Ищем количество ТОЛЬКО после слова операции, чтобы не захватить даты
    op_match = re.search(r'(приход|расход|списание|возврат|корректировка)', text_lower)
    search_text = text_lower[op_match.end():] if op_match else text_lower

    # Паттерн 1: "X канистр/уп по Y л/пар"
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:канистр\w*|уп\.?|упаков\w*)\s*по\s*(\d+(?:\.\d+)?)\s*(л|мл|кг|г|шт|пар)', search_text)
    if match:
        count, volume, unit_raw = float(match.group(1)), float(match.group(2)), match.group(3)
        return count * volume, base_unit if base_unit else unit_raw

    # Паттерн 2: "X л/кг/пар/шт/мл"
    match = re.search(r'([-−]?\d+(?:\.\d+)?)\s*(л|мл|кг|г|шт|пар)', search_text)
    if match:
        qty = float(match.group(1).replace("−", "-"))
        unit_raw = match.group(2)
        
        if unit_raw == "мл" and base_unit == "л": return qty / 1000.0, base_unit
        if unit_raw == "г" and base_unit == "кг": return qty / 1000.0, base_unit
            
        return qty, base_unit if base_unit else unit_raw

    return None, None

def _parse_location(text: str) -> Optional[str]:
    text_upper = text.upper()
    if "КРАСНАЯ ПОЛЯНА" in text_upper: return "Красная Поляна"
    if "СОЧИ" in text_upper: return "Сочи"
    for loc in ["MS-01", "MS-02"]:
        if loc in text_upper: return loc
    return None

def _parse_batch(text: str) -> Optional[str]:
    match = re.search(r'(?:парт\.?|batch)\s*[:\-]?\s*([A-Z0-9\-]+)', text, re.IGNORECASE)
    if match: return match.group(1)
    match = re.search(r'\b(B-[A-Z0-9\-]+)\b', text.upper())
    if match: return match.group(1)
    return None

def _parse_doc_no(text: str) -> Optional[str]:
    match = re.search(r'\b([А-Я]{2,}-\d+)\b', text.upper())
    if match: return match.group(1)
    return None

def normalize_movement(text: str, catalog: list) -> dict:
    date = _parse_date(text)
    operation = _parse_operation(text)
    sku = _parse_sku(text, catalog)
    qty, unit = _parse_qty_and_unit(text, sku, catalog)
    location = _parse_location(text)
    batch = _parse_batch(text)
    doc_no = _parse_doc_no(text)
    
    if operation == "correction" and qty is not None and "−" in text:
        qty = -abs(qty)

    return {
        "date": date, "sku": sku, "location": location,
        "operation": operation, "qty": qty, "unit": unit,
        "batch": batch, "doc_no": doc_no
    }