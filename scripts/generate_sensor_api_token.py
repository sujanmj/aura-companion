import secrets


def main() -> None:
    token = secrets.token_urlsafe(32)
    print(f"AURA_SENSOR_API_TOKEN={token}")
    print("Add this line to config/keys.env:")
    print(f"AURA_SENSOR_API_TOKEN={token}")


if __name__ == "__main__":
    main()
