import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tg_keyword_trends.app import _format_message_date, download_queued_media, run_async
from tg_keyword_trends.media import MEDIA_STATUS_DOWNLOADED, MediaDownloadJob, load_media_manifest


class AppMediaTests(unittest.TestCase):
    def test_format_message_date_uses_isoformat_when_available(self):
        value = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)

        self.assertEqual(_format_message_date(value), "2026-01-02T03:04:00+00:00")
        self.assertIsNone(_format_message_date(None))
        self.assertEqual(_format_message_date("raw"), "raw")

    def test_download_queued_media_downloads_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "media_manifest.jsonl"
            output_path = Path(temp_dir) / "media.bin"
            client = Mock()
            client.download_media = AsyncMock(return_value=output_path)
            job = MediaDownloadJob(
                message="message",
                file_path=output_path,
                channel_id=123,
                message_id=456,
                metadata={"search_term": "alpha"},
            )

            results = run_async(download_queued_media(client, [job], manifest_path, [], 2))

            self.assertEqual(results[0].status, MEDIA_STATUS_DOWNLOADED)
            self.assertEqual(client.download_media.await_count, 1)
            self.assertEqual(load_media_manifest(manifest_path)[0]["search_term"], "alpha")


if __name__ == "__main__":
    unittest.main()
