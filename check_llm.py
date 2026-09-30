from llm_client import ask_llm


def main() -> None:
    answer = ask_llm(
        "Ответь одним словом: ок",
        "Ты тестовый ассистент. Отвечай максимально коротко."
    )

    print("LLM answer:", answer)


if __name__ == "__main__":
    main()