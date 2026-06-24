import os
import textwrap
import traceback
from importlib.resources import files
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from PIL import Image as PILImage
from colorama import Fore
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph, Preformatted, Spacer

from .console import printC


def plot_keyword_frequency(all_results, dataframes_dict, output_folder, now):
    try:
        plot_keyword_frequency_per_channel(dataframes_dict, output_folder)
    except Exception as e:
        print(f"Error making per-channel chart: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        plot_keyword_frequency_aggregate(dataframes_dict, output_folder)
    except Exception as e:
        print(f"Error making aggregate chart: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        plot_adjusted_keyword_frequency(dataframes_dict, output_folder, now)
    except Exception as e:
        print(f"Error making adjusted chart (normal scale): {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        plot_adjusted_keyword_frequency(dataframes_dict, output_folder, now, scale="log")
    except Exception as e:
        print(f"Error making adjusted chart (log scale): {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    try:
        generate_pdf(all_results, output_folder, dataframes_dict, now)
    except Exception as e:
        print(f"Error making PDF: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()


def plot_keyword_frequency_per_channel(dataframes_dict, output_folder):
    min_date = None
    max_date = None

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
            continue
        plt.figure(figsize=(14, 6))

        all_results = pd.concat(dataframes, ignore_index=True)
        all_results['date'] = pd.to_datetime(all_results['time'].astype(str).str[:11].str.strip()).dt.tz_localize(
            None)

        daily_message_count = all_results.resample('D', on='date').size()
        plt.plot(daily_message_count.index, daily_message_count.values, label=search_term)

        current_date = min_date.to_period('M').to_timestamp()
        while current_date < max_date:
            plt.axvline(current_date, color='gray', linestyle='--', linewidth=0.5)
            current_date += pd.DateOffset(months=1)

        plt.xlabel('Date')
        plt.ylabel('Number of Messages')
        plt.title(f'Number of Messages Returned Per Day for "{search_term}"')
        plt.legend()

        filepath = os.path.join(output_folder, f'message_count_per_day_{search_term}.png')

        printC(f'Saving graph as image for "{search_term}"...', Fore.YELLOW)
        plt.savefig(filepath)
        printC(f'Saved Graph as image for "{search_term}".', Fore.GREEN)

        plt.show(block=False)


def plot_keyword_frequency_aggregate(dataframes_dict, output_folder):
    plt.figure(figsize=(14, 6))

    min_date, max_date = None, None
    search_terms_with_data = {term: dataframes for term, dataframes in dataframes_dict.items() if dataframes}

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
    plt.title('Number of Messages Returned Per Day (All Search Terms)')
    plt.legend()

    filepath = os.path.join(output_folder, 'message_count_per_day.png')

    printC('Saving graph as image...', Fore.YELLOW)
    plt.savefig(filepath)
    printC('Saved Aggregated Graph as image.', Fore.GREEN)

    plt.show(block=False)


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

    filepath = os.path.join(output_folder, f'adjusted_keyword_frequency_{now}_{scale}.png')

    plt.savefig(filepath)
    plt.show(block=False)


def get_total_daily_messages(dataframes_dict):
    all_messages = pd.DataFrame()

    for search_term, dataframes in dataframes_dict.items():
        for df in dataframes:
            current_results = df.copy()
            current_results['id'] = current_results['message'].apply(lambda msg: msg.id)
            current_results['date'] = pd.to_datetime(
                current_results['time'].astype(str).str[:11].str.strip()).dt.tz_localize(None)
            all_messages = pd.concat([all_messages, current_results], ignore_index=True)

    daily_message_count = all_messages.resample('D', on='date')['id'].agg(lambda x: x.max() - x.min() + 1)
    daily_message_count.name = 'total_messages'
    return daily_message_count


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


def generate_pdf(all_results, output_folder, dataframes_dict, now):
    if isinstance(all_results, list):
        all_results = pd.DataFrame(all_results)

    pdf_filename = os.path.join(output_folder, f'Telegram_Keyword_Trends_Report_{now}.pdf')
    doc = NumberedDocTemplate(pdf_filename, pagesize=letter)

    num_results = len(all_results)
    number_of_results = f"Number of results: {num_results}"
    date_range = (all_results['time'].min(), all_results['time'].max())
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

    story.append(PageBreak())

    aggregated_image_path = os.path.join(output_folder, 'message_count_per_day.png')

    pil_image = PILImage.open(aggregated_image_path)
    max_image_width = letter[0] - 2 * doc.leftMargin
    image_width, image_height = pil_image.size
    image_ratio = image_height / image_width
    new_width = max_image_width
    new_height = max_image_width * image_ratio
    aggregated_image = Image(aggregated_image_path, width=new_width, height=new_height)

    story.append(aggregated_image)

    for search_term in dataframes_dict.keys():
        image_filename = f'message_count_per_day_{search_term}.png'
        image_path = os.path.join(output_folder, image_filename)

        try:
            pil_image = PILImage.open(image_path)
            image_width, image_height = pil_image.size

            image_ratio = image_height / image_width
            new_width = max_image_width
            new_height = max_image_width * image_ratio

            image = Image(image_path, width=new_width, height=new_height)

            story.append(Spacer(1, 20))
            story.append(image)
        except FileNotFoundError:
            print(f"Error: File '{image_path}' not found. Skipping this search term.")

    for scale in ["normal", "log"]:
        image_filename = f'adjusted_keyword_frequency_{now}_{scale}.png'
        image_path = os.path.join(output_folder, image_filename)

        try:
            pil_image = PILImage.open(image_path)
            image_width, image_height = pil_image.size

            image_ratio = image_height / image_width
            new_width = max_image_width
            new_height = max_image_width * image_ratio

            image = Image(image_path, width=new_width, height=new_height)

            story.append(Spacer(1, 20))
            story.append(Paragraph(f"Adjusted Keyword Frequency ({scale.capitalize()} Scale):", subheading_style))
            story.append(image)
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
