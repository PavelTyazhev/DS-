import math
from typing import Dict, Any, List, Optional
import config

def _clean_history(history: List[Optional[float]]) -> List[float]:
    """Обрабатывает пропуски (null) линейной интерполяцией."""
    cleaned = history.copy()
    for i in range(len(cleaned)):
        if cleaned[i] is None:
            prev_val = next((cleaned[j] for j in range(i-1, -1, -1) if cleaned[j] is not None), None)
            next_val = next((cleaned[j] for j in range(i+1, len(cleaned)) if cleaned[j] is not None), None)
            if prev_val is not None and next_val is not None:
                cleaned[i] = (prev_val + next_val) / 2.0
            elif prev_val is not None:
                cleaned[i] = prev_val
            elif next_val is not None:
                cleaned[i] = next_val
            else:
                cleaned[i] = 0.0
    return [float(x) for x in cleaned]

def _handle_outliers(data: List[float]) -> List[float]:
    """
    Обрабатывает выбросы. 
    Если скачок поддерживается последующими неделями (как в SCRB-020),
    мы считаем это новым уровнем спроса, а не выбросом.
    Для единичных пиков применяем сглаживание медианой.
    """
    if len(data) < 4:
        return data
        
    median_val = sorted(data)[len(data)//2]
    threshold = median_val * config.FORECAST_CONFIG["outlier_multiplier"]
    
    # Проверяем, является ли рост устойчивым (последние 3 недели > threshold)
    recent_high = sum(1 for x in data[-3:] if x > threshold)
    if recent_high >= 2:
        # Это новый уровень спроса (тренд), оставляем как есть
        return data
        
    # Иначе сглаживаем единичные выбросы
    smoothed = []
    for i, val in enumerate(data):
        if val > threshold:
            # Заменяем средним соседей
            neighbors = [data[j] for j in range(max(0, i-1), min(len(data), i+2)) if j != i]
            smoothed.append(sum(neighbors) / len(neighbors) if neighbors else median_val)
        else:
            smoothed.append(val)
    return smoothed

def _calculate_trend(data: List[float]) -> float:
    """Рассчитывает линейный тренд (наклон) методом наименьших квадратов."""
    n = len(data)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(data) / n
    num = sum((i - x_mean) * (data[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0

def _calculate_confidence(data: List[float], trend: float) -> float:
    """
    Рассчитывает уверенность прогноза (0.0 - 1.0).
    Снижается при короткой истории и высокой волатильности (CV).
    """
    n = len(data)
    if n == 0:
        return 0.0
        
    mean_val = sum(data) / n
    if mean_val == 0:
        return 0.5
        
    variance = sum((x - mean_val) ** 2 for x in data) / n
    std_dev = math.sqrt(variance)
    cv = std_dev / mean_val  # Коэффициент вариации
    
    # Базовая уверенность зависит от длины истории (максимум при >= 12 неделях)
    length_score = min(1.0, n / 12.0)
    
    # Штраф за волатильность (CV > 0.3 сильно снижает уверенность)
    vol_score = max(0.0, 1.0 - (cv * 2.0))
    
    confidence = (length_score * 0.4) + (vol_score * 0.6)
    return round(max(0.1, min(1.0, confidence)), 2)


def forecast_demand(history: dict, sku: str, horizon_days: int, params: dict) -> dict:
    """
    Рассчитывает прогноз потребности и рекомендацию по закупке.
    
    Args:
        history: Словарь с историей потребления, остатками и поставками.
        sku: Артикул товара.
        horizon_days: Горизонт планирования в днях.
        params: Дополнительные параметры (например, из каталога).
        
    Returns:
        Словарь с результатами расчета.
    """
    weekly_data = history.get("weekly_consumption", {}).get(sku, [])
    current_stock = history.get("current_stock", {}).get(sku, 0.0)
    incoming_qty = history.get("incoming_qty", {}).get(sku, 0.0)
    
    safety_stock_days = params.get("safety_stock_days", 14)
    lead_time_days = params.get("lead_time_days", 7)
    pack_size = params.get("pack_size", 1)
    min_order_qty = params.get("min_order_qty", 1)
    price = params.get("price", 0.0)
    
    # 1. Очистка и обработка данных
    cleaned_data = _clean_history(weekly_data)
    processed_data = _handle_outliers(cleaned_data)
    
    # 2. Расчет среднего дневного потребления
    # Используем последние N недель с учетом тренда
    if len(processed_data) >= config.FORECAST_CONFIG["min_weeks_for_trend"]:
        trend = _calculate_trend(processed_data)
        # Прогноз на следующую неделю с учетом тренда
        # Берем среднее за последние 4 недели + половину тренда для стабилизации
        recent_avg = sum(processed_data[-4:]) / 4.0
        forecast_weekly = recent_avg + (trend * 0.5)
    else:
        forecast_weekly = sum(processed_data) / len(processed_data) if processed_data else 0.0
        trend = 0.0
        
    avg_daily_consumption = max(0.0, forecast_weekly / 7.0)
    
    # 3. Основные метрики
    forecast_demand_val = avg_daily_consumption * horizon_days
    safety_stock = avg_daily_consumption * safety_stock_days
    reorder_point = (avg_daily_consumption * lead_time_days) + safety_stock
    
    # 4. Рекомендуемый объем
    net_requirement = forecast_demand_val + safety_stock - current_stock - incoming_qty
    recommended_qty = max(0.0, net_requirement)
    
    # Округление вверх до кратности упаковки и минимальной партии
    if recommended_qty > 0:
        recommended_qty = max(recommended_qty, min_order_qty)
        recommended_qty = math.ceil(recommended_qty / pack_size) * pack_size
        
    estimated_cost = recommended_qty * price
    
    # 5. Дата дефицита (через сколько дней закончится)
    stockout_date = None
    if avg_daily_consumption > 0:
        days_until_stockout = (current_stock + incoming_qty) / avg_daily_consumption
        stockout_date = f"{days_until_stockout:.1f} дней"
        
    # 6. Уверенность
    confidence = _calculate_confidence(processed_data, trend)
    
    # 7. Объяснение
    explanation = (
        f"Расчет для {sku} на {horizon_days} дней. "
        f"Средний дневной расход: {avg_daily_consumption:.2f} (учтен тренд: {'да' if trend > 0 else 'нет'}). "
        f"Прогнозная потребность: {forecast_demand_val:.2f}. "
        f"Текущий остаток: {current_stock}, в пути: {incoming_qty}. "
        f"Страховой запас ({safety_stock_days} дн.): {safety_stock:.2f}. "
        f"Рекомендуемый объем округлен до кратности упаковки ({pack_size}) и мин. заказа ({min_order_qty})."
    )
    
    if confidence < config.FORECAST_CONFIG["confidence_threshold"]:
        explanation += " ВНИМАНИЕ: низкая уверенность прогноза, требуется уточнение."
        
    return {
        "avg_daily_consumption": round(avg_daily_consumption, 4),
        "forecast_demand": round(forecast_demand_val, 2),
        "current_stock": current_stock,
        "incoming_qty": incoming_qty,
        "safety_stock": round(safety_stock, 2),
        "reorder_point": round(reorder_point, 2),
        "recommended_qty": recommended_qty,
        "estimated_cost": round(estimated_cost, 2),
        "stockout_date": stockout_date,
        "confidence": confidence,
        "explanation": explanation
    }