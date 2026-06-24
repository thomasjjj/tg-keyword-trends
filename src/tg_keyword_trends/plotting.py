import os
import re
import textwrap
import traceback
import unicodedata
from importlib.resources import files
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from PIL import Image as PILImage
from colorama import Fore
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph, Preformatted, Spacer

from .console import printC


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_graph_filename(*parts, extension=".png", max_length=180):
    safe_parts = []

    for part in parts:
        if part is None:
            continue

        text = unicodedata.normalize("NFKD", str(part).strip())
        text = text.encode("ascii", "ignore").decode("ascii")
        text = text.replace(os.sep, "_")
        if os.altsep:
            text = text.replace(os.altsep, "_")

        safe_part = SAFE_FILENAME_RE.sub("_", text)
        safe_part = re.sub(r"_+", "_", safe_part).strip("._-")
        if safe_part:
            safe_parts.append(safe_part)

    stem = "_".join(safe_parts) or "graph"
    if stem.upper() in WINDOWS_RESERVED_FILENAMES:
        stem = f"graph_{stem}"

    extension = str(extension or "")
    if extension and not extension.startswith("."):
        extension = f".{extension}"

    max_stem_length = max_length - len(extension)
    if max_stem_length > 0 and len(stem) > max_stem_length:
        stem = stem[:max_stem_length].rstrip("._-") or "graph"

    return f"{stem}{extension}"


def build_graph_manifest_entry(graph_type, filepath=None, *, title=None, search_term=None, scale=None, skipped=False,
                               reason=None, **extra):
    path = Path(filepath) if filepath is not None else None
    entry = {
        "type": graph_type,
        "title": title or graph_type,
        "status": "skipped" if skipped else "created",
        "skipped": bool(skipped),
    }

    if path is not None:
        entry["filename"] = path.name
        entry["path"] = str(path)
    if search_term is not None:
        entry["search_term"] = search_term
    if scale is not None:
        entry["scale"] = scale
    if reason:
        entry["reason"] = reason

    for key, value in extra.items():
        if value is not None:
            entry[key] = value

    return entry


def save_matplotlib_figure(fig, filepath, *, graph_type, title=None, search_term=None, scale=None, close=True, **extra):
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    try:
        fig.savefig(filepath)
    finally:
        if close:
            plt.close(fig)

    return build_graph_manifest_entry(
        graph_type,
        filepath,
        title=title,
        search_term=search_term,
        scale=scale,
        **extra,
    )


def _append_manifest_entry(manifest, entry_or_entries):
    if not entry_or_entries:
        return

    if isinstance(entry_or_entries, list):
        manifest.extend(entry_or_entries)
    else:
        manifest.append(entry_or_entries)


def _iter_grouped_result_frames(grouped_results):
    if grouped_results is None:
        return

    if isinstance(grouped_results, pd.DataFrame):
        if "_search_term" in grouped_results.columns:
            for search_term, frame in grouped_results.groupby("_search_term", dropna=False):
                yield search_term, frame
        elif "search_term" in grouped_results.columns:
            for search_term, frame in grouped_results.groupby("search_term", dropna=False):
                yield search_term, frame
        else:
            yield None, grouped_results
        return

    for search_term, frames in grouped_results.items():
        if isinstance(frames, pd.DataFrame):
            yield search_term, frames
            continue

        if frames is None:
            continue

        for frame in frames:
            if isinstance(frame, pd.DataFrame):
                yield search_term, frame


def _coerce_result_dates(frame):
    if "_date" in frame.columns:
        values = frame["_date"]
    elif "time" in frame.columns:
        values = frame["time"]
    elif "date" in frame.columns:
        values = frame["date"]
    else:
        return pd.Series(pd.NaT, index=frame.index)

    return pd.to_datetime(values, errors="coerce", utc=True).dt.tz_localize(None).dt.floor("D")


def _coerce_message_ids(frame):
    if "_message_id" in frame.columns:
        return pd.to_numeric(frame["_message_id"], errors="coerce")

    if "message_id" in frame.columns:
        return pd.to_numeric(frame["message_id"], errors="coerce")

    if "id" in frame.columns:
        return pd.to_numeric(frame["id"], errors="coerce")

    if "message" in frame.columns:
        return pd.to_numeric(frame["message"].apply(lambda message: getattr(message, "id", None)), errors="coerce")

    return pd.Series(pd.NA, index=frame.index, dtype="Float64")


def _normalise_grouped_results(grouped_results):
    frames = []

    for search_term, frame in _iter_grouped_result_frames(grouped_results):
        if frame.empty:
            continue

        current = frame.copy()
        current["_date"] = _coerce_result_dates(current)
        current = current.dropna(subset=["_date"])
        if current.empty:
            continue

        if search_term is None and "_search_term" in current.columns:
            current["_search_term"] = current["_search_term"].fillna("")
        elif search_term is None and "search_term" in current.columns:
            current["_search_term"] = current["search_term"].fillna("")
        else:
            current["_search_term"] = search_term

        current["_search_term"] = current["_search_term"].astype(str)
        current["_message_id"] = _coerce_message_ids(current)
        if "_channel_id" in current.columns:
            current["_channel_id"] = current["_channel_id"].fillna("_unknown")
        elif "channel_id" in current.columns:
            current["_channel_id"] = current["channel_id"].fillna("_unknown")
        else:
            current["_channel_id"] = "_unknown"

        frames.append(current)

    if not frames:
        return pd.DataFrame(columns=["_date", "_search_term", "_message_id", "_channel_id"])

    return pd.concat(frames, ignore_index=True)


def _normalise_total_daily_messages(total_daily_messages):
    if isinstance(total_daily_messages, pd.DataFrame):
        if "total_messages" in total_daily_messages.columns:
            if "date" in total_daily_messages.columns:
                total_daily_messages = total_daily_messages.set_index("date")["total_messages"]
            else:
                total_daily_messages = total_daily_messages["total_messages"]
        else:
            total_daily_messages = total_daily_messages.iloc[:, 0]

    total_daily_messages = pd.Series(total_daily_messages).copy()
    total_daily_messages.name = "total_messages"

    if total_daily_messages.empty:
        return pd.Series(dtype="float64", name="total_messages")

    index = pd.to_datetime(total_daily_messages.index, errors="coerce", utc=True).tz_localize(None).floor("D")
    valid_dates = ~pd.isna(index)
    total_daily_messages = total_daily_messages[valid_dates]
    total_daily_messages.index = index[valid_dates]
    total_daily_messages = pd.to_numeric(total_daily_messages, errors="coerce").fillna(0)
    total_daily_messages = total_daily_messages.groupby(level=0).sum().astype(float).sort_index()
    total_daily_messages.index.name = "date"
    total_daily_messages.name = "total_messages"
    return total_daily_messages


def calculate_total_daily_messages(grouped_results):
    results = _normalise_grouped_results(grouped_results)
    if results.empty:
        return pd.Series(dtype="float64", name="total_messages")

    with_message_ids = results.dropna(subset=["_message_id"])
    if with_message_ids.empty:
        total_messages = results.groupby("_date").size().astype(float)
    else:
        by_channel = with_message_ids.groupby(["_date", "_channel_id"])["_message_id"].agg(["min", "max"])
        by_channel["message_count"] = by_channel["max"] - by_channel["min"] + 1
        total_messages = by_channel.groupby(level="_date")["message_count"].sum().astype(float)

    total_messages.index.name = "date"
    total_messages.name = "total_messages"
    return total_messages.sort_index()


def calculate_percentage_over_time(grouped_results, total_daily_messages=None):
    results = _normalise_grouped_results(grouped_results)
    columns = ["date", "search_term", "mentions", "total_messages", "percentage"]
    if results.empty:
        return pd.DataFrame(columns=columns)

    daily_mentions = results.groupby(["_date", "_search_term"]).size().rename("mentions")
    terms = sorted(results["_search_term"].unique())

    if total_daily_messages is None:
        total_daily_messages = calculate_total_daily_messages(grouped_results)
    else:
        total_daily_messages = _normalise_total_daily_messages(total_daily_messages)

    if total_daily_messages.empty:
        min_date = results["_date"].min()
        max_date = results["_date"].max()
    else:
        min_date = min(results["_date"].min(), total_daily_messages.index.min())
        max_date = max(results["_date"].max(), total_daily_messages.index.max())
    dates = pd.date_range(min_date, max_date, freq="D")

    full_index = pd.MultiIndex.from_product([dates, terms], names=["date", "search_term"])
    percentages = daily_mentions.reindex(full_index, fill_value=0).reset_index()

    total_daily_messages = total_daily_messages.reindex(dates, fill_value=0)
    percentages["total_messages"] = percentages["date"].map(total_daily_messages).astype(float)
    denominator = percentages["total_messages"].where(percentages["total_messages"] != 0)
    percentages["percentage"] = (100 * percentages["mentions"] / denominator).fillna(0.0)

    return percentages[columns]


def calculate_rolling_percentage_over_time(grouped_results, window_days=7, total_daily_messages=None):
    if window_days < 1:
        raise ValueError("window_days must be at least 1")

    daily_percentages = calculate_percentage_over_time(
        grouped_results,
        total_daily_messages=total_daily_messages,
    )
    columns = [
        "date",
        "search_term",
        "mentions",
        "total_messages",
        "rolling_mentions",
        "rolling_total_messages",
        "rolling_percentage",
    ]
    if daily_percentages.empty:
        return pd.DataFrame(columns=columns)

    rolling_frames = []
    for search_term, term_data in daily_percentages.groupby("search_term", sort=False):
        term_data = term_data.sort_values("date").copy()
        term_data["rolling_mentions"] = term_data["mentions"].rolling(window_days, min_periods=1).sum()
        term_data["rolling_total_messages"] = term_data["total_messages"].rolling(window_days, min_periods=1).sum()
        denominator = term_data["rolling_total_messages"].where(term_data["rolling_total_messages"] != 0)
        term_data["rolling_percentage"] = (100 * term_data["rolling_mentions"] / denominator).fillna(0.0)
        rolling_frames.append(term_data[columns])

    return pd.concat(rolling_frames, ignore_index=True)


def calculate_7_day_rolling_percentage(grouped_results, total_daily_messages=None):
    return calculate_rolling_percentage_over_time(
        grouped_results,
        window_days=7,
        total_daily_messages=total_daily_messages,
    )


def extract_wordcloud_text(grouped_results, text_column="message"):
    text_parts = []

    for _, frame in _iter_grouped_result_frames(grouped_results):
        if text_column not in frame.columns:
            continue

        for value in frame[text_column].dropna():
            if not isinstance(value, str):
                value = getattr(value, "message", value)
            if value is None:
                continue

            text = str(value).strip()
            if text:
                text_parts.append(text)

    return "\n".join(text_parts)


def generate_wordcloud_image(grouped_results, output_folder, *, filename=None, title="Wordcloud", search_term=None,
                             text_column="message", wordcloud_cls=None, wordcloud_kwargs=None):
    graph_type = "wordcloud"
    text = extract_wordcloud_text(grouped_results, text_column=text_column)

    if not text.strip():
        return build_graph_manifest_entry(
            graph_type,
            title=title,
            search_term=search_term,
            skipped=True,
            reason="empty_text",
            text_length=0,
            word_count=0,
        )

    if wordcloud_cls is None:
        try:
            from wordcloud import WordCloud

            wordcloud_cls = WordCloud
        except ImportError:
            return build_graph_manifest_entry(
                graph_type,
                title=title,
                search_term=search_term,
                skipped=True,
                reason="missing_dependency: wordcloud",
                text_length=len(text),
                word_count=len(text.split()),
            )

    kwargs = {
        "width": 1200,
        "height": 700,
        "background_color": "white",
    }
    if wordcloud_kwargs:
        kwargs.update(wordcloud_kwargs)

    cloud = wordcloud_cls(**kwargs).generate(text)
    image = cloud.to_array() if hasattr(cloud, "to_array") else cloud

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.imshow(image, interpolation="bilinear")
    ax.axis("off")

    filename = filename or safe_graph_filename("wordcloud", search_term or "all")
    filepath = Path(output_folder) / filename

    return save_matplotlib_figure(
        fig,
        filepath,
        graph_type=graph_type,
        title=title,
        search_term=search_term,
        text_length=len(text),
        word_count=len(text.split()),
    )


def plot_percentage_over_time(grouped_results, output_folder, total_daily_messages=None):
    percentages = calculate_percentage_over_time(
        grouped_results,
        total_daily_messages=total_daily_messages,
    )
    graph_type = "daily_percentage"
    title = "Daily Keyword Matches as Percentage of Estimated Daily Messages"

    if percentages.empty:
        return build_graph_manifest_entry(
            graph_type,
            title=title,
            skipped=True,
            reason="no_data",
        )

    fig, ax = plt.subplots(figsize=(14, 6))
    for search_term, term_data in percentages.groupby("search_term", sort=False):
        ax.plot(term_data["date"], term_data["percentage"], label=search_term)

    ax.set_xlabel("Date")
    ax.set_ylabel("Daily matches (%)")
    ax.set_title(title)
    ax.legend()

    filepath = Path(output_folder) / safe_graph_filename(graph_type)
    return save_matplotlib_figure(
        fig,
        filepath,
        graph_type=graph_type,
        title=title,
        rows=len(percentages),
    )


def plot_rolling_percentage_over_time(grouped_results, output_folder, window_days=7, total_daily_messages=None):
    percentages = calculate_rolling_percentage_over_time(
        grouped_results,
        window_days=window_days,
        total_daily_messages=total_daily_messages,
    )
    graph_type = f"rolling_{window_days}_day_percentage"
    title = f"{window_days}-Day Rolling Keyword Matches as Percentage of Estimated Daily Messages"

    if percentages.empty:
        return build_graph_manifest_entry(
            graph_type,
            title=title,
            skipped=True,
            reason="no_data",
            window_days=window_days,
        )

    fig, ax = plt.subplots(figsize=(14, 6))
    for search_term, term_data in percentages.groupby("search_term", sort=False):
        ax.plot(term_data["date"], term_data["rolling_percentage"], label=search_term)

    ax.set_xlabel("Date")
    ax.set_ylabel(f"{window_days}-day rolling matches (%)")
    ax.set_title(title)
    ax.legend()

    filepath = Path(output_folder) / safe_graph_filename(graph_type)
    return save_matplotlib_figure(
        fig,
        filepath,
        graph_type=graph_type,
        title=title,
        rows=len(percentages),
        window_days=window_days,
    )


def plot_keyword_frequency(all_results, dataframes_dict, output_folder, now):
    manifest = []

    try:
        _append_manifest_entry(manifest, plot_keyword_frequency_per_channel(dataframes_dict, output_folder))
    except Exception as e:
        print(f"Error making per-channel chart: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        _append_manifest_entry(manifest, plot_keyword_frequency_aggregate(dataframes_dict, output_folder))
    except Exception as e:
        print(f"Error making aggregate chart: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        _append_manifest_entry(manifest, plot_adjusted_keyword_frequency(dataframes_dict, output_folder, now))
    except Exception as e:
        print(f"Error making adjusted chart (normal scale): {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        _append_manifest_entry(manifest, plot_adjusted_keyword_frequency(dataframes_dict, output_folder, now, scale="log"))
    except Exception as e:
        print(f"Error making adjusted chart (log scale): {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        _append_manifest_entry(manifest, plot_percentage_over_time(dataframes_dict, output_folder))
    except Exception as e:
        print(f"Error making daily percentage chart: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        _append_manifest_entry(manifest, plot_rolling_percentage_over_time(dataframes_dict, output_folder))
    except Exception as e:
        print(f"Error making rolling percentage chart: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        _append_manifest_entry(
            manifest,
            generate_wordcloud_image(dataframes_dict, output_folder, title="Wordcloud of Matching Messages"),
        )
    except Exception as e:
        print(f"Error making wordcloud: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        generate_pdf(all_results, output_folder, dataframes_dict, now, graph_manifest=manifest)
    except Exception as e:
        print(f"Error making PDF: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    return manifest


def plot_keyword_frequency_per_channel(dataframes_dict, output_folder):
    min_date = None
    max_date = None
    manifest = []

    for search_term, dataframes in dataframes_dict.items():
        if not dataframes:
            continue
        all_results = pd.concat(dataframes, ignore_index=True)
        all_results['date'] = pd.to_datetime(all_results['time'].astype(str).str[:11].str.strip()).dt.tz_localize(
            None)

        if min_date is None or all_results['date'].min() < min_date:
            min_date = all_results['date'].min()

        if max_date is None or all_results['date'].max() > max_date:
            max_date = all_results['date'].max()

    for search_term, dataframes in dataframes_dict.items():
        if not dataframes:
            print(f"No data available for search term: {search_term}")
            manifest.append(
                build_graph_manifest_entry(
                    "message_count_per_day",
                    title=f'Number of Messages Returned Per Day for "{search_term}"',
                    search_term=search_term,
                    skipped=True,
                    reason="no_data",
                )
            )
            continue
        fig = plt.figure(figsize=(14, 6))

        all_results = pd.concat(dataframes, ignore_index=True)
        all_results['date'] = pd.to_datetime(all_results['time'].astype(str).str[:11].str.strip()).dt.tz_localize(
            None)

        daily_message_count = all_results.resample('D', on='date').size()
        plt.plot(daily_message_count.index, daily_message_count.values, label=search_term)

        if min_date is not None and max_date is not None:
            current_date = min_date.to_period('M').to_timestamp()
            while current_date < max_date:
                plt.axvline(current_date, color='gray', linestyle='--', linewidth=0.5)
                current_date += pd.DateOffset(months=1)

        plt.xlabel('Date')
        plt.ylabel('Number of Messages')
        title = f'Number of Messages Returned Per Day for "{search_term}"'
        plt.title(title)
        plt.legend()

        filename = safe_graph_filename("message_count_per_day", search_term)
        filepath = os.path.join(output_folder, filename)

        printC(f'Saving graph as image for "{search_term}"...', Fore.YELLOW)
        manifest.append(
            save_matplotlib_figure(
                fig,
                filepath,
                graph_type="message_count_per_day",
                title=title,
                search_term=search_term,
            )
        )
        printC(f'Saved Graph as image for "{search_term}".', Fore.GREEN)

    return manifest


def plot_keyword_frequency_aggregate(dataframes_dict, output_folder):
    fig = plt.figure(figsize=(14, 6))

    min_date, max_date = None, None
    search_terms_with_data = {term: dataframes for term, dataframes in dataframes_dict.items() if dataframes}

    if not search_terms_with_data:
        plt.close(fig)
        return build_graph_manifest_entry(
            "message_count_per_day",
            title="Number of Messages Returned Per Day (All Search Terms)",
            skipped=True,
            reason="no_data",
        )

    for search_term, dataframes in search_terms_with_data.items():
        current_results = pd.concat(dataframes, ignore_index=True)
        current_results['date'] = pd.to_datetime(
            current_results['time'].astype(str).str[:11].str.strip()).dt.tz_localize(None)

        if min_date is None or current_results['date'].min() < min_date:
            min_date = current_results['date'].min()

        if max_date is None or current_results['date'].max() > max_date:
            max_date = current_results['date'].max()

        daily_message_count = current_results.resample('D', on='date').size()
        plt.plot(daily_message_count.index, daily_message_count.values, label=search_term)

    current_date = min_date.to_period('M').to_timestamp()
    while current_date < max_date:
        plt.axvline(current_date, color='gray', linestyle='--', linewidth=0.5)
        current_date += pd.DateOffset(months=1)

    plt.xlabel('Date')
    plt.ylabel('Number of Messages')
    title = 'Number of Messages Returned Per Day (All Search Terms)'
    plt.title(title)
    plt.legend()

    filename = safe_graph_filename("message_count_per_day")
    filepath = os.path.join(output_folder, filename)

    printC('Saving graph as image...', Fore.YELLOW)
    entry = save_matplotlib_figure(
        fig,
        filepath,
        graph_type="message_count_per_day",
        title=title,
    )
    printC('Saved Aggregated Graph as image.', Fore.GREEN)

    return entry


def plot_adjusted_keyword_frequency(dataframes_dict, output_folder, now, scale="normal"):
    fig, ax = plt.subplots(figsize=(14, 6))

    daily_message_count = get_total_daily_messages(dataframes_dict)

    for search_term, dataframes in dataframes_dict.items():
        if dataframes:
            current_results = pd.concat(dataframes, ignore_index=True)
            current_results['date'] = pd.to_datetime(
                current_results['time'].astype(str).str[:11].str.strip()).dt.tz_localize(None)

            daily_mentions = current_results.resample('D', on='date').size().to_frame(name='mentions')

            adjusted_daily_mentions = daily_mentions.join(daily_message_count, how='outer')
            adjusted_daily_mentions['total_messages'] = adjusted_daily_mentions['total_messages'].ffill()
            adjusted_daily_mentions['mentions'] = adjusted_daily_mentions['mentions'].fillna(0)

            adjusted_daily_mentions['cumulative_mentions'] = adjusted_daily_mentions['mentions'].cumsum()
            adjusted_daily_mentions['cumulative_total_messages'] = adjusted_daily_mentions[
                'total_messages'].cumsum()

            adjusted_daily_mentions['ratio'] = 100 * adjusted_daily_mentions['cumulative_mentions'] / \
                                               adjusted_daily_mentions['cumulative_total_messages']

            ax.plot(adjusted_daily_mentions.index, adjusted_daily_mentions['ratio'], label=search_term)

    ax.set_xlabel('Date')
    ax.set_ylabel(f'Cumulative Mentions to Total Messages Ratio ({scale.capitalize()} Scale %)')

    if scale == "normal":
        ax.set_title('Adjusted Keyword Frequency - Proportion keyword matches vs total messages (Percentages)')
        ax.yaxis.set_major_locator(ticker.FixedLocator([100, 50, 10, 1]))
    else:
        ax.set_title(
            'Adjusted Keyword Frequency - Proportion keyword matches vs total messages - (Log Scale Percentages)')
        ax.yaxis.set_major_locator(ticker.FixedLocator([100, 10, 1, 0.1, 0.01]))
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'{x:,.2f} %'))
        ax.set_yscale('log')

    plt.setp(ax.get_yticklabels(), rotation=45, ha="right")

    ax.legend()

    title = ax.get_title()
    filename = safe_graph_filename("adjusted_keyword_frequency", now, scale)
    filepath = os.path.join(output_folder, filename)

    return save_matplotlib_figure(
        fig,
        filepath,
        graph_type="adjusted_keyword_frequency",
        title=title,
        scale=scale,
    )


def get_total_daily_messages(dataframes_dict):
    return calculate_total_daily_messages(dataframes_dict)


class NumberedDocTemplate(BaseDocTemplate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addPageTemplates([PageTemplate(id='All', frames=[self.createFrame()], onPage=self.addPageNumber)])

    def createFrame(self):
        return Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='normal')

    def addPageNumber(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawCentredString(105 * mm, 20 * mm, f"Page {canvas._pageNumber}")
        canvas.restoreState()


def generate_pdf(all_results, output_folder, dataframes_dict, now, graph_manifest=None):
    if isinstance(all_results, list):
        all_results = pd.DataFrame(all_results)

    pdf_filename = os.path.join(output_folder, f'Telegram_Keyword_Trends_Report_{now}.pdf')
    doc = NumberedDocTemplate(pdf_filename, pagesize=letter)

    num_results = len(all_results)
    number_of_results = f"Number of results: {num_results}"
    date_range = _result_date_range(all_results)
    date_range_of_results = f"Date range of results: {date_range[0]} - {date_range[1]}\n\n"

    title_style = ParagraphStyle('Title', fontSize=14, spaceAfter=16)
    subheading_style = ParagraphStyle('Subheading', fontSize=11, spaceAfter=8)
    intro_text_style = ParagraphStyle('IntroText', fontSize=9, spaceAfter=20)
    code_style = ParagraphStyle('Code', fontName='Courier', fontSize=8, spaceAfter=20)

    title = Paragraph(f"Telegram Keyword Trend Analysis {now}", title_style)
    subheading = Paragraph(
        "Digital scraping of Telegram channels to extract frequency and trends of keyword use",
        subheading_style,
    )

    intro_text = files("tg_keyword_trends").joinpath("report_template_text.txt").read_text(encoding="utf-8")
    intro_text = Paragraph(f"{intro_text}", intro_text_style)

    result_summary_number = Paragraph(f"{number_of_results}", intro_text_style)
    result_summary_date_range = Paragraph(f"{date_range_of_results}", intro_text_style)

    story = []

    story.append(title)
    story.append(subheading)
    story.append(intro_text)
    story.append(result_summary_number)
    story.append(result_summary_date_range)

    max_image_width = letter[0] - 2 * doc.leftMargin
    graph_entries = _graph_entries_for_pdf(graph_manifest, output_folder, dataframes_dict, now)
    if graph_entries:
        story.append(PageBreak())

    for graph_entry in graph_entries:
        image_path = graph_entry["path"]
        title = graph_entry.get("title") or graph_entry.get("type") or Path(image_path).name
        try:
            story.append(Spacer(1, 20))
            story.append(Paragraph(title, subheading_style))
            story.append(_pdf_image(image_path, max_image_width))
        except FileNotFoundError:
            print(f"Error: File '{image_path}' not found. Skipping this graph.")

    story.append(PageBreak())
    story.append(Paragraph("Code used", title_style))
    story.append(Paragraph("Repository source snapshot:", subheading_style))

    max_code_width = letter[0] - 2 * doc.leftMargin
    wrapped_content = ""
    for line in read_source_snapshot().split("\n"):
        wrapped_content += textwrap.fill(line, width=int(max_code_width / 6)) + "\n"

    story.append(Preformatted(wrapped_content, code_style))

    doc.build(story)
    printC('Generated PDF with all graphs.', Fore.GREEN)


def _result_date_range(all_results):
    if 'time' not in all_results or all_results.empty:
        return (None, None)
    return (all_results['time'].min(), all_results['time'].max())


def _graph_entries_for_pdf(graph_manifest, output_folder, dataframes_dict, now):
    if graph_manifest:
        entries = []
        seen_paths = set()
        for entry in graph_manifest:
            if entry.get("skipped") or not entry.get("path"):
                continue

            path = str(entry["path"])
            if path in seen_paths:
                continue

            seen_paths.add(path)
            entries.append(entry)
        return entries

    fallback_entries = [
        build_graph_manifest_entry(
            "message_count_per_day",
            Path(output_folder) / safe_graph_filename("message_count_per_day"),
            title="Number of Messages Returned Per Day (All Search Terms)",
        )
    ]

    for search_term in dataframes_dict.keys():
        fallback_entries.append(
            build_graph_manifest_entry(
                "message_count_per_day",
                Path(output_folder) / safe_graph_filename("message_count_per_day", search_term),
                title=f'Number of Messages Returned Per Day for "{search_term}"',
                search_term=search_term,
            )
        )

    for scale in ["normal", "log"]:
        fallback_entries.append(
            build_graph_manifest_entry(
                "adjusted_keyword_frequency",
                Path(output_folder) / safe_graph_filename("adjusted_keyword_frequency", now, scale),
                title=f"Adjusted Keyword Frequency ({scale.capitalize()} Scale)",
                scale=scale,
            )
        )

    return fallback_entries


def _pdf_image(image_path, max_image_width):
    with PILImage.open(image_path) as pil_image:
        image_width, image_height = pil_image.size

    image_ratio = image_height / image_width
    new_width = max_image_width
    new_height = max_image_width * image_ratio
    return Image(str(image_path), width=new_width, height=new_height)


def read_source_snapshot():
    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parents[1] if package_dir.parent.name == "src" else package_dir.parent

    source_paths = []
    root_entrypoint = repo_root / "main.py"
    if root_entrypoint.exists():
        source_paths.append(root_entrypoint)
    source_paths.extend(sorted(package_dir.glob("*.py")))

    chunks = []
    for source_path in source_paths:
        if source_path.exists():
            relative_path = source_path.relative_to(repo_root) if source_path.is_relative_to(repo_root) else source_path.name
            chunks.append(f"# {relative_path}")
            chunks.append(source_path.read_text(encoding="utf-8"))

    return "\n\n".join(chunks)
