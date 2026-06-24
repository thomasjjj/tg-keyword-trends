import datetime

import pytz


DATE_FORMAT = "%d/%m/%Y"


def parse_date_bound(value, is_end=False, timezone=pytz.UTC):
    value = value.strip()
    if not value:
        return None

    try:
        parsed_date = datetime.datetime.strptime(value, DATE_FORMAT)
    except ValueError as exc:
        raise ValueError("Date must be in dd/mm/yyyy format.") from exc

    if is_end:
        parsed_date = parsed_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        parsed_date = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)

    return timezone.localize(parsed_date) if parsed_date.tzinfo is None else parsed_date.astimezone(timezone)


def parse_date_range(start_date_text, end_date_text, timezone=pytz.UTC):
    start_date = parse_date_bound(start_date_text, is_end=False, timezone=timezone)
    end_date = parse_date_bound(end_date_text, is_end=True, timezone=timezone)

    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date must be before or equal to end date.")

    return start_date, end_date


def prompt_date_range(input_func=input, output_func=print, timezone=pytz.UTC):
    while True:
        start_date_text = input_func("Enter the start date (dd/mm/yyyy) or leave it blank for no start date: ")
        end_date_text = input_func("Enter the end date (dd/mm/yyyy) or leave it blank for no end date: ")

        try:
            return parse_date_range(start_date_text, end_date_text, timezone=timezone)
        except ValueError as exc:
            output_func(f"Invalid date range: {exc}")
