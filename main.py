import os
import re
import sys
import time as t
from collections import Counter
import traceback
import pandas as pd
from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerChannel
from colorama import Style, Fore
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog


description = r"""

 _____    _                                  _____                  _     
|_   _|  | |                                |_   _|                | |    
  | | ___| | ___  __ _ _ __ __ _ _ __ ___     | |_ __ ___ _ __   __| |___ 
  | |/ _ \ |/ _ \/ _` | '__/ _` | '_ ` _ \    | | '__/ _ \ '_ \ / _` / __|
  | |  __/ |  __/ (_| | | | (_| | | | | | |   | | | |  __/ | | | (_| \__ \
  \_/\___|_|\___|\__, |_|  \__,_|_| |_| |_|   \_/_|  \___|_| |_|\__,_|___/
                  __/ |                                                   
                 |___/                                                    
By: Tom Jarvis ¦ Twitter: @tomtomjarvis
---------------------------------------
This script searches messages containing specified search terms in Telegram channels the user is a member of.
It exports the search results in HTML and CSV formats, generates a report, and plots the message count per day."""

WARNING = r"""
WARNING: This tool uses your list of followed groups as the list it searches from. It may include personal chats/groups.
         For the sake of OPSEC, it is recommended to use a burner account and follow only investigation-specific chats.
"""

def print_coloured(string, colour):
    print(colour + string + Style.RESET_ALL)

def connect_to_telegram():
    def retrieve_api_details():
        """
        Reads the API ID and API hash values from a file named 'api_values.txt'. If the file does not exist,
        the function sets default values for the API ID and API hash and creates the file.

        If the file does exist, the function reads the values from the file and returns them.

        Returns:
            tuple: A tuple containing the API ID (an integer) and API hash (a string) values.
        """

        api_details_file_path = 'api_values.txt'

        if not os.path.exists(api_details_file_path):
            print_coloured('No API details found. Please follow the instructions. This should be a one-time setup.',
                           Fore.YELLOW)
            api_id = input('Type your API ID: ')
            api_hash = input('Type your API Hash: ')

            with open(api_details_file_path, 'w') as file:
                file.write(f'api_id:\n{api_id}\n')
                file.write(f'api_hash:\n{api_hash}')
        else:
            with open(api_details_file_path, 'r') as file:
                lines = file.readlines()
                api_id = int(lines[1])
                api_hash = lines[3].strip()

        print(f'API ID retrieved: {api_id} ¦ API Hash retrieved: {api_hash}\n')
        return api_id, api_hash

    def attempt_connection():
        api_id, api_hash = retrieve_api_details()
        client = TelegramClient('session_name', api_id, api_hash)
        if not client.start():
            sys.exit("Error connecting to Telegram client. Please fix API details in api_values.txt and restart.")
        return client

    client = attempt_connection()
    return client

def progress_display(start_time, total_channels, count):
    '''
    Displays the progress of a process by showing a progress bar, percentage,
    elapsed time, and estimated time remaining.

    :param start_time: float, the starting time of the process (in seconds since the epoch)
    :param total_channels: int, the total number of channels the process needs to handle
    :param count: int, the number of channels processed so far
    :return: None
    '''

    def seconds_to_hms(seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return h, m, s

    # Calculate ETA
    elapsed_time = t.time() - start_time
    average_time_per_channel = elapsed_time / count
    remaining_channels = total_channels - count
    estimated_remaining_time = remaining_channels * average_time_per_channel
    h, m, s = seconds_to_hms(estimated_remaining_time)
    elapsed_h, elapsed_m, elapsed_s = seconds_to_hms(elapsed_time)
    total_time = elapsed_time + estimated_remaining_time
    progress_percentage = elapsed_time / total_time

    # Generate a 24-character progress bar
    progress_bar_length = 74
    filled_length = int(progress_percentage * progress_bar_length)
    progress_bar = '█' * filled_length + '-' * (progress_bar_length - filled_length)

    time_message = f"Processed {count}/{total_channels} channels. Time elapsed: {elapsed_h:02d}:{elapsed_m:02d}:{elapsed_s:02d}. ETA: {h:02d}:{m:02d}:{s:02d}."
    progress_message = f"Progress: |{progress_bar}| {progress_percentage * 100:.1f}%"
    print_coloured(time_message, Fore.CYAN)
    print_coloured(progress_message, Fore.CYAN)

def create_output_directory(directory_name):
    os.makedirs(directory_name, exist_ok=True)
    print('Directory created.')
    return directory_name

def open_file_dialog():
    """
   Opens a file dialog to allow the user to select a .txt file.

   The function creates a hidden Tkinter window, brings it to the top, and opens a file dialog.
   The file dialog is restricted to selecting .txt files. Once the user selects a file and closes
   the dialog, the function destroys the hidden Tkinter window and returns the selected file path.

   Returns:
       str: The path of the selected .txt file.
   """
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.wm_attributes('-topmost', True)  # Make the window appear on top
    file_path = filedialog.askopenfilename(title="Select the search terms file", filetypes=[("Text files", "*.txt")])
    root.destroy()  # Destroy the window after the dialog is closed
    if not file_path:  # Check if file_path is empty
        sys.exit("Process cancelled.")  # cancel the process if user clicks file dialogue "cancel"
    return file_path

def check_search_terms_file(file_path):
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8'):
            print(f"Created a new file '{file_path}'. Please add your search terms, one per line.")
            print("Press Ctrl+C or close the program to stop.")

    with open(file_path, 'r', encoding='utf-8') as f:
        search_terms = f.read().splitlines()

    if not search_terms:
        print("The search terms file is empty. Please enter a search term:")
        new_term = input().strip()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_term + '\n')
        search_terms = [new_term]
    else:
        print_coloured('Search terms TXT file found\n', Fore.GREEN)

    return search_terms

def render_url(url):
    """Return an HTML link for a given URL."""
    return f'<a href="{url}">{url}</a>'

def plot_keyword_frequency(dataframes_dict, output_folder):
    """
    Creates a line plot of the frequency of each keyword over time, based on a dictionary of Pandas DataFrames.

    The function concatenates all DataFrames for each keyword, resamples the data by day, and plots the count of messages
    per day. The resulting plot is saved as a PNG file in the specified output directory.

    Args:
        dataframes_dict (dict): A dictionary where each key is a search term and each value is a list of Pandas DataFrames
                                containing the search results for that term.
        output_folder (str): The path to the directory where the output file should be saved.
    """
    plt.figure(figsize=(14, 6))

    min_date = None
    max_date = None

    # Iterate through each search term and its corresponding DataFrames
    for search_term, dataframes in dataframes_dict.items():
        # Concatenate all DataFrames for the current search term
        all_results = pd.concat(dataframes, ignore_index=True)

        # Extract the date from the 'time' column and convert it to a pandas datetime object
        all_results['date'] = pd.to_datetime(all_results['time'].str[:11], format='%d/%b/%Y')

        # Update min and max dates
        if min_date is None or all_results['date'].min() < min_date:
            min_date = all_results['date'].min()

        if max_date is None or all_results['date'].max() > max_date:
            max_date = all_results['date'].max()

        # Resample the DataFrame by day and count the number of messages per day
        daily_message_count = all_results.resample('D', on='date').size()

        # Plot the message count per day for the current search term
        plt.plot(daily_message_count.index, daily_message_count.values, label=search_term)

    # Add vertical lines for each month
    current_date = min_date.to_period('M').to_timestamp()
    while current_date < max_date:
        plt.axvline(current_date, color='gray', linestyle='--', linewidth=0.5)
        current_date += pd.DateOffset(months=1)

    plt.xlabel('Date')
    plt.ylabel('Number of Messages')
    plt.title('Number of Messages Returned Per Day')
    plt.legend()

    # Save the plot to a file in the output directory
    filename = 'message_count_per_day.png'
    filepath = os.path.join(output_folder, filename)

    print_coloured('Saving graph as image...', Fore.YELLOW)
    plt.savefig(filepath)
    print_coloured('Saved Graph as image.', Fore.GREEN)

    plt.show(block=False)


    # Idiot alert - I spent hours debugging the code because it didn't work after this stage.
    # The block=false is mandatory, so it runs in the background while the graph shows

def generate_report(all_results, channels, search_terms, output_folder, now):
    """
    Generates a text report summarizing the search results for a list of channels and search terms.

    The function creates a new text file in the specified output folder and writes various summary statistics
    and information to the file, including the project date, the channels searched, the search terms used, summary stats
    on the search results (e.g. number of results, date range), and a table of the most common channels.

    Args:
        all_results (pandas.DataFrame): A Pandas DataFrame containing all search results.
        channels (list): A list of dictionaries, where each dictionary represents a Telegram channel and contains
                         information about the channel ID and title.
        search_terms (list): A list of strings representing the search terms used.
        output_folder (str): The path to the directory where the output file should be saved.
        now (str): A string representing the current date and time in ISO format (YYYY-MM-DD HH:MM:SS).
    """
    print(f"Generating report for {len(channels)} channels and {len(search_terms)} search terms...")
    output_file = os.path.join(output_folder, f'report_{now}.txt')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Project Date\n")
        f.write(f"{now}\n\n")

        f.write("Summary Stats\n")
        num_results = len(all_results)
        date_range = (all_results['time'].min(), all_results['time'].max())
        f.write(f"Number of results: {num_results}\n")
        f.write(f"Date range of results: {date_range[0]} - {date_range[1]}\n\n")

        f.write("Channels Searched\n")
        for channel in channels:
            f.write(f"{channel.title}\n")
        f.write("\n")

        f.write("Search Terms Used\n")
        for term in search_terms:
            f.write(f"{term}\n")
        f.write("\n")

        f.write("Most Common Channels\n")
        channel_counts = Counter(all_results['channel_id']).most_common()
        for channel_id, count in channel_counts:
            f.write(f"Channel ID: {channel_id}, Count: {count}\n")

    print(f"Saved {output_file}")


########################################################################
print_coloured(description, Fore.LIGHTYELLOW_EX)
print_coloured(WARNING, Fore.LIGHTRED_EX)
client = connect_to_telegram()

# Create an empty DataFrame to store the results
all_results = pd.DataFrame(columns=['time', 'message', 'message_id', 'channel_id', 'search_term', 'link'])

# Get all the channels you are a member of
dialogs = client.get_dialogs()

print_coloured('Select the .txt file with search terms.'
              'Each search term should be on a new line.', Fore.BLUE)

# search_terms_file = 'search_terms.txt'  # Commented out to allow for file search dialogue
search_terms_file = open_file_dialog()  # Open TKinter file dialogue -- switch with line above for txt file in directory

search_terms = check_search_terms_file(search_terms_file)

# Initialize dataframes_dict with empty lists
dataframes_dict = {search_term: [] for search_term in search_terms}

count = 0
total_channels = sum(1 for dialog in dialogs if dialog.is_channel)
start_time = t.time()

# colour codes assigned for readability (call the escape sequences with {colour_name} in string
reset_colour = '\033[0m'
green_colour = '\033[32m'
yellow_colour = '\033[33m'
pink_colour = '\x1b[38;2;255;20;147m'


# Iterate over each channel and process its messages
for dialog in dialogs:

    if dialog.is_channel:
        count = count + 1
        # Get the channel's InputPeerChannel object
        channel = client.get_input_entity(dialog)

        # ---- Select what reporting information you want
        # print(str(count) + "¦ Searching..." + str(channel) + f"{dialog.title}")  # Channel ID details & Channel Name
        # print(str(count) + "¦ Searching..." + str(channel))  # Just Channel ID details
        print(str(count) + "/" + str(total_channels) + "¦ Searching Channel: " + f"{dialog.title}")  # Just Channel name

        for search_string in search_terms:
            # Prints the "searching" statement and allows it to be overwritten
            print(f"{yellow_colour}Searching term: {reset_colour}" + search_string + "... [RUNNING]", end='', flush=True)

            messages = []
            time = []
            message_ids = []
            # Perform a case-insensitive search using regular expressions
            pattern = re.compile(search_string, re.IGNORECASE)
            # Convert the pattern to a string
            search_string = pattern.pattern

            for message in client.iter_messages(channel, search=search_string):
                messages.append(message.message)    # get messages
                time.append(message.date)           # get timestamp
                message_ids.append(message.id)

            if messages:  # If messages list is not empty
                channel_id = channel.channel_id if channel.channel_id else channel.chat_id
                data = {'time': time, 'message': messages, 'message_id': message_ids, 'channel_id': channel_id}
                data['search_term'] = search_string  # Add the search term to the data
                df = pd.DataFrame(data)
                df['link'] = 'https://t.me/c/' + str(channel_id) + '/' + df['message_id'].astype(str)
                df['time'] = df['time'].apply(lambda x: x.strftime('%d/%b/%Y'))

                # Overwrites the "searching" statement and adds a white tick at the start with retrieved results
                print(
                    f'\r{reset_colour}✓{green_colour}Searched term: {reset_colour}{search_string} - {green_colour}Results: {len(messages)}{reset_colour}', flush=True)

                # --- Uncomment for printing the dataframes (not recommended as it is messy)
                # print(f"{dialog.title}")
                # print(df[['time', 'message', 'link']])

                # Append the results to the all_results DataFrame
                all_results = pd.concat([all_results, pd.DataFrame(data)], ignore_index=True)
                # Add the current DataFrame to the list
                dataframes_dict[search_string].append(df)  # This line is modified
                # Wait for 1 seconds to avoid rate limits
                t.sleep(1)

            else:
                # Overwrites the "searching" statement and adds a white tick at the start with "No Results""
                print(f'\r{reset_colour}✓{green_colour}Searched term: {reset_colour}{search_string} - {yellow_colour}No results{reset_colour}', flush=True)

        # Run the ETA
        progress_display(start_time, total_channels, count)  # Runs the progress bar and the ETA


        # Print a nice pink separator
        print(f'{pink_colour}-------------------------------------------------------------------------------------------' + '\x1b[0m')


try:

    now = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    output_folder = create_output_directory(f'TG-Search_{now}')

    filename_html = os.path.join(output_folder, f'all_results__{now}.html')
    filename_csv = os.path.join(output_folder, f'all_results__{now}.csv')
    filename_png = os.path.join(output_folder, f'keyword_frequency__{now}.png')

    try:
        # Export to HTML
        try:
            with open(filename_html, 'w', encoding='utf-8') as f:
                print_coloured('Making HTML output file...', Fore.YELLOW)
                html = all_results.to_html(index=False, formatters={'link': render_url}, escape=False)
                f.write(html)
                print_coloured(f"Saved {filename_html}", Fore.GREEN)
        except IOError as e:
            print(f'Error making HTML file: {e}')

        # Export to a CSV
        try:
            print_coloured('Exporting to csv...', Fore.YELLOW)
            all_results.to_csv(filename_csv, index=False, encoding='utf-8')
            print_coloured(f"Saved {filename_csv}", Fore.GREEN)
        except IOError as e:
            print(f'Error making CSV: {e}')

        # plot time graph
        try:
            plot_keyword_frequency(dataframes_dict, output_folder)
        except Exception as e:
            print(f'Error making chart: {e}')

        # Generate the report
        try:
            print_coloured('Generating report...', Fore.YELLOW)
            channels = [dialog for dialog in dialogs if dialog.is_channel]
            generate_report(all_results, channels, search_terms, output_folder, now)
            print_coloured('Report generated.', Fore.GREEN)
        except Exception as e:
            print(f'Error generating report: {e}')
            traceback.print_exc()

    except ValueError as e:
        print_coloured('Error.', Fore.RED)


except ValueError as e:
    print_coloured('Error.', Fore.RED)

print_coloured('\nProcess completed', Fore.GREEN)

# Disconnect the Telethon client from the Telegram server
client.disconnect()
