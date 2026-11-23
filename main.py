import requests

# Настройки подключения к Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b"  # Измените на вашу модель в Ollama

# Системные инструкции для Даниела (System Prompt)
SYSTEM_PROMPT = (
    "Ты — Р. Даниел Оливо (Daneel.AI), локальный ИИ-агент, названный в честь робота-детектива Исаака Азимова. "
    "Твоя цель — помогать пользователю решать домашние и рабочие задачи. "
    "Отвечай кратко, четко, по делу и на русском языке."
)


def ask_daneel(user_input):
    """Функция отправки запроса в локальную Ollama"""
    full_prompt = f"{SYSTEM_PROMPT}\n\nПользователь: {user_input}\nДаниел:"

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,  # Выключаем потоковую передачу для простоты кода MVP
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            return response.json().get("response", "Ошибка: пустой ответ.")
        else:
            return f"Ошибка Ollama: код {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "Ошибка: Не удалось подключиться к Ollama. Проверьте, запущен ли сервис."


def main():
    print("🤖 Daneel.AI запущен и готов к работе offline.")
    print("(Для выхода введите 'выход' или 'exit')\n")

    while True:
        user_input = input("Вы: ")
        if user_input.lower() in ["выход", "exit"]:
            print("🤖 До встречи, создатель.")
            break

        if not user_input.strip():
            continue

        print("🤖 Даниел думает...")
        answer = ask_daneel(user_input)
        print(f"🤖 Даниел: {answer}\n")


if __name__ == "__main__":
    main()
