from hh_bump.notifier import TelegramNotifier


def main():
    notifier = TelegramNotifier()
    notifier.send(
        "ℹ️ Поднятие резюме через API HH больше недоступно.\n"
        "Используй ручное поднятие в UI."
    )


if __name__ == "__main__":
    main()

