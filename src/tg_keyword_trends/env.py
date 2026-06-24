import os
import sys

from colorama import Fore

from .console import printC
from .constants import (
    DEFAULT_TELEGRAM_SESSION_NAME,
    ENV_FILE_PATH,
    LEGACY_API_VALUES_FILE_PATH,
    TELEGRAM_API_HASH_KEY,
    TELEGRAM_API_ID_KEY,
    TELEGRAM_SESSION_KEY,
)


def parse_env_value(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        quote = value[0]
        value = value[1:-1]
        if quote == '"':
            value = value.replace(r"\n", "\n").replace(r"\"", '"').replace(r"\\", "\\")
    return value


def read_env_file(file_path=ENV_FILE_PATH):
    env_values = {}

    if not os.path.exists(file_path):
        return env_values

    with open(file_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            env_values[key.strip()] = parse_env_value(value)

    return env_values


def format_env_value(value):
    value = str(value).replace("\n", r"\n")
    if not value or any(character.isspace() for character in value) or any(character in value for character in '#"\''):
        value = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{value}"'
    return value


def write_env_file(updated_values, file_path=ENV_FILE_PATH):
    existing_lines = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as env_file:
            existing_lines = env_file.readlines()

    written_keys = set()
    output_lines = []

    for raw_line in existing_lines:
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#") or "=" not in raw_line:
            output_lines.append(raw_line)
            continue

        key = raw_line.split("=", 1)[0].strip()
        if key in updated_values:
            output_lines.append(f"{key}={format_env_value(updated_values[key])}\n")
            written_keys.add(key)
        else:
            output_lines.append(raw_line)

    if output_lines and output_lines[-1].strip():
        output_lines.append("\n")

    for key, value in updated_values.items():
        if key not in written_keys:
            output_lines.append(f"{key}={format_env_value(value)}\n")

    with open(file_path, "w", encoding="utf-8") as env_file:
        env_file.writelines(output_lines)


def read_legacy_api_values(file_path=LEGACY_API_VALUES_FILE_PATH):
    if not os.path.exists(file_path):
        return {}

    with open(file_path, "r", encoding="utf-8") as legacy_file:
        lines = [line.strip() for line in legacy_file.readlines()]

    try:
        return {
            TELEGRAM_API_ID_KEY: lines[1],
            TELEGRAM_API_HASH_KEY: lines[3],
        }
    except IndexError:
        printC(f"Could not read legacy API details from {file_path}.", Fore.YELLOW)
        return {}


def prompt_for_env_value(env_values, key, prompt, allow_empty=False):
    value = env_values.get(key, "").strip()
    if value:
        return value

    value = input(prompt).strip()
    if not value and not allow_empty:
        sys.exit(f"Missing required value for {key}.")

    env_values[key] = value
    write_env_file(env_values)
    return value


def load_telegram_env_credentials():
    env_values = read_env_file()
    legacy_api_values = read_legacy_api_values()
    migrated_legacy_values = False

    for key, value in legacy_api_values.items():
        if value and not env_values.get(key):
            env_values[key] = value
            migrated_legacy_values = True

    if migrated_legacy_values:
        write_env_file(env_values)
        printC(f"Migrated Telegram API details from {LEGACY_API_VALUES_FILE_PATH} to {ENV_FILE_PATH}.", Fore.YELLOW)

    if not env_values.get(TELEGRAM_API_ID_KEY) or not env_values.get(TELEGRAM_API_HASH_KEY):
        printC(f"No Telegram API details found in {ENV_FILE_PATH}. This should be a one-time setup.", Fore.YELLOW)

    api_id = prompt_for_env_value(env_values, TELEGRAM_API_ID_KEY, "Type your Telegram API ID: ")
    api_hash = prompt_for_env_value(env_values, TELEGRAM_API_HASH_KEY, "Type your Telegram API Hash: ")

    try:
        api_id = int(api_id)
    except ValueError:
        sys.exit(f"{TELEGRAM_API_ID_KEY} in {ENV_FILE_PATH} must be a number.")

    if not env_values.get(TELEGRAM_SESSION_KEY, "").strip():
        env_values[TELEGRAM_SESSION_KEY] = DEFAULT_TELEGRAM_SESSION_NAME
        write_env_file(env_values)
    session_name = env_values[TELEGRAM_SESSION_KEY].strip()

    return env_values, api_id, api_hash, session_name
