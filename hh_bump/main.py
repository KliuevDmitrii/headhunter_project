from hh_bump.notifier import TelegramNotifier


def main():
    notifier = TelegramNotifier()
    notifier.send(
        "ℹ️ Пора поднять резюме."
    )


if __name__ == "__main__":
    main()