import asyncio
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from importlib.resources import files
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tg_keyword_trends import constants
from tg_keyword_trends import env
from tg_keyword_trends.app import run_async
from tg_keyword_trends.auth import sign_in_with_2fa_password
from tg_keyword_trends.files import check_search_terms_file, render_url


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

        values = env.read_env_file(env_path)

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

        env.write_env_file(
            {
                constants.TELEGRAM_API_ID_KEY: "456",
                constants.TELEGRAM_API_HASH_KEY: "hash with spaces",
            },
            env_path,
        )

        contents = env_path.read_text(encoding="utf-8")
        values = env.read_env_file(env_path)

        self.assertIn("# header", contents)
        self.assertIn("OTHER=value", contents)
        self.assertEqual(values[constants.TELEGRAM_API_ID_KEY], "456")
        self.assertEqual(values[constants.TELEGRAM_API_HASH_KEY], "hash with spaces")

    def test_read_legacy_api_values_reads_existing_format(self):
        legacy_path = Path("api_values.txt")
        legacy_path.write_text("api_id:\n123\napi_hash:\nabc123\n", encoding="utf-8")

        values = env.read_legacy_api_values(legacy_path)

        self.assertEqual(
            values,
            {
                constants.TELEGRAM_API_ID_KEY: "123",
                constants.TELEGRAM_API_HASH_KEY: "abc123",
            },
        )

    def test_load_credentials_migrates_legacy_file_and_adds_default_session(self):
        Path("api_values.txt").write_text("api_id:\n123\napi_hash:\nabc123\n", encoding="utf-8")

        with redirect_stdout(io.StringIO()):
            env_values, api_id, api_hash, session_name = env.load_telegram_env_credentials()

        self.assertEqual(api_id, 123)
        self.assertEqual(api_hash, "abc123")
        self.assertEqual(session_name, constants.DEFAULT_TELEGRAM_SESSION_NAME)
        self.assertEqual(env_values[constants.TELEGRAM_SESSION_KEY], constants.DEFAULT_TELEGRAM_SESSION_NAME)

        saved_values = env.read_env_file(Path(".env"))
        self.assertEqual(saved_values[constants.TELEGRAM_API_ID_KEY], "123")
        self.assertEqual(saved_values[constants.TELEGRAM_API_HASH_KEY], "abc123")
        self.assertEqual(saved_values[constants.TELEGRAM_SESSION_KEY], constants.DEFAULT_TELEGRAM_SESSION_NAME)

    def test_prompt_for_env_value_saves_entered_value(self):
        env_values = {}

        with patch("builtins.input", return_value="entered"):
            value = env.prompt_for_env_value(env_values, "SAMPLE_KEY", "Sample prompt: ")

        self.assertEqual(value, "entered")
        self.assertEqual(env_values["SAMPLE_KEY"], "entered")
        self.assertEqual(env.read_env_file(Path(".env"))["SAMPLE_KEY"], "entered")

    def test_sign_in_with_2fa_password_uses_saved_password(self):
        client = Mock()
        client.sign_in = AsyncMock()
        env_values = {constants.TELEGRAM_2FA_PASSWORD_KEY: "secret"}

        run_async(sign_in_with_2fa_password(client, env_values))

        client.sign_in.assert_awaited_once_with(password="secret")
        self.assertEqual(env.read_env_file(Path(".env"))[constants.TELEGRAM_2FA_PASSWORD_KEY], "secret")


class PureHelperTests(WorkingDirectoryTestCase):
    def test_check_search_terms_file_reads_existing_terms(self):
        terms_path = Path("terms.txt")
        terms_path.write_text("alpha\nbeta\n", encoding="utf-8")

        with redirect_stdout(io.StringIO()):
            search_terms = check_search_terms_file(terms_path)

        self.assertEqual(search_terms, ["alpha", "beta"])

    def test_render_url_returns_link_markup(self):
        url = "https://t.me/example/1"

        self.assertEqual(render_url(url), f'<a href="{url}">{url}</a>')

    def test_report_template_is_packaged(self):
        template_text = files("tg_keyword_trends").joinpath("report_template_text.txt").read_text(encoding="utf-8")

        self.assertIn("Telegram", template_text)

    def test_run_async_returns_coroutine_result(self):
        async def sample():
            return "done"

        self.assertEqual(run_async(sample()), "done")

    def test_run_async_returns_result_when_loop_is_already_running(self):
        async def outer():
            async def sample():
                return "done"

            return run_async(sample())

        self.assertEqual(asyncio.run(outer()), "done")


if __name__ == "__main__":
    unittest.main()
