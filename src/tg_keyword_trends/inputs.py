"""Pure input parsing helpers for dates, search terms, and channel lists."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone as datetime_timezone, tzinfo
import re
from typing import Callable, Iterable, TypeAlias
from urllib.parse import unquote, urlparse


DATE_FORMAT = "%d/%m/%Y"

ChannelReference: TypeAlias = str | int

_NUMERIC_ID_RE = re.compile(r"^-?\d+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_TELEGRAM_HOSTS = {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}


@dataclass(frozen=True)
class DateRange:
    start: datetime | None
    end: datetime | None

    def __iter__(self):
        yield self.start
        yield self.end


@dataclass(frozen=True)
class SearchTermGroup:
    label: str
    terms: tuple[str, ...]


def content_lines(lines: Iterable[str]) -> list[str]:
    """Return stripped, non-empty, non-comment input lines."""
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def parse_date_value(value: str, *, is_end: bool = False, tz: tzinfo | None = datetime_timezone.utc) -> datetime | None:
    """Parse a dd/mm/yyyy input value, returning None for blank input."""
    cleaned_value = value.strip()
    if not cleaned_value:
        return None

    try:
        parsed = datetime.strptime(cleaned_value, DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(f"Expected date in dd/mm/yyyy format, got {value!r}.") from exc

    return _datetime_at_boundary(parsed, is_end=is_end, tz=tz)


def _datetime_at_boundary(parsed: datetime, *, is_end: bool, tz: tzinfo | None) -> datetime:
    boundary = time.max if is_end else time.min
    naive_value = datetime.combine(parsed.date(), boundary)
    if tz is None:
        return naive_value
    if hasattr(tz, "localize"):
        return tz.localize(naive_value)
    return naive_value.replace(tzinfo=tz)


def parse_date_bound(
    value: str,
    is_end: bool = False,
    timezone: tzinfo | None = datetime_timezone.utc,
) -> datetime | None:
    """Backward-compatible wrapper for parsing a start/end date bound."""
    return parse_date_value(value, is_end=is_end, tz=timezone)


def parse_date_range(
    start_value: str,
    end_value: str,
    *,
    tz: tzinfo | None = datetime_timezone.utc,
    timezone: tzinfo | None = None,
) -> DateRange:
    """Parse and validate a start/end date range from dd/mm/yyyy strings."""
    selected_tz = timezone if timezone is not None else tz
    start = parse_date_value(start_value, tz=selected_tz)
    end = parse_date_value(end_value, is_end=True, tz=selected_tz)

    if start is not None and end is not None and start > end:
        raise ValueError("Start date must be on or before end date.")

    return DateRange(start=start, end=end)


def prompt_date_range(
    input_func: Callable[[str], str] = input,
    *,
    error_func: Callable[[str], None] | None = None,
    output_func: Callable[[str], None] | None = print,
    start_prompt: str = "Enter the start date (dd/mm/yyyy) or leave it blank for no start date: ",
    end_prompt: str = "Enter the end date (dd/mm/yyyy) or leave it blank for no end date: ",
    tz: tzinfo | None = datetime_timezone.utc,
    timezone: tzinfo | None = None,
) -> DateRange:
    """Prompt until a valid date range is entered."""
    while True:
        start_value = input_func(start_prompt)
        end_value = input_func(end_prompt)

        try:
            return parse_date_range(start_value, end_value, tz=tz, timezone=timezone)
        except ValueError as exc:
            if error_func is not None:
                error_func(str(exc))
                continue
            if output_func is not None:
                output_func(f"Invalid date range: {exc}")
                continue
            else:
                raise


def parse_search_term_groups(lines: Iterable[str]) -> list[SearchTermGroup]:
    """Parse search terms, allowing labelled groups with pipe-delimited terms."""
    groups: list[SearchTermGroup] = []

    for line in content_lines(lines):
        if ":" not in line:
            groups.append(SearchTermGroup(label=line, terms=(line,)))
            continue

        label, terms_value = line.split(":", 1)
        label = label.strip()
        terms = tuple(term.strip() for term in terms_value.split("|") if term.strip())

        if not label:
            raise ValueError("Search term group label cannot be blank.")
        if not terms:
            raise ValueError(f"Search term group {label!r} must include at least one term.")

        groups.append(SearchTermGroup(label=label, terms=terms))

    return groups


def flatten_search_term_groups(groups: Iterable[SearchTermGroup]) -> list[str]:
    """Return search terms in group order for callers that need a flat term list."""
    return [term for group in groups for term in group.terms]


def normalize_channel_entry(entry: str) -> ChannelReference:
    """Normalize a Telegram channel entry to a username or numeric ID."""
    value = _extract_telegram_link_reference(entry.strip())
    if not value:
        raise ValueError("Channel entry cannot be blank.")

    if value.startswith("@"):
        value = value[1:].strip()

    if _NUMERIC_ID_RE.fullmatch(value):
        return int(value)

    if _USERNAME_RE.fullmatch(value):
        return value

    raise ValueError(f"Unsupported Telegram channel entry: {entry!r}.")


def parse_channel_entries(lines: Iterable[str]) -> list[ChannelReference]:
    """Parse channel entries, ignoring blank lines and full-line comments."""
    return [normalize_channel_entry(line) for line in content_lines(lines)]


def _extract_telegram_link_reference(value: str) -> str:
    if "://" in value:
        parsed = urlparse(value)
    else:
        parsed = urlparse(f"https://{value}")

    if parsed.netloc.lower() not in _TELEGRAM_HOSTS:
        return value

    path_parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if not path_parts:
        return ""

    if path_parts[0] == "c" and len(path_parts) >= 2 and _NUMERIC_ID_RE.fullmatch(path_parts[1]):
        return _normalize_private_channel_id(path_parts[1])

    if path_parts[0] == "s" and len(path_parts) >= 2:
        return path_parts[1]

    return path_parts[0]


def _normalize_private_channel_id(value: str) -> str:
    if value.startswith("-"):
        return value
    return f"-100{value}"
