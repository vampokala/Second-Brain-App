import requests


def fetch_models():
    try:
        response = requests.get("http://localhost:11434/api/tags")
        response.raise_for_status()

        data = response.json()
        models = data.get("models", [])

        if not models:
            print("No local Ollama models found.")
            return

        for model in models:
            name = model.get("name", "Unknown")
            size_bytes = model.get("size", 0)
            size_gb = size_bytes / (1024 ** 3)
            modified = model.get("modified_at", "Unknown")

            print(f"Name: {name}")
            print(f"Size: {size_gb:.2f} GB")
            print(f"Modified: {modified}")
            print("-" * 40)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching models: {e}")


if __name__ == "__main__":
    fetch_models()