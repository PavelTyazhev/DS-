import json
import argparse
from typing import Any

from part1_normalization import normalize_movement
from part2_forecast import forecast_demand
from part3_qa import answer_question


def load_json(filepath: str) -> Any:
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def run_pipeline(dataset_path: str, catalog_path: str) -> None:
    dataset = load_json(dataset_path)
    catalog = load_json(catalog_path)

    print("=" * 60)
    print("ЧАСТЬ 1: НОРМАЛИЗАЦИЯ ЗАПИСЕЙ ДВИЖЕНИЯ ТОВАРА")
    print("=" * 60)

    movements = dataset.get("movements", [])

    for m in movements:
        result = normalize_movement(m["text"], catalog)
        print(f"[{m['id']}] {m['text']}")
        print(f"  -> {json.dumps(result, ensure_ascii=False)}\n")

    print("=" * 60)
    print("ЧАСТЬ 2: ПРОГНОЗ ПОТРЕБНОСТИ (Горизонт 30 и 90 дней)")
    print("=" * 60)

    history = dataset.get("history", {})
    skus_to_forecast = ["OIL-001", "SCRB-020", "WRAP-030"]

    for sku in skus_to_forecast:
        cat_item = next((item for item in catalog if item["sku"] == sku), {})

        for horizon in [30, 90]:
            result = forecast_demand(history, sku, horizon, cat_item)

            print(f"[{sku}] Горизонт: {horizon} дней")
            print(f"  Средний расход/день: {result['avg_daily_consumption']}")
            print(f"  Прогноз: {result['forecast_demand']}")
            print(
                f"  Рекомендация: {result['recommended_qty']} "
                f"{cat_item.get('unit')} "
                f"(Стоимость: {result['estimated_cost']} руб)"
            )
            print(f"  Уверенность: {result['confidence']}\n")

    print("=" * 60)
    print("ЧАСТЬ 3: РАЗБОР ВОПРОСОВ ПОЛЬЗОВАТЕЛЯ")
    print("=" * 60)

    questions = dataset.get("questions", [])
    context = {
        "history": history,
        "catalog": catalog
    }

    for i, q in enumerate(questions, 1):
        params, conf, answer = answer_question(q, context)

        source = params.get("source", "fallback")

        print(f"Q{i}: {q}")
        print(
            f"  Интент: {params['intent']} | "
            f"Источник: {source} | "
            f"Уверенность: {conf:.2f}"
        )

        if len(answer) > 200:
            print(f"  Ответ: {answer[:200]}...\n")
        else:
            print(f"  Ответ: {answer}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Inventory Assistant Pipeline")
    parser.add_argument("--dataset", default="dataset.json", help="Path to dataset.json")
    parser.add_argument("--catalog", default="catalog.json", help="Path to catalog.json")
    args = parser.parse_args()

    run_pipeline(args.dataset, args.catalog)