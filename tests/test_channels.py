import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tg_keyword_trends.app import run_async
from tg_keyword_trends.channels import ChannelTarget, resolve_channel_entries, select_channels


class ChannelSelectionTests(unittest.TestCase):
    def test_resolve_channel_entries_returns_targets_and_unresolved(self):
        client = SimpleNamespace()

        async def get_entity(reference):
            if reference == "bad":
                raise ValueError("not found")
            return SimpleNamespace(id=123, title=f"Title {reference}")

        client.get_entity = AsyncMock(side_effect=get_entity)

        selection = run_async(resolve_channel_entries(client, ["# ignored", "t.me/good", "bad"]))

        self.assertEqual(selection.targets, [ChannelTarget(title="Title good", entity=selection.targets[0].entity, channel_id=123)])
        self.assertEqual(selection.unresolved[0].entry, "bad")

    def test_select_channels_defaults_to_followed_dialogs(self):
        client = SimpleNamespace()
        client.get_input_entity = AsyncMock(return_value=SimpleNamespace(channel_id=42))
        dialogs = [SimpleNamespace(is_channel=True, title="News"), SimpleNamespace(is_channel=False, title="Chat")]

        selection = run_async(select_channels(client, dialogs, input_func=lambda _: "no"))

        self.assertEqual(len(selection.targets), 1)
        self.assertEqual(selection.targets[0].title, "News")
        self.assertEqual(selection.targets[0].channel_id, 42)

    def test_select_channels_reads_custom_file(self):
        client = SimpleNamespace()
        client.get_entity = AsyncMock(return_value=SimpleNamespace(id=99, title="Custom"))

        with tempfile.TemporaryDirectory() as temp_dir:
            channel_file = Path(temp_dir) / "channels.txt"
            channel_file.write_text("t.me/custom\n", encoding="utf-8")

            selection = run_async(
                select_channels(
                    client,
                    dialogs=[],
                    input_func=lambda _: "yes",
                    file_picker=lambda _: str(channel_file),
                )
            )

        self.assertEqual(len(selection.targets), 1)
        self.assertEqual(selection.targets[0].title, "Custom")

    def test_select_channels_errors_when_custom_file_resolves_none(self):
        client = SimpleNamespace()
        client.get_entity = AsyncMock(side_effect=ValueError("not found"))

        with tempfile.TemporaryDirectory() as temp_dir:
            channel_file = Path(temp_dir) / "channels.txt"
            channel_file.write_text("bad\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "No channels"):
                run_async(
                    select_channels(
                        client,
                        dialogs=[],
                        input_func=lambda _: "yes",
                        file_picker=lambda _: str(channel_file),
                        output_func=lambda _: None,
                    )
                )


if __name__ == "__main__":
    unittest.main()
