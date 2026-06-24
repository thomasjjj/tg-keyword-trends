from dataclasses import dataclass
from typing import Any, Callable

from .files import open_file_dialog
from .inputs import content_lines, normalize_channel_entry


@dataclass(frozen=True)
class ChannelTarget:
    title: str
    entity: Any
    channel_id: int


@dataclass(frozen=True)
class UnresolvedChannel:
    entry: str
    reason: str


@dataclass(frozen=True)
class ChannelSelection:
    targets: list[ChannelTarget]
    unresolved: list[UnresolvedChannel]


def get_channel_id(entity):
    channel_id = getattr(entity, "channel_id", None)
    if channel_id is not None:
        return channel_id

    chat_id = getattr(entity, "chat_id", None)
    if chat_id is not None:
        return chat_id

    return entity.id


def get_channel_title(source, entity):
    title = getattr(source, "title", None) or getattr(entity, "title", None) or getattr(entity, "username", None)
    return title or str(get_channel_id(entity))


async def target_from_dialog(client, dialog):
    entity = await client.get_input_entity(dialog)
    return ChannelTarget(
        title=get_channel_title(dialog, entity),
        entity=entity,
        channel_id=get_channel_id(entity),
    )


async def resolve_channel_entries(client, lines):
    targets = []
    unresolved = []

    for line in content_lines(lines):
        try:
            reference = normalize_channel_entry(line)
            entity = await client.get_entity(reference)
            targets.append(
                ChannelTarget(
                    title=get_channel_title(entity, entity),
                    entity=entity,
                    channel_id=get_channel_id(entity),
                )
            )
        except Exception as exc:
            unresolved.append(UnresolvedChannel(entry=line, reason=str(exc)))

    return ChannelSelection(targets=targets, unresolved=unresolved)


async def select_channels(
    client,
    dialogs,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
    file_picker: Callable[[str], str] = open_file_dialog,
):
    use_custom_list = input_func("Use a custom channel list? (yes/no): ").strip().lower()

    if use_custom_list not in {"yes", "y"}:
        return ChannelSelection(
            targets=[await target_from_dialog(client, dialog) for dialog in dialogs if dialog.is_channel],
            unresolved=[],
        )

    channel_list_file = file_picker("Select the channel list .txt file")
    with open(channel_list_file, "r", encoding="utf-8") as file:
        selection = await resolve_channel_entries(client, file.readlines())

    for unresolved in selection.unresolved:
        output_func(f"Could not resolve channel '{unresolved.entry}': {unresolved.reason}")

    if not selection.targets:
        raise ValueError("No channels from the custom channel list could be resolved.")

    return selection
