import json
import re
from typing import Any, Dict, List, Optional, Tuple

import config
from llm_client import ask_llm
from part2_forecast import forecast_demand


# =========================
# Fallback extraction
# =========================

def _extract_period(question: str) -> Optional[int]:
    q_lower = question.lower()

    match = re.search(r"(\d+)\s*дн", q_lower)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    for period_str, days in config.PERIOD_MAP.items():
        if period_str in q_lower:
            return days

    return None


def _extract_budget(question: str) -> Optional[float]:
    q_lower = question.lower()

    if "200 тысяч" in q_lower:
        return 200000.0

    q_norm = (
        q_lower
        .replace("тысяч", "000")
        .replace("руб", "")
        .replace(" ", "")
    )

    match = re.search(r"(\d{3,})\s*(?:000)?", q_norm)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    return None


def _extract_location(question: str) -> Optional[str]:
    q_upper = question.upper()

    for loc in config.KNOWN_LOCATIONS:
        if loc.upper() in q_upper:
            if loc.upper() == "СОЧИ":
                return "Сочи"
            if loc.upper() == "КРАСНАЯ ПОЛЯНА":
                return "Красная Поляна"
            return loc

    return None


def _extract_sku(question: str, catalog: List[Dict[str, Any]]) -> Optional[str]:
    q_lower = question.lower()
    q_upper = question.upper()

    # 1) Прямое вхождение SKU
    match = re.search(r"\b([A-Z]+[-\s]?[0-9]{2,3})\b", q_upper)
    if match:
        sku_raw = match.group(1).replace(" ", "-").replace("--", "-")

        if "-" not in sku_raw:
            sku_raw = re.sub(r"([A-Z]+)(\d+)", r"\1-\2", sku_raw)

        for item in catalog:
            if item.get("sku") == sku_raw:
                return sku_raw

    # 2) Поиск по ключевым словам
    keyword_map = [
        ("ароматическ", "OIL-002"),
        ("лаванда", "OIL-002"),
        ("базов", "OIL-001"),
        ("миндаль", "OIL-001"),
        ("скраб", "SCRB-020"),
        ("альгинатн", "WRAP-030"),
        ("обёртыван", "WRAP-030"),
        ("обертыван", "WRAP-030"),
        ("маска", "WRAP-030"),
        ("тапочк", "CONS-051"),
        ("шапочк", "CONS-052"),
        ("масл", "OIL-001"),
    ]

    for keyword, sku in keyword_map:
        if keyword in q_lower:
            for item in catalog:
                if item.get("sku") == sku:
                    return sku

    return None


def _classify_intent(question: str) -> Tuple[str, float]:
    q_lower = question.lower()
    scores: Dict[str, int] = {}

    for intent, keywords in config.INTENTS.items():
        if intent == "unknown":
            continue

        score = sum(1 for kw in keywords if kw in q_lower)
        if score > 0:
            scores[intent] = score

    if not scores:
        return "unknown", 0.0

    sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_intent, best_score = sorted_intents[0]

    if len(sorted_intents) > 1:
        second_score = sorted_intents[1][1]
        if best_score == second_score:
            return "unknown", 0.3

    confidence = min(1.0, 0.5 + best_score * 0.2)
    return best_intent, confidence


# =========================
# LLM parsing
# =========================

def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        pass

    try:
        return int(float(value))
    except (TypeError, ValueError):
        pass

    match = re.search(r"\d+", str(value))
    if match:
        try:
            return int(match.group(0))
        except ValueError:
            return default

    return default


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    match = re.search(r"\d+(?:[\.,]\d+)?", str(value))
    if match:
        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            return default

    return default


def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    return json.loads(text)


def _llm_parse_question(question: str, catalog: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    provider = getattr(config, "LLM_PROVIDER", "fallback").strip().lower()
    credentials = getattr(config, "GIGACHAT_CREDENTIALS", "")

    if provider != "gigachat" or not credentials:
        return None

    allowed_intents = [
        "forecast_purchase",
        "reorder_list",
        "budget",
        "deficit_risk",
        "expiry_risk",
        "price_dynamics",
        "unknown"
    ]

    skus = [item.get("sku") for item in catalog if item.get("sku")]

    system_prompt = (
        "Ты — модуль извлечения параметров запроса для системы планирования закупок.\n"
        "Твоя задача — определить только намерение пользователя и сущности.\n"
        "Запрещено вычислять количество товара, стоимость, прогноз, бюджет, если они явно не указаны пользователем.\n"
        "Верни только один валидный JSON-объект без пояснений, без markdown и без лишнего текста."
    )

    user_prompt = f"""
Разбери вопрос пользователя.

Вопрос:
{question}

Допустимые интенты:
{', '.join(allowed_intents)}

Известные SKU:
{', '.join(skus)}

Верни JSON строго в таком формате:
{{
  "intent": "один из допустимых интентов",
  "sku": "SKU или null",
  "period_days": число дней или null,
  "budget_limit": число в рублях или null,
  "location": "локация или null",
  "confidence": число от 0.0 до 1.0
}}

Правила:
1. Если вопрос вне домена закупок, склада, цен, дефицита или сроков годности, верни intent="unknown".
2. Если сущность не указана явно, верни для неё null.
3. Не выдумывай значения, которых нет в вопросе.
4. Периоды: месяц=30, квартал=90, три месяца=90, полгода=180, 14 дней=14.
5. Если вопрос сформулирован недостаточно конкретно, поставь confidence не выше 0.4.
""".strip()

    raw_response = ask_llm(user_prompt, system_prompt)
    if not raw_response:
        return None

    try:
        parsed = _extract_json_payload(raw_response)

        intent = str(parsed.get("intent", "unknown")).strip().lower()
        if intent not in allowed_intents:
            intent = "unknown"

        sku = parsed.get("sku")
        if sku not in skus:
            sku = None

        period_days = _to_int(parsed.get("period_days"))
        budget_limit = _to_float(parsed.get("budget_limit"))

        location = parsed.get("location")
        if location is not None:
            location = str(location).strip() or None

        confidence = _to_float(parsed.get("confidence"), default=0.75)
        if confidence is None:
            confidence = 0.75

        confidence = max(0.0, min(1.0, confidence))

        return {
            "intent": intent,
            "sku": sku,
            "period_days": period_days,
            "budget_limit": budget_limit,
            "location": location,
            "confidence": confidence
        }

    except Exception:
        return None


# =========================
# Main entrypoint
# =========================

def answer_question(question: str, context: Dict[str, Any]) -> Tuple[Dict[str, Any], float, str]:
    """
    Разбирает вопрос пользователя.

    Сначала пытается использовать GigaChat.
    Если LLM недоступна или ответ не проходит валидацию, использует fallback.

    Важно:
    - LLM не считает прогноз, объём закупки и стоимость.
    - Все числовые расчёты выполняются детерминированно через forecast_demand.
    """
    catalog = context.get("catalog", [])
    history = context.get("history", {})

    fallback_intent, fallback_confidence = _classify_intent(question)

    llm_parsed = _llm_parse_question(question, catalog)

    used_llm = False

    if (
        llm_parsed is not None
        and llm_parsed.get("intent") != "unknown"
        and llm_parsed.get("confidence", 0.0) >= 0.6
    ):
        intent = llm_parsed["intent"]
        confidence = llm_parsed["confidence"]
        sku = llm_parsed.get("sku") or _extract_sku(question, catalog)
        period = llm_parsed.get("period_days") or _extract_period(question)
        budget = llm_parsed.get("budget_limit") or _extract_budget(question)
        location = llm_parsed.get("location") or _extract_location(question)
        used_llm = True
    else:
        intent = fallback_intent
        confidence = fallback_confidence
        sku = _extract_sku(question, catalog)
        period = _extract_period(question)
        budget = _extract_budget(question)
        location = _extract_location(question)

    parsed_params: Dict[str, Any] = {
        "intent": intent,
        "sku": sku,
        "period_days": period,
        "budget_limit": budget,
        "location": location,
        "source": "gigachat" if used_llm else "fallback"
    }

    # Вне домена или низкая уверенность
    if intent == "unknown" or confidence < 0.5:
        return (
            parsed_params,
            confidence,
            "Не удалось точно определить запрос. Пожалуйста, уточните товар, период, локацию или действие."
        )

    response_text = ""

    # Прогноз закупки конкретного товара
    if intent == "forecast_purchase":
        if not sku:
            return (
                parsed_params,
                min(confidence, 0.4),
                "Уточните, какой именно товар вы хотите закупить?"
            )

        if not period:
            return (
                parsed_params,
                min(confidence, 0.4),
                "Уточните период планирования: например, 30 дней, квартал или полгода."
            )

        cat_item = next((item for item in catalog if item.get("sku") == sku), None)

        if not cat_item:
            return (
                parsed_params,
                confidence,
                "Товар не найден в справочнике."
            )

        forecast = forecast_demand(history, sku, period, cat_item)
        parsed_params["forecast_result"] = forecast

        response_text = (
            f"Для товара {cat_item.get('name')} ({sku}) на {period} дней:\n"
            f"- Прогнозный расход: {forecast['forecast_demand']} {cat_item.get('unit')}\n"
            f"- Рекомендуемый объем закупки: {forecast['recommended_qty']} {cat_item.get('unit')}\n"
            f"- Ориентировочная стоимость: {forecast['estimated_cost']} руб.\n"
            f"- Уверенность прогноза: {forecast['confidence']}\n\n"
            f"Обоснование: {forecast['explanation']}"
        )

        if budget is not None and forecast["estimated_cost"] > budget:
            response_text += f"\n\nВНИМАНИЕ: Стоимость превышает указанный лимит бюджета ({budget} руб.)."

        return parsed_params, confidence, response_text

    # Список на заказ
    if intent == "reorder_list":
        if not period:
            return (
                parsed_params,
                min(confidence, 0.4),
                "Уточните период, на который нужно сформировать список заказа: например, 14 дней, месяц или квартал."
            )

        lines = [f"Список товаров для заказа на {period} дней:"]

        has_recommendations = False

        for item in catalog:
            forecast_result = forecast_demand(history, item.get("sku"), period, item)

            if forecast_result["recommended_qty"] > 0:
                has_recommendations = True
                lines.append(
                    f"- {item.get('name')} ({item.get('sku')}): "
                    f"заказать {forecast_result['recommended_qty']} {item.get('unit')}, "
                    f"стоимость {forecast_result['estimated_cost']} руб."
                )

        if not has_recommendations:
            lines.append("На выбранный период нет товаров, требующих закупки.")

        return parsed_params, confidence, "\n".join(lines)

    # Бюджет
    if intent == "budget":
        if not period:
            return (
                parsed_params,
                min(confidence, 0.4),
                "Уточните период для расчёта бюджета: месяц, квартал, полгода и т.д."
            )

        total_cost = 0.0
        lines = [f"Бюджет закупок на {period} дней:"]

        for item in catalog:
            forecast_result = forecast_demand(history, item.get("sku"), period, item)
            total_cost += forecast_result["estimated_cost"]

        lines.append(f"Итого ориентировочно: {round(total_cost, 2)} руб.")

        if budget is not None and total_cost > budget:
            lines.append(f"ВНИМАНИЕ: Итоговая сумма превышает лимит {budget} руб.")

        return parsed_params, confidence, "\n".join(lines)

    # Риск дефицита
    if intent == "deficit_risk":
        lines = ["Товары с риском дефицита:"]

        has_risk = False

        for item in catalog:
            lead_time = item.get("lead_time_days", 7)
            forecast_result = forecast_demand(history, item.get("sku"), lead_time, item)

            available_stock = forecast_result["current_stock"] + forecast_result["incoming_qty"]

            if available_stock < forecast_result["forecast_demand"]:
                has_risk = True
                lines.append(
                    f"- {item.get('name')} ({item.get('sku')}): "
                    f"доступно {available_stock}, "
                    f"ориентировочно закончится через {forecast_result['stockout_date']}"
                )

        if not has_risk:
            lines.append("Явного риска дефицита по текущим данным не найдено.")

        if location:
            lines.append(f"Локация фильтрации: {location}. В текущем MVP расчёт ведётся по общему складу.")

        return parsed_params, confidence, "\n".join(lines)

    # Риск истечения срока годности
    if intent == "expiry_risk":
        return (
            parsed_params,
            confidence,
            "Для анализа рисков истечения срока годности требуются данные о партиях и сроках годности. "
            "В текущем наборе данных эти поля отсутствуют."
        )

    # Динамика цен
    if intent == "price_dynamics":
        return (
            parsed_params,
            confidence,
            "Динамика цен требует исторических данных о ценах поставщика. "
            "В текущем наборе данных есть только актуальные цены."
        )

    return (
        parsed_params,
        confidence,
        "Функция для данного запроса находится в разработке."
    )