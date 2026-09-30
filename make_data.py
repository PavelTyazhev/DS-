import json
from pathlib import Path


CATALOG = [
    {
        "sku": "OIL-001",
        "name": "Массажное масло базовое(миндаль)",
        "unit": "л",
        "pack_size": 5,
        "min_order_qty": 10,
        "safety_stock_days": 14,
        "lead_time_days": 7,
        "price": 1259.05
    },
    {
        "sku": "OIL-002",
        "name": "Массажное масло ароматическое(лаванда)",
        "unit": "л",
        "pack_size": 1,
        "min_order_qty": 5,
        "safety_stock_days": 14,
        "lead_time_days": 7,
        "price": 3223.40
    },
    {
        "sku": "SCRB-020",
        "name": "Скраб для тела кофейный",
        "unit": "кг",
        "pack_size": 1,
        "min_order_qty": 5,
        "safety_stock_days": 14,
        "lead_time_days": 10,
        "price": 1789.50
    },
    {
        "sku": "WRAP-030",
        "name": "Альгинатная маска для обёртывания",
        "unit": "кг",
        "pack_size": 1,
        "min_order_qty": 5,
        "safety_stock_days": 14,
        "lead_time_days": 14,
        "price": 2437.00
    },
    {
        "sku": "CONS-051",
        "name": "Тапочки одноразовые",
        "unit": "пар",
        "pack_size": 50,
        "min_order_qty": 100,
        "safety_stock_days": 10,
        "lead_time_days": 5,
        "price": 45.30
    },
    {
        "sku": "CONS-052",
        "name": "Шапочки одноразовые",
        "unit": "шт",
        "pack_size": 100,
        "min_order_qty": 200,
        "safety_stock_days": 10,
        "lead_time_days": 5,
        "price": 9.70
    }
]


DATASET = {
    "movements": [
        {
            "id": "M1",
            "text": "05.03.2026 MS-01 приход OIL-001, 2 канистры по 5 л, НК-345"
        },
        {
            "id": "M2",
            "text": "1 марта 2026 MS-01 расход oil 001 — 450 мл, B-OIL-001-012"
        },
        {
            "id": "M3",
            "text": "03/06/26 Сочи списание SCRB-020 1,2 кг, истёк срок"
        },
        {
            "id": "M4",
            "text": "07.03.26 ms-02 WRAP030 расход 3,5кг, парт.B-WRAP-030-004"
        },
        {
            "id": "M5",
            "text": "Возврат 12 марта 2026 г.: OIL-002, 2 л, брак упаковки"
        },
        {
            "id": "M6",
            "text": "2026-03-08; MS-01; CONS-051; расход; 48 пар"
        },
        {
            "id": "M7",
            "text": "Корректировка 15.03.2026, MS-02, CONS-052: −120 шт"
        },
        {
            "id": "M8",
            "text": "Приход тапочек одноразовых, 4 уп. по 50 пар, Красная Поляна"
        }
    ],
    "history": {
        "as_of": "2026-09-15",
        "weekly_consumption": {
            "OIL-001": [8.4, 9.1, 8.8, 9.6, 10.2, 9.4, 11.0, 10.6, 12.3, 11.8, 12.9, 13.4],
            "SCRB-020": [3.1, 2.9, 3.4, 3.0, 3.3, 3.2, 3.5, 3.1, 6.8, 7.4, 7.1, 7.6],
            "WRAP-030": [6.2, 5.8, 6.5, 6.0, None, 6.3, 6.1, 6.4, 6.0, 6.6, 6.2, 6.9]
        },
        "current_stock": {
            "OIL-001": 50.4,
            "SCRB-020": 9.4,
            "WRAP-030": 29.6
        },
        "incoming_qty": {
            "OIL-001": 20.0,
            "SCRB-020": 0.0,
            "WRAP-030": 30.0
        }
    },
    "questions": [
        "Сколько масла закупить на три месяца и сколько это будет стоить?",
        "Что нужно заказать в ближайшие 14 дней?",
        "Какой бюджет закупок на квартал?",
        "Что закончится до следующей поставки в Сочи?",
        "Какие партии сгорят в этом месяце?",
        "Насколько подорожало ароматическое масло у поставщика?",
        "Сколько альгинатной маски осталось в Красной Поляне?",
        "Посчитай закупку скраба на полгода при лимите 200 тысяч",
        "Почему план закупок вырос по сравнению с прошлым кварталом?",
        "Сколько стоит закупить всё, что в риске дефицита?",
        "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?",
        "Заказать масло",
        "Сколько это будет стоить?",
        "Когда привезут заказ от поставщика?",
        "Какая погода в Сочи на выходных?"
    ]
}


def main() -> None:
    Path("dataset.json").write_text(
        json.dumps(DATASET, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    Path("catalog.json").write_text(
        json.dumps(CATALOG, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Created dataset.json and catalog.json")


if __name__ == "__main__":
    main()