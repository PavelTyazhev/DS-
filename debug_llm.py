import os
import sys
import traceback
from pathlib import Path


def main() -> None:
    print("Python:", sys.version)
    print("Current directory:", Path.cwd())
    print(".env exists:", Path(".env").exists())

    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("python-dotenv: OK")
    except ImportError as e:
        print("python-dotenv is not installed:", e)

    print("LLM_PROVIDER:", os.getenv("LLM_PROVIDER"))
    print("GIGACHAT_CREDENTIALS set:", bool(os.getenv("GIGACHAT_CREDENTIALS")))
    print("GIGACHAT_CREDENTIALS length:", len(os.getenv("GIGACHAT_CREDENTIALS", "")))
    print("LLM_MODEL:", os.getenv("LLM_MODEL"))
    print("GIGACHAT_VERIFY_SSL:", os.getenv("GIGACHAT_VERIFY_SSL"))

    try:
        from gigachat import GigaChat
        print("gigachat import: OK")
    except ImportError as e:
        print("gigachat is not installed:", e)
        return

    credentials = os.getenv("GIGACHAT_CREDENTIALS", "")
    model = os.getenv("LLM_MODEL", "GigaChat-3-Ultra")
    verify_ssl = os.getenv("GIGACHAT_VERIFY_SSL", "false").strip().lower() != "false"
    scope = os.getenv("GIGACHAT_SCOPE", "https://api.gigachat.ai/v1")

    if not credentials:
        print("No GIGACHAT_CREDENTIALS found. Stop.")
        return

    messages = [
        {
            "role": "user",
            "content": "Ответь одним словом: ок"
        }
    ]

    init_variants = [
        {
            "credentials": credentials,
            "verify_ssl": verify_ssl,
            "scope": scope,
        },
        {
            "credentials": credentials,
            "verify_ssl": verify_ssl,
        },
        {
            "credentials": credentials,
        },
    ]

    for kwargs in init_variants:
        try:
            print("\nTrying GigaChat init with keys:", list(kwargs.keys()))

            client = GigaChat(**kwargs)

            if hasattr(client, "__enter__"):
                with client as giga_client:
                    response = giga_client.chat(
                        model=model,
                        messages=messages,
                        temperature=0.0,
                    )
            else:
                response = client.chat(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                )

            print("SUCCESS")
            print(response)
            return

        except Exception:
            traceback.print_exc()

    print("\nAll GigaChat init variants failed.")


if __name__ == "__main__":
    main()