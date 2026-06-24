import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import main


class WorkingDirectoryTestCase(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()


class EnvFileTests(WorkingDirectoryTestCase):
    def test_read_env_file_ignores_comments_and_unquotes_values(self):
        env_path = Path(".env")
        env_path.write_text(
            "\n".join(
                [
                    "# comment",
                    "TELEGRAM_API_ID=123",
                    'SPACED="value with spaces"',
                    'QUOTED="value with \\"quote\\""',
                    'HASHED="abc#123"',
                    "not-a-key-value-line",
                ]
            ),
            encoding="utf-8",
        )

        values = main.read_env_file(env_path)

        self.assertEqual(values["TELEGRAM_API_ID"], "123")
        self.assertEqual(values["SPACED"], "value with spaces")
        self.assertEqual(values["QUOTED"], 'value with "quote"')
        self.assertEqual(values["HASHED"], "abc#123")
        self.assertNotIn("not-a-key-value-line", values)

    def test_write_env_file_updates_existing_keys_and_preserves_other_lines(self):
        env_path = Path(".env")
        env_path.write_text(
            "# header\nOTHER=value\nTELEGRAM_API_ID=old\n",
            encoding="utf-8",
        )

        main.write_env_file(
            {
                main.TELEGRAM_API_ID_KEY: "456",
                main.TELEGRAM_API_HASH_KEY: "hash with spaces",
            },
            env_path,
        )

        contents = env_path.read_text(encoding="utf-8")
        values = main.read_env_file(env_path)

        self.assertIn("# header", contents)
        self.assertIn("OTHER=value", contents)
        self.assertEqual(values[main.TELEGRAM_API_ID_KEY], "456")
        self.assertEqual(values[main.TELEGRAM_API_HASH_KEY], "hash with spaces")

    def test_read_legacy_api_values_reads_existing_format(self):
        legacy_path = Path("api_values.txt")
        legacy_path.write_text("api_id:\n123\napi_hash:\nabc123\n", encoding="utf-8")

        values = main.read_legacy_api_values(legacy_path)

        self.assertEqual(
            values,
            {
                main.TELEGRAM_API_ID_KEY: "123",
                main.TELEGRAM_API_HASH_KEY: "abc123",
            },
        )

    def test_load_credentials_migrates_legacy_file_and_adds_default_session(self):
        Path("api_values.txt").write_text("api_id:\n123\napi_hash:\nabc123\n", encoding="utf-8")

        with redirect_stdout(io.StringIO()):
            env_values, api_id, api_hash, session_name = main.load_telegram_env_credentials()

        self.assertEqual(api_id, 123)
        self.assertEqual(api_hash, "abc123")
        self.assertEqual(session_name, main.DEFAULT_TELEGRAM_SESSION_NAME)
        self.assertEqual(env_values[main.TELEGRAM_SESSION_KEY], main.DEFAULT_TELEGRAM_SESSION_NAME)

        saved_values = main.read_env_file(Path(".env"))
        self.assertEqual(saved_values[main.TELEGRAM_API_ID_KEY], "123")
        self.assertEqual(saved_values[main.TELEGRAM_API_HASH_KEY], "abc123")
        self.assertEqual(saved_values[main.TELEGRAM_SESSION_KEY], main.DEFAULT_TELEGRAM_SESSION_NAME)

    def test_prompt_for_env_value_saves_entered_value(self):
        env_values = {}

        with patch("builtins.input", return_value="entered"):
            value = main.prompt_for_env_value(env_values, "SAMPLE_KEY", "Sample prompt: ")

        self.assertEqual(value, "entered")
        self.assertEqual(env_values["SAMPLE_KEY"], "entered")
        self.assertEqual(main.read_env_file(Path(".env"))["SAMPLE_KEY"], "entered")

    def test_sign_in_with_2fa_password_uses_saved_password(self):
        client = Mock()
        env_values = {main.TELEGRAM_2FA_PASSWORD_KEY: "secret"}

        main.sign_in_with_2fa_password(client, env_values)

        client.sign_in.assert_called_once_with(password="secret")
        self.assertEqual(main.read_env_file(Path(".env"))[main.TELEGRAM_2FA_PASSWORD_KEY], "secret")


class PureHelperTests(WorkingDirectoryTestCase):
    def test_check_search_terms_file_reads_existing_terms(self):
        terms_path = Path("terms.txt")
        terms_path.write_text("alpha\nbeta\n", encoding="utf-8")

        with redirect_stdout(io.StringIO()):
            search_terms = main.check_search_terms_file(terms_path)

        self.assertEqual(search_terms, ["alpha", "beta"])

    def test_render_url_returns_link_markup(self):
        url = "https://t.me/example/1"

        self.assertEqual(main.render_url(url), f'<a href="{url}">{url}</a>')


if __name__ == "__main__":
    unittest.main()
