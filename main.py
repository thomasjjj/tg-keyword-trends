import os
import re
import sys
import time as t
from _ast import pattern
import datetime
from collections import Counter
import traceback

import pandas as pd
from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerChannel
from colorama import Style, Fore
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import tkinter as tk
from tkinter import filedialog


"""
This script searches messages containing specified search terms in Telegram channels the user is a member of.
It exports the search results in HTML and CSV formats, generates a report, and plots the message count per day.

WARNING: This tool uses your list of followed groups as the list it searches from. It may include personal chats/groups.
         For the sake of OPSEC, it is recommended to use a burner account and follow only investigation-specific chats.

Usage:
1. Add your API ID and API Hash as plain text in 'api_details.txt'.
2. Add the list of search terms, one per line, in 'search_terms.txt'.
3. The script will search through all the channels the user is a member of.
4. The search results will be exported as HTML and CSV files in a timestamped output folder.
5. The script will generate a report containing the search results for each channel.
6. The script will plot the message count per day for each search term in a graph and save it as an image.

Functions:
- retrieve_api_details: Read API details from 'api_details.txt'.
- check_search_terms_file: Read search terms from 'search_terms.txt' or prompt the user to enter search terms.
- create_output_directory: Create a timestamped directory for storing output files.
- print_colored: Print text in specified color using the colorama module.
- render_url: Generate HTML code for a hyperlink using a URL and message text.
- generate_report: Generate a report containing search results for each channel.
- plot_keyword_frequency: Plot the message count per day for each search term in a graph.

Dependencies:
- Telethon
- pandas
- matplotlib
- colorama
- regex
- reportlab


Python Version:
- Python 3.11 or higher
"""
def print_colored(string, color):
    print(color + string + Style.RESET_ALL)


def create_output_directory(directory_name):
    os.makedirs(directory_name, exist_ok=True)
    print('Directory created.')
    return directory_name

def open_file_dialog():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.wm_attributes('-topmost', True)  # Make the window appear on top
    file_path = filedialog.askopenfilename(title="Select the search terms file")
    root.destroy()  # Destroy the window after the dialog is closed
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
        print_colored('search_terms.txt found', Fore.GREEN)

    return search_terms


def render_url(url):
    """Return an HTML link for a given URL."""
    return f'<a href="{url}">{url}</a>'


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
        print_colored('No API details found. Please follow the instructions. This should be a one-time setup.', Fore.YELLOW)
        api_id = input('Type your API ID: ')
        api_hash = input('Type your API Hash: ')

        with open(api_details_file_path, 'w') as file:
            file.write('api_id:\n' + str(api_id) + '\n')
            file.write('api_hash:\n' + api_hash)

    else:
        with open(api_details_file_path, 'r') as file:
            lines = file.readlines()
            api_id = int(lines[1])
            api_hash = lines[3].strip()

    print('API ID retrieved: ' + str(api_id) + " ¦ API Hash retrieved: " + api_hash + "\n")
    return api_id, api_hash


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

    print_colored('Saving graph as image...', Fore.YELLOW)
    plt.savefig(filepath)
    print_colored('Saved Graph as image.', Fore.GREEN)

    plt.show(block=False)


    # Idiot alert - I spent hours debugging the code because it didn't work after this stage.
    # The block=false is mandatory so it runs in the background while the graph shows


def generate_report(all_results, channels, search_terms, output_folder, now):
    """
    Generates a PDF report summarizing the search results for a list of channels and search terms.

        The function creates a new PDF file in the specified output folder, and adds various summary statistics
        and tables to the file, including the project date, the channels searched, the search terms used, summary stats
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
    output_file = os.path.join(output_folder, f'report_{now}.pdf')
    doc = SimpleDocTemplate(output_file, pagesize=letter)

    # Styles for the report
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Heading', fontSize=14, leading=16, spaceAfter=6))
    styles.add(ParagraphStyle(name='List', fontSize=10, leftIndent=20, spaceAfter=6))

    report = []

    # Project date
    report.append(Paragraph("Project Date", styles['Heading']))
    report.append(Paragraph(now, styles['List']))

    # Channels searched
    report.append(Paragraph("Channels Searched", styles['Heading']))
    for channel in channels:
        report.append(Paragraph(channel.title, styles['List']))

    # Search terms used
    report.append(Paragraph("Search Terms Used", styles['Heading']))
    for term in search_terms:
        report.append(Paragraph(term, styles['List']))

    # Summary stats
    report.append(Paragraph("Summary Stats", styles['Heading']))
    num_results = len(all_results)
    date_range = (all_results['time'].min(), all_results['time'].max())

    report.append(Paragraph(f"Number of results: {num_results}", styles['List']))
    report.append(Paragraph(f"Date range of results: {date_range[0]} - {date_range[1]}", styles['List']))

    # Most common channels
    report.append(Paragraph("Most Common Channels", styles['Heading']))
    channel_counts = Counter(all_results['channel_id']).most_common()
    channel_table_data = [["Channel ID", "Count"]]
    for channel_id, count in channel_counts:
        channel_table_data.append([channel_id, count])

    table = Table(channel_table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    report.append(table)

    # Build the report
    doc.build(report)

    print(f"Saved {output_file}")


########################################################################


api_id, api_hash = retrieve_api_details()

try:
    client = TelegramClient('session_name', api_id, api_hash)
    client.start()
except:
    sys.exit("Error connecting to Telegram client. Please fix API details in api_values.txt and restart.")

# Create an empty DataFrame to store the results
all_results = pd.DataFrame(columns=['time', 'message', 'message_id', 'channel_id', 'search_term', 'link'])

# Get all the channels you are a member of
dialogs = client.get_dialogs()

# Get search terms from the file or prompt the user to enter a search term

print_colored('Select the .txt file with search terms.'
              'Each search term should be on a new line.', Fore.BLUE)

# search_terms_file = 'search_terms.txt'  # Commented out to allow for file search dialogue
search_terms_file = open_file_dialog()  # Open TKinter file dialogue -- switch with line above for txt file in directory

search_terms = check_search_terms_file(search_terms_file)

# Initialize dataframes_dict with empty lists
dataframes_dict = {search_term: [] for search_term in search_terms}

count = 0

# Iterate over each channel and process its messages
for dialog in dialogs:

    if dialog.is_channel:
        count = count + 1
        # Get the channel's InputPeerChannel object
        channel = client.get_input_entity(dialog)
        print(str(count) + "¦ Searching..." + str(channel))

        for search_string in search_terms:
            print("\033[33mSearching term: \033[0m" + search_string)

            # Replace 'keyword' with your desired value
            messages = []
            time = []
            message_ids = []
            # Perform a case-insensitive search using regular expressions
            pattern  = re.compile(search_string, re.IGNORECASE)
            # Convert the pattern to a string
            search_string = pattern.pattern

            for message in client.iter_messages(channel, search=search_string):
                messages.append(message.message) # get messages
                time.append(message.date) # get timestamp
                message_ids.append(message.id)

            if messages:  # If messages list is not empty
                channel_id = channel.channel_id if channel.channel_id else channel.chat_id
                data = {'time': time, 'message': messages, 'message_id': message_ids, 'channel_id': channel_id}
                data['search_term'] = search_string  # Add the search term to the data
                df = pd.DataFrame(data)
                df['link'] = 'https://t.me/c/' + str(channel_id) + '/' + df['message_id'].astype(str)
                df['time'] = df['time'].apply(lambda x: x.strftime('%d/%b/%Y'))
                print(f"Messages from {dialog.title}")
                print(df[['time', 'message', 'link']])
                print()

                # Append the results to the all_results DataFrame
                all_results = pd.concat([all_results, pd.DataFrame(data)], ignore_index=True)
                # Add the current DataFrame to the list
                dataframes_dict[search_string].append(df)  # This line is modified
                # Wait for 1 seconds to avoid rate limits
                t.sleep(1)

        # Print a nice pink separator
        print('\x1b[38;2;255;20;147m' + '-------------------------------------------------------------------------------------------' + '\x1b[0m')


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
                print_colored('Making HTML output file...', Fore.YELLOW)
                html = all_results.to_html(index=False, formatters={'link': render_url}, escape=False)
                f.write(html)
                print_colored(f"Saved {filename_html}", Fore.GREEN)
        except IOError as e:
            print(f'Error making HTML file: {e}')

        # Export to a CSV
        try:
            print_colored('Exporting to csv...', Fore.YELLOW)
            all_results.to_csv(filename_csv, index=False, encoding='utf-8')
            print_colored(f"Saved {filename_csv}", Fore.GREEN)
        except IOError as e:
            print(f'Error making CSV: {e}')

        # plot time graph
        try:
            plot_keyword_frequency(dataframes_dict, output_folder)
        except Exception as e:
            print(f'Error making chart: {e}')

        # Generate the report
        try:
            print_colored('Generating report...', Fore.YELLOW)
            channels = [dialog for dialog in dialogs if dialog.is_channel]
            generate_report(all_results, channels, search_terms, output_folder, now)
            print_colored('Report generated.', Fore.GREEN)
        except Exception as e:
            print(f'Error generating report: {e}')
            traceback.print_exc()

    except ValueError as e:
        print_colored('Error.', Fore.RED)


except ValueError as e:
    print_colored('Error.', Fore.RED)

print_colored('\nProcess completed', Fore.GREEN)

# Disconnect the Telethon client from the Telegram server
client.disconnect()
