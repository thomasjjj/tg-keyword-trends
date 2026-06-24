import asyncio
import os
import re
import threading
import time as t
import traceback

import pandas as pd
import pytz
from colorama import Fore
from tqdm import tqdm

from .auth import connect_to_telegram
from .channels import render_message_link, select_channels
from .console import printC
from .constants import SCRIPT_DESCRIPTION, SCRIPT_WARNING
from .files import check_search_terms_file, create_output_directory, open_file_dialog, open_folder_dialog, render_url
from .inputs import flatten_search_term_groups, parse_search_term_groups, prompt_date_range
from .plotting import plot_keyword_frequency
from .progress import progress_display
from .reports import generate_txt_report


def main():
    return run_async(async_main())


def run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {}

    def run_in_thread():
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            result["exception"] = exc

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()

    if "exception" in result:
        raise result["exception"]
    return result.get("value")


async def async_main():
    now = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    printC(SCRIPT_DESCRIPTION, Fore.LIGHTYELLOW_EX)
    printC(SCRIPT_WARNING, Fore.LIGHTRED_EX)

    client = await connect_to_telegram()

    try:
        await run_search_workflow(client, now)
    finally:
        await client.disconnect()


async def run_search_workflow(client, now):
    dialogs = await client.get_dialogs()
    channel_selection = await select_channels(client, dialogs)
    channels = channel_selection.targets

    all_results = pd.DataFrame(
        columns=[
            'time',
            'message',
            'message_id',
            'channel_id',
            'channel_title',
            'search_group',
            'search_term',
            'link',
        ]
    )

    printC(
        'Select the .txt file with search terms. Use one term per line or "Group: term | term" for grouped terms.',
        Fore.BLUE,
    )
    search_terms_file = open_file_dialog()
    search_term_groups = parse_search_term_groups(check_search_terms_file(search_terms_file))
    if not search_term_groups:
        raise ValueError("Search terms file does not contain any active search terms.")
    search_terms = flatten_search_term_groups(search_term_groups)
    dataframes_dict = {search_group.label: [] for search_group in search_term_groups}

    count, start_time, total_channels = 0, t.time(), len(channels)

    reset_colour = '\033[0m'
    green_colour = '\033[32m'
    yellow_colour = '\033[33m'

    date_range = prompt_date_range(timezone=pytz.UTC)
    start_date, end_date = date_range

    download_media = input("Do you want to download media files? (yes/no): ").strip().lower()

    if download_media == 'yes':
        print("Select the folder to save media files.")
        media_folder_path = open_folder_dialog()

    for channel_target in channels:
        count = count + 1
        channel = channel_target.entity
        channel_id = channel_target.channel_id

        channels_progress = str(count) + "/" + str(total_channels)
        print(channels_progress + " | Searching Channel: " + f"{channel_target.title}")

        for search_group in search_term_groups:
            for search_string in search_group.terms:
                display_search = (
                    f"{search_group.label} / {search_string}"
                    if search_group.label != search_string
                    else search_string
                )
                print(f"{yellow_colour}Searching term: {reset_colour}" + display_search + "... [RUNNING]", end='',
                      flush=True)

                messages, time, message_ids = [], [], []

                pattern = re.compile(search_string, re.IGNORECASE)
                search_string = pattern.pattern

                async for message in client.iter_messages(channel, search=search_string):
                    if (start_date is None or message.date >= start_date) and (
                            end_date is None or message.date <= end_date):

                        message_text = message.message

                        if download_media == 'yes' and message.media:
                            media_path = os.path.join(media_folder_path,
                                                      f'media export - tg-keyword-trends - {now}')
                            if not os.path.exists(media_path):
                                os.makedirs(media_path)
                            try:
                                filename = f"{channel_id}_{message.id}"
                                file_path = os.path.join(media_path, filename)
                                with tqdm(desc=f"Downloading {filename}", total=1, unit="B", unit_scale=True) as pbar:
                                    def callback(update_bytes, total_bytes):
                                        pbar.update(update_bytes - pbar.n)

                                    await client.download_media(message, file_path, progress_callback=callback)
                            except Exception as e:
                                print(f"\rError downloading media file: {e}  ", flush=True)

                        messages.append(message_text)
                        time.append(message.date)
                        message_ids.append(message.id)

                if messages:
                    links = [render_message_link(channel_id, message_id) for message_id in message_ids]
                    data = {
                        'time': time,
                        'message': messages,
                        'message_id': message_ids,
                        'channel_id': channel_id,
                        'channel_title': channel_target.title,
                        'search_group': search_group.label,
                        'search_term': search_string,
                        'link': links,
                    }
                    df = pd.DataFrame(data)

                    print(
                        f'\r{reset_colour}OK{green_colour} Searched term: {reset_colour}{display_search} - {green_colour}Results: {len(messages)}{reset_colour}',
                        flush=True)

                    all_results = pd.concat([all_results, df], ignore_index=True)
                    dataframes_dict[search_group.label].append(df)
                else:
                    print(
                        f'\r{reset_colour}OK{green_colour} Searched term: {reset_colour}{display_search} - {yellow_colour}No results{reset_colour}',
                        flush=True)

                t.sleep(1)

        progress_display(start_time, total_channels, count)

    try:
        output_folder = create_output_directory(f'TG-Search_{now}')

        filename_html = os.path.join(output_folder, f'all_results__{now}.html')
        filename_csv = os.path.join(output_folder, f'all_results__{now}.csv')
        filename_json = os.path.join(output_folder, f'all_results__{now}.json')

        try:
            try:
                with open(filename_html, 'w', encoding='utf-8') as f:
                    printC('Making HTML output file...', Fore.YELLOW)
                    print("DataFrame before exporting to HTML:")
                    print(all_results)
                    html = all_results.to_html(index=False, formatters={'link': render_url}, escape=False)
                    f.write(html)
                    printC(f"Saved {filename_html}", Fore.GREEN)
            except IOError as e:
                print(f'Error making HTML file: {e}')
                traceback.print_exc()

            try:
                printC('Exporting to csv...', Fore.YELLOW)
                all_results.to_csv(filename_csv, index=False, encoding='utf-8')
                printC(f"Saved {filename_csv}", Fore.GREEN)
            except IOError as e:
                print(f'Error making CSV: {e}')
                traceback.print_exc()

            try:
                printC('Exporting to json...', Fore.YELLOW)
                all_results.to_json(filename_json, orient='records', indent=4, force_ascii=False)
                printC(f"Saved {filename_json}", Fore.GREEN)
            except IOError as e:
                print(f'Error making JSON: {e}')
                traceback.print_exc()

            plot_keyword_frequency(all_results, dataframes_dict, output_folder, now)

            try:
                printC('Generating .txt report...', Fore.YELLOW)
                generate_txt_report(all_results, channels, search_term_groups, output_folder, now)
                printC('Report .txt generated.', Fore.GREEN)
            except Exception as e:
                print(f'Error generating .txt report: {e}')
                traceback.print_exc()

        except ValueError:
            printC('Error.', Fore.RED)
            traceback.print_exc()

    except ValueError:
        printC('Error.', Fore.RED)

    printC('\nProcess completed', Fore.GREEN)
