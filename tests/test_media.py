import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tg_keyword_trends import media


class WorkingDirectoryTestCase(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()


class MediaOutputDirectoryTests(WorkingDirectoryTestCase):
    def test_resolve_media_output_dir_defaults_to_tg_media(self):
        self.assertEqual(media.resolve_media_output_dir(), Path.cwd() / "TG-Media")

    def test_resolve_media_output_dir_uses_env_values(self):
        self.assertEqual(
            media.resolve_media_output_dir({media.MEDIA_OUTPUT_DIR_KEY: "custom-media"}),
            Path.cwd() / "custom-media",
        )

    def test_resolve_media_output_dir_reads_env_file(self):
        Path(".env").write_text("MEDIA_OUTPUT_DIR=from-env\n", encoding="utf-8")

        self.assertEqual(media.resolve_media_output_dir(), Path.cwd() / "from-env")

    def test_resolve_media_output_dir_keeps_absolute_env_value(self):
        absolute_path = Path.cwd() / "absolute-media"

        self.assertEqual(
            media.resolve_media_output_dir({media.MEDIA_OUTPUT_DIR_KEY: str(absolute_path)}),
            absolute_path,
        )


class MediaManifestTests(WorkingDirectoryTestCase):
    def test_load_media_manifest_returns_empty_list_when_missing(self):
        self.assertEqual(media.load_media_manifest("missing.jsonl"), [])

    def test_append_and_load_media_manifest_records(self):
        manifest_path = Path("nested") / "media.jsonl"
        first = {"channel_id": 123, "message_id": 1, "file_path": "one.jpg"}
        second = {"channel_id": "456", "message_id": "2", "file_path": "two.jpg"}

        media.append_media_manifest_record(manifest_path, first)
        media.append_media_manifest_record(manifest_path, second)

        self.assertEqual(media.load_media_manifest(manifest_path), [first, second])

    def test_load_media_manifest_rejects_non_object_lines(self):
        manifest_path = Path("media.jsonl")
        manifest_path.write_text('["not", "an", "object"]\n', encoding="utf-8")

        with self.assertRaises(ValueError):
            media.load_media_manifest(manifest_path)

    def test_is_duplicate_media_matches_channel_and_message_pair(self):
        records = [
            {"channel_id": 123, "message_id": 1, "file_path": "one.jpg"},
            {"channel_id": 999, "message_id": 2, "file_path": "two.jpg"},
        ]

        self.assertTrue(media.is_duplicate_media(records, "123", "1"))
        self.assertFalse(media.is_duplicate_media(records, "123", "2"))

    def test_should_redownload_missing_file_uses_latest_matching_record(self):
        existing_path = Path("existing.jpg")
        existing_path.write_text("media", encoding="utf-8")
        records = [
            {"channel_id": 123, "message_id": 1, "file_path": "missing.jpg"},
            {"channel_id": 123, "message_id": 1, "file_path": str(existing_path)},
        ]

        self.assertFalse(media.should_redownload_missing_file(records, 123, 1))

    def test_should_redownload_missing_file_returns_true_for_missing_manifest_file(self):
        records = [{"channel_id": 123, "message_id": 1, "file_path": "missing.jpg"}]

        self.assertTrue(media.should_redownload_missing_file(records, 123, 1))

    def test_should_redownload_missing_file_returns_false_without_manifest_record(self):
        self.assertFalse(media.should_redownload_missing_file([], 123, 1))


class MediaDownloadQueueTests(WorkingDirectoryTestCase):
    def test_download_media_queue_limits_concurrency_and_appends_manifest(self):
        active_downloads = 0
        max_active_downloads = 0

        async def download_media(message, file_path, **kwargs):
            nonlocal active_downloads, max_active_downloads
            active_downloads += 1
            max_active_downloads = max(max_active_downloads, active_downloads)
            await asyncio.sleep(0.01)
            active_downloads -= 1
            return file_path

        client = Mock()
        client.download_media = AsyncMock(side_effect=download_media)
        jobs = [
            media.MediaDownloadJob(
                message=f"message-{index}",
                file_path=Path("downloads") / f"{index}.jpg",
                channel_id=123,
                message_id=index,
            )
            for index in range(5)
        ]

        results = asyncio.run(
            media.download_media_queue(
                client,
                jobs,
                max_concurrency=2,
                manifest_path=Path("downloads") / "manifest.jsonl",
            )
        )

        self.assertLessEqual(max_active_downloads, 2)
        self.assertEqual(client.download_media.await_count, 5)
        self.assertEqual([result.status for result in results], [media.MEDIA_STATUS_DOWNLOADED] * 5)

        manifest_records = media.load_media_manifest(Path("downloads") / "manifest.jsonl")
        self.assertEqual(len(manifest_records), 5)
        self.assertEqual({record["message_id"] for record in manifest_records}, set(range(5)))

    def test_download_media_queue_skips_existing_manifest_record_with_file(self):
        existing_path = Path("existing.jpg")
        existing_path.write_text("media", encoding="utf-8")
        client = Mock()
        client.download_media = AsyncMock()
        jobs = [
            {
                "message": "message",
                "file_path": "new.jpg",
                "channel_id": 123,
                "message_id": 1,
            }
        ]

        results = asyncio.run(
            media.download_media_queue(
                client,
                jobs,
                manifest_records=[{"channel_id": 123, "message_id": 1, "file_path": str(existing_path)}],
            )
        )

        client.download_media.assert_not_awaited()
        self.assertEqual(results[0].status, media.MEDIA_STATUS_SKIPPED_DUPLICATE)

    def test_download_media_queue_redownloads_when_manifest_file_is_missing(self):
        client = Mock()
        client.download_media = AsyncMock(return_value=Path("new.jpg"))
        jobs = [
            media.MediaDownloadJob(
                message="message",
                file_path="new.jpg",
                channel_id=123,
                message_id=1,
            )
        ]

        results = asyncio.run(
            media.download_media_queue(
                client,
                jobs,
                manifest_records=[{"channel_id": 123, "message_id": 1, "file_path": "missing.jpg"}],
            )
        )

        client.download_media.assert_awaited_once()
        self.assertEqual(results[0].status, media.MEDIA_STATUS_REDOWNLOADED)

    def test_download_media_queue_rejects_invalid_concurrency(self):
        client = Mock()

        with self.assertRaises(ValueError):
            asyncio.run(media.download_media_queue(client, [], max_concurrency=0))


if __name__ == "__main__":
    unittest.main()
