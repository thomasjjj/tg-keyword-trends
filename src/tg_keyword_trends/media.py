from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .constants import ENV_FILE_PATH
from .env import read_env_file


MEDIA_OUTPUT_DIR_KEY = "MEDIA_OUTPUT_DIR"
DEFAULT_MEDIA_OUTPUT_DIR = "TG-Media"
DEFAULT_MEDIA_MANIFEST_FILENAME = "media_manifest.jsonl"

MEDIA_STATUS_DOWNLOADED = "downloaded"
MEDIA_STATUS_REDOWNLOADED = "redownloaded"
MEDIA_STATUS_SKIPPED_DUPLICATE = "skipped_duplicate"

_FILE_PATH_KEYS = ("file_path", "download_path", "path")


@dataclass(frozen=True)
class MediaDownloadJob:
    message: Any
    file_path: Path | str
    channel_id: Any
    message_id: Any
    progress_callback: Any = None
    metadata: Mapping[str, Any] | None = None
    download_kwargs: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class MediaDownloadResult:
    job: MediaDownloadJob
    status: str
    file_path: Path | None = None
    manifest_record: Mapping[str, Any] | None = None


def resolve_media_output_dir(env_values=None, env_file_path=ENV_FILE_PATH, base_dir=None):
    if env_values is None:
        env_values = read_env_file(env_file_path)

    configured_dir = _clean_env_value((env_values or {}).get(MEDIA_OUTPUT_DIR_KEY))
    output_dir = Path(configured_dir or DEFAULT_MEDIA_OUTPUT_DIR).expanduser()

    if output_dir.is_absolute():
        return output_dir

    root = Path(base_dir) if base_dir is not None else Path.cwd()
    return root / output_dir


def media_manifest_path(output_dir):
    return Path(output_dir) / DEFAULT_MEDIA_MANIFEST_FILENAME


def load_media_manifest(manifest_path):
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        return []

    records = []
    with manifest_path.open("r", encoding="utf-8") as manifest_file:
        for line_number, raw_line in enumerate(manifest_file, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid media manifest JSON on line {line_number}: {exc.msg}") from exc

            if not isinstance(record, dict):
                raise ValueError(f"Media manifest line {line_number} must be a JSON object.")

            records.append(record)

    return records


def append_media_manifest_record(manifest_path, record):
    if not isinstance(record, Mapping):
        raise TypeError("Media manifest records must be mappings.")

    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("a", encoding="utf-8") as manifest_file:
        json.dump(dict(record), manifest_file, ensure_ascii=False, sort_keys=True, default=str)
        manifest_file.write("\n")


def build_media_manifest_record(channel_id, message_id, file_path, metadata=None):
    record = {}
    if metadata:
        record.update(dict(metadata))

    record.update(
        {
            "channel_id": channel_id,
            "message_id": message_id,
            "file_path": str(file_path),
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return record


def media_manifest_key(channel_id, message_id):
    return (_normalize_manifest_id("channel_id", channel_id), _normalize_manifest_id("message_id", message_id))


def find_media_manifest_record(records, channel_id, message_id):
    target_key = media_manifest_key(channel_id, message_id)
    for record in reversed(list(records)):
        if _record_manifest_key(record) == target_key:
            return record
    return None


def is_duplicate_media(records, channel_id, message_id):
    return find_media_manifest_record(records, channel_id, message_id) is not None


def should_redownload_missing_file(records, channel_id, message_id, base_dir=None):
    record = find_media_manifest_record(records, channel_id, message_id)
    if record is None:
        return False

    file_path = _record_file_path(record)
    if file_path is None:
        return True

    file_path = file_path.expanduser()
    if not file_path.is_absolute() and base_dir is not None:
        file_path = Path(base_dir) / file_path

    return not file_path.exists()


async def download_media_queue(
    client,
    jobs,
    max_concurrency=3,
    manifest_path=None,
    manifest_records=None,
    manifest_base_dir=None,
    skip_duplicates=True,
    redownload_missing=True,
):
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1.")

    normalized_jobs = [_coerce_download_job(job) for job in jobs]
    semaphore = asyncio.Semaphore(max_concurrency)
    manifest_lock = asyncio.Lock()
    records = list(manifest_records) if manifest_records is not None else []

    if manifest_path is not None and manifest_records is None:
        records = load_media_manifest(manifest_path)

    if manifest_base_dir is None and manifest_path is not None:
        manifest_base_dir = Path(manifest_path).parent

    in_progress_keys = set()

    async def run_job(job):
        status = MEDIA_STATUS_DOWNLOADED
        job_key = media_manifest_key(job.channel_id, job.message_id)

        if skip_duplicates:
            async with manifest_lock:
                if job_key in in_progress_keys:
                    return MediaDownloadResult(job=job, status=MEDIA_STATUS_SKIPPED_DUPLICATE)

                duplicate = is_duplicate_media(records, job.channel_id, job.message_id)
                missing = (
                    redownload_missing
                    and duplicate
                    and should_redownload_missing_file(records, job.channel_id, job.message_id, manifest_base_dir)
                )

                if duplicate and not missing:
                    return MediaDownloadResult(job=job, status=MEDIA_STATUS_SKIPPED_DUPLICATE)

                if missing:
                    status = MEDIA_STATUS_REDOWNLOADED

                in_progress_keys.add(job_key)
        else:
            async with manifest_lock:
                in_progress_keys.add(job_key)

        try:
            async with semaphore:
                requested_path = Path(job.file_path)
                requested_path.parent.mkdir(parents=True, exist_ok=True)

                kwargs = dict(job.download_kwargs or {})
                if job.progress_callback is not None and "progress_callback" not in kwargs:
                    kwargs["progress_callback"] = job.progress_callback

                downloaded_path = await client.download_media(job.message, requested_path, **kwargs)
                final_path = Path(downloaded_path) if downloaded_path else requested_path
                record = build_media_manifest_record(job.channel_id, job.message_id, final_path, job.metadata)

                if manifest_path is not None:
                    async with manifest_lock:
                        append_media_manifest_record(manifest_path, record)
                        records.append(record)

                return MediaDownloadResult(
                    job=job,
                    status=status,
                    file_path=final_path,
                    manifest_record=record,
                )
        finally:
            async with manifest_lock:
                in_progress_keys.discard(job_key)

    return await asyncio.gather(*(run_job(job) for job in normalized_jobs))


def _clean_env_value(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_manifest_id(name, value):
    normalized = _clean_env_value(value)
    if not normalized:
        raise ValueError(f"{name} is required.")
    return normalized


def _record_manifest_key(record):
    try:
        return media_manifest_key(record.get("channel_id"), record.get("message_id"))
    except ValueError:
        return None


def _record_file_path(record):
    for key in _FILE_PATH_KEYS:
        value = record.get(key)
        if value:
            return Path(value)
    return None


def _coerce_download_job(job):
    if isinstance(job, MediaDownloadJob):
        return job

    if not isinstance(job, Mapping):
        raise TypeError("Download jobs must be MediaDownloadJob instances or mappings.")

    return MediaDownloadJob(
        message=job["message"],
        file_path=job["file_path"],
        channel_id=job["channel_id"],
        message_id=job["message_id"],
        progress_callback=job.get("progress_callback"),
        metadata=job.get("metadata"),
        download_kwargs=job.get("download_kwargs"),
    )
