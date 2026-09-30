import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from part1_normalization import normalize_movement
from part2_forecast import forecast_demand
from part3_qa import answer_question

@pytest.fixture
def catalog():
    return [
        {"sku":"OIL-001","name":"Массажное масло базовое(миндаль)","unit":"л","pack_size":5,"min_order_qty":10,"safety_stock_days":14,"lead_time_days":7,"price":1259.05},
        {"sku":"CONS-051","name":"Тапочки одноразовые","unit":"пар","pack_size":50,"min_order_qty":100,"safety_stock_days":10,"lead_time_days":5,"price":45.30},
        {"sku":"CONS-052","name":"Шапочки одноразовые","unit":"шт","pack_size":100,"min_order_qty":200,"safety_stock_days":10,"lead_time_days":5,"price":9.70}
    ]

@pytest.fixture
def history():
    return {
        "as_of": "2026-09-15",
        "weekly_consumption": {"OIL-001": [8.4, 9.1, 8.8, 9.6, 10.2, 9.4, 11.0, 10.6, 12.3, 11.8, 12.9, 13.4]},
        "current_stock": {"OIL-001": 50.4},
        "incoming_qty": {"OIL-001": 20.0}
    }

class TestPart1Normalization:
    def test_date_parsing_iso(self, catalog):
        res = normalize_movement("2026-03-08; MS-01; CONS-051; расход; 48 пар", catalog)
        assert res["date"] == "2026-03-08"

    def test_qty_conversion_ml_to_l(self, catalog):
        res = normalize_movement("1 марта 2026 MS-01 расход oil 001 — 450 мл", catalog)
        assert res["qty"] == 0.45
        assert res["unit"] == "л"

    def test_qty_conversion_packs_to_base(self, catalog):
        res = normalize_movement("Приход тапочек одноразовых, 4 уп. по 50 пар, Красная Поляна", catalog)
        assert res["qty"] == 200.0
        assert res["unit"] == "пар"
        assert res["sku"] == "CONS-051"

    def test_negative_correction(self, catalog):
        res = normalize_movement("Корректировка 15.03.2026, MS-02, CONS-052: −120 шт", catalog)
        assert res["operation"] == "correction"
        assert res["qty"] == -120.0

class TestPart2Forecast:
    def test_rounding_to_pack_size(self, history, catalog):
        cat_item = next(item for item in catalog if item["sku"] == "OIL-001")
        res = forecast_demand(history, "OIL-001", 30, cat_item)
        assert res["recommended_qty"] % 5 == 0
        assert res["recommended_qty"] >= 10

    def test_confidence_range(self, history, catalog):
        cat_item = next(item for item in catalog if item["sku"] == "OIL-001")
        res = forecast_demand(history, "OIL-001", 30, cat_item)
        assert 0.0 <= res["confidence"] <= 1.0

    def test_deterministic_calculation(self, history, catalog):
        cat_item = next(item for item in catalog if item["sku"] == "OIL-001")
        res1 = forecast_demand(history, "OIL-001", 30, cat_item)
        res2 = forecast_demand(history, "OIL-001", 30, cat_item)
        assert res1["forecast_demand"] == res2["forecast_demand"]

class TestPart3QA:
    def test_intent_extraction(self, history, catalog):
        context = {"history": history, "catalog": catalog}
        params, conf, text = answer_question("Сколько масла закупить на три месяца?", context)
        # Интент должен быть forecast_purchase (от LLM или fallback)
        assert params["intent"] == "forecast_purchase"
        
    def test_unknown_domain(self, history, catalog):
        context = {"history": history, "catalog": catalog}
        params, conf, text = answer_question("Какая погода в Сочи на выходных?", context)
        assert params["intent"] == "unknown"