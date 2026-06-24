ENV_FILE_PATH = ".env"
LEGACY_API_VALUES_FILE_PATH = "api_values.txt"
DEFAULT_TELEGRAM_SESSION_NAME = "session_name"

TELEGRAM_API_ID_KEY = "TELEGRAM_API_ID"
TELEGRAM_API_HASH_KEY = "TELEGRAM_API_HASH"
TELEGRAM_PHONE_KEY = "TELEGRAM_PHONE"
TELEGRAM_2FA_PASSWORD_KEY = "TELEGRAM_2FA_PASSWORD"
TELEGRAM_SESSION_KEY = "TELEGRAM_SESSION"


SCRIPT_DESCRIPTION = r"""

 _____    _                                  _____                  _
|_   _|  | |                                |_   _|                | |
  | | ___| | ___  __ _ _ __ __ _ _ __ ___     | |_ __ ___ _ __   __| |___
  | |/ _ \ |/ _ \/ _` | '__/ _` | '_ ` _ \    | | '__/ _ \ '_ \ / _` / __|
  | |  __/ |  __/ (_| | | | (_| | | | | | |   | | | |  __/ | | | (_| \__ \
  \_/\___|_|\___|\__, |_|  \__,_|_| |_| |_|   \_/_|  \___|_| |_|\__,_|___/
                  __/ |
                 |___/
By: Tom Jarvis | Twitter: @tomtomjarvis
---------------------------------------
This script searches messages containing specified search terms in Telegram channels the user is a member of.
It exports the search results in HTML and CSV formats, generates a report, and plots the message count per day."""

SCRIPT_WARNING = r"""
WARNING: This tool uses your list of followed groups as the list it searches from. It may include personal chats/groups.
         For the sake of OPSEC, it is recommended to use a burner account and follow only investigation-specific chats.
"""
