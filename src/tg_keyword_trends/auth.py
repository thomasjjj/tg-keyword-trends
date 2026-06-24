import sys

from colorama import Fore
from telethon.errors import PasswordHashInvalidError, SessionPasswordNeededError
from telethon.sync import TelegramClient

from .console import printC
from .constants import ENV_FILE_PATH, TELEGRAM_2FA_PASSWORD_KEY, TELEGRAM_PHONE_KEY
from .env import load_telegram_env_credentials, prompt_for_env_value, write_env_file


def sign_in_with_2fa_password(client, env_values):
    password = env_values.get(TELEGRAM_2FA_PASSWORD_KEY, "")

    for _ in range(2):
        if not password:
            printC("Two-factor authentication is enabled for this Telegram account.", Fore.YELLOW)
            printC(f"The password you enter will be visible and saved in {ENV_FILE_PATH} as plaintext.", Fore.YELLOW)
            password = input("Type your Telegram 2FA password: ")

        try:
            client.sign_in(password=password)
            env_values[TELEGRAM_2FA_PASSWORD_KEY] = password
            write_env_file(env_values)
            return
        except PasswordHashInvalidError:
            printC("The Telegram 2FA password was rejected.", Fore.RED)
            password = ""

    sys.exit(f"Could not sign in. Please update {TELEGRAM_2FA_PASSWORD_KEY} in {ENV_FILE_PATH} and try again.")


def connect_to_telegram():
    """
     Connects to Telegram using credentials stored in '.env'.
     If credentials are missing, it prompts the user and saves them for future runs.

     Returns:
         TelegramClient: A connected TelegramClient instance.

     Raises:
         SystemExit: If the connection to the Telegram client fails.
     """

    print("Connecting to Telegram...")
    env_values, api_id, api_hash, session_name = load_telegram_env_credentials()
    client = TelegramClient(session_name, api_id, api_hash)

    try:
        client.connect()

        if not client.is_user_authorized():
            phone = prompt_for_env_value(
                env_values,
                TELEGRAM_PHONE_KEY,
                "Type your Telegram phone number, including country code: ",
            )

            print("Sending Telegram login code...")
            client.send_code_request(phone)
            code = input("Type the Telegram login code: ").strip()

            try:
                client.sign_in(phone=phone, code=code)
            except SessionPasswordNeededError:
                sign_in_with_2fa_password(client, env_values)

        if not client.is_user_authorized():
            sys.exit(f"Error connecting to Telegram client. Please check credentials in {ENV_FILE_PATH}.")

        print("Connection to Telegram established.")
        print("Please wait...")
        return client
    except Exception:
        client.disconnect()
        raise
