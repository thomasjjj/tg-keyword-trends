import datetime
import os
import re
import sys
import textwrap
import time as t
import tkinter as tk
import traceback
from collections import Counter
from tkinter import filedialog

from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import pytz
from PIL import Image as PILImage
from colorama import Style, Fore
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Spacer, Image, PageBreak, Preformatted, PageTemplate, BaseDocTemplate, Frame
from telethon.sync import TelegramClient
# import stylecloud  # disabled while I fix the wordcloud




SCRIPT_DESCRIPTION = r"""

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

SCRIPT_WARNING = r"""
WARNING: This tool uses your list of followed groups as the list it searches from. It may include personal chats/groups.
         For the sake of OPSEC, it is recommended to use a burner account and follow only investigation-specific chats.
"""


def printC(string, colour):
    '''Print coloured and then reset: The "colour" variable should be written as "Fore.GREEN" (or other colour) as it
    uses Fore function from colorama.'''
    print(colour + string + Style.RESET_ALL)

def connect_to_telegram():
    """
     Connects to the Telegram API using the API ID and API hash values stored in a file named 'api_values.txt'.
     If the file does not exist, it prompts the user to enter their API ID and API hash and creates the file.

     Returns:
         TelegramClient: A connected TelegramClient instance.

     Raises:
         SystemExit: If the connection to the Telegram client fails.
     """

    def retrieve_or_generate_api_details():
        api_details_file_path = 'api_values.txt'
        if not os.path.exists(api_details_file_path):
            printC('No API details found. Please follow the instructions. This should be a one-time setup.',
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

    def attempt_connection_to_telegram():
        api_id, api_hash = retrieve_or_generate_api_details()
        client = TelegramClient('session_name', api_id, api_hash)
        if not client.start():
            sys.exit("Error connecting to Telegram client. Please fix API details in api_values.txt and restart.")
        print("Connection to Telegram established.")
        print("Please wait...")
        return client

    # Run the sub-functions and return the client
    print("Connecting to Telegram...")
    return attempt_connection_to_telegram()  # returns the client created in sub-function

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
    printC(time_message, Fore.CYAN)
    printC(progress_message, Fore.CYAN)
    print(f'{pink_colour}{"-" * 91}\x1b[0m')  # Print a nice pink separator

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

def open_folder_dialog():
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', True)  # Make the window appear on top
    folder_path = filedialog.askdirectory(parent=root, initialdir="/", title="Please select a directory")
    root.destroy()
    return folder_path

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
        printC('Search terms TXT file found\n', Fore.GREEN)

    return search_terms

def render_url(url):
    """Return an HTML link for a given URL."""
    return f'<a href="{url}">{url}</a>'

def plot_keyword_frequency(all_results, dataframes_dict, output_folder, now):
    def plot_keyword_frequency_per_channel(dataframes_dict, output_folder):
        """
        Plot the daily frequency of messages containing specific keywords across all channels.

        This function takes a dictionary of DataFrames, where each key is a search term and the
        corresponding value is a list of DataFrames containing the search results for that term.
        It creates a line plot for each search term, showing the number of messages per day that
        include the term, and saves the plot as an image in the specified output folder.

        Parameters:
        ----------
        dataframes_dict : dict
            A dictionary containing search terms as keys and lists of DataFrames with search results
            as values. Each DataFrame should have a 'time' column containing timestamps.

        output_folder : str
            The path to the folder where the generated plot images should be saved.

        Returns:
        -------
        None
        """
        min_date = None
        max_date = None

        # Find the overall min and max dates
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

        # Iterate through each search term and its corresponding DataFrames
        for search_term, dataframes in dataframes_dict.items():
            if not dataframes:  # Add this condition to check if the dataframes list is not empty
                print(f"No data available for search term: {search_term}")
                continue
            plt.figure(figsize=(14, 6))

            # Concatenate all DataFrames for the current search term
            all_results = pd.concat(dataframes, ignore_index=True)

            # Extract the date from the 'time' column and convert it to a pandas datetime object
            all_results['date'] = pd.to_datetime(all_results['time'].astype(str).str[:11].str.strip()).dt.tz_localize(None)


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
            plt.title(f'Number of Messages Returned Per Day for "{search_term}"')
            plt.legend()

            # Save the plot to a file in the output directory
            filename = f'message_count_per_day_{search_term}.png'
            filepath = os.path.join(output_folder, filename)

            printC(f'Saving graph as image for "{search_term}"...', Fore.YELLOW)
            plt.savefig(filepath)
            printC(f'Saved Graph as image for "{search_term}".', Fore.GREEN)

            plt.show(block=False)

    def plot_keyword_frequency_aggregate(dataframes_dict, output_folder):
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

        min_date, max_date = None, None

        # Filter search terms with data available
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

        filename = 'message_count_per_day.png'
        filepath = os.path.join(output_folder, filename)

        printC('Saving graph as image...', Fore.YELLOW)
        plt.savefig(filepath)
        printC('Saved Aggregated Graph as image.', Fore.GREEN)

        plt.show(block=False)

        # Idiot alert - I spent hours debugging the code because it didn't work after this stage.
        # The block=false is mandatory, so it runs in the background while the graph shows

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
                adjusted_daily_mentions['total_messages'].fillna(method='ffill', inplace=True)
                adjusted_daily_mentions['mentions'].fillna(0, inplace=True)

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
        else:
            ax.set_title(
                'Adjusted Keyword Frequency - Proportion keyword matches vs total messages - (Log Scale Percentages)')

        if scale == "normal":
            ax.yaxis.set_major_locator(ticker.FixedLocator([100, 50, 10, 1]))
        else:
            ax.yaxis.set_major_locator(ticker.FixedLocator([100, 10, 1, 0.1, 0.01]))
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'{x:,.2f} %'))
            ax.set_yscale('log')

        plt.setp(ax.get_yticklabels(), rotation=45, ha="right")

        ax.legend()

        filename = f'adjusted_keyword_frequency_{now}_{scale}.png'
        filepath = os.path.join(output_folder, filename)

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

    # Wordcloud generator -- -- Disabled for testing
    '''
    def generate_wordcloud_from_messages(messages, output_name):
        all_messages = " ".join([msg.text for msg in messages])
        stylecloud.gen_stylecloud(text=all_messages, output_name=output_name)
    '''

    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._code = []

        def showPage(self):
            self._code.append("canvas.showPage()")
            super().showPage()

        def save(self):
            page_count = len(self._pages)
            for i, code in enumerate(self._code):
                self._pageNumber = i + 1
                self.setFont("Helvetica", 9)
                self.drawRightString(200 * mm, 10 * mm, f"Page {i + 1} of {page_count}")
                eval(code)
            super().save()

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

    def generate_pdf(all_results, output_folder, dataframes_dict):
        if isinstance(all_results, list):
            all_results = pd.DataFrame(all_results)

        pdf_filename = os.path.join(output_folder, f'Telegram_Keyword_Trends_Report_{now}.pdf')
        doc = NumberedDocTemplate(pdf_filename, pagesize=letter)
        canvas = NumberedCanvas(doc)

        num_results = len(all_results)
        number_of_results = f"Number of results: {num_results}"
        date_range = (all_results['time'].min(), all_results['time'].max())
        date_range_of_results = f"Date range of results: {date_range[0]} - {date_range[1]}\n\n"

        title_style = ParagraphStyle('Title', fontSize=14, spaceAfter=16)
        subheading_style = ParagraphStyle('Subheading', fontSize=11, spaceAfter=8)
        intro_text_style = ParagraphStyle('IntroText', fontSize=9, spaceAfter=20)
        code_style = ParagraphStyle('Code', fontName='Courier', fontSize=8, spaceAfter=20)

        title = Paragraph(f"Telegram Keyword Trend Analysis {now}", title_style)
        subheading = Paragraph(f"Digital scraping of Telegram channels to extract frequency and trends of keyword use",
                               subheading_style)

        with open(r"report_template_text.txt", "r") as file:
            intro_text = file.read()
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

        # Add basic keyword per day graphs to the PDF report
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

        # Add adjusted keyword frequency and log-adjusted keyword frequency images to the PDF report
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


        # Add the wordcloud image to the report -- Disabled for testing
        '''
        wordcloud_image_path = os.path.join(output_folder,
                                            f'wordcloud_{now}.png')  # Use the same file name format as in the word cloud generation code

        pil_image = PILImage.open(wordcloud_image_path)
        max_image_width = letter[0] - 2 * doc.leftMargin
        image_width, image_height = pil_image.size
        image_ratio = image_height / image_width
        new_width = max_image_width
        new_height = max_image_width * image_ratio
        wordcloud_image = Image(wordcloud_image_path, width=new_width, height=new_height)
        
        story.append(Spacer(1, 20))
        story.append(Paragraph("Word Cloud:", subheading_style))
        story.append(wordcloud_image)
        '''

        # Add the code used to run the script (for auditablity)
        story.append(PageBreak())
        title_of_code_overview = Paragraph(f"Code used", title_style)
        story.append(title_of_code_overview)
        story.append(Paragraph("Content of main.py:", subheading_style))

        # Wrap the code to fit within the PDF page width
        max_code_width = letter[0] - 2 * doc.leftMargin
        with open("main.py", "r") as f:
            main_py_content = f.read()
        wrapped_content = ""
        for line in main_py_content.split("\n"):
            wrapped_content += textwrap.fill(line, width=int(max_code_width / 6)) + "\n"

        main_py_preformatted = Preformatted(wrapped_content, code_style)
        story.append(main_py_preformatted)

        doc.build(story)
        printC('Generated PDF with all graphs.', Fore.GREEN)


    # Run Plotting tools
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

    # Call the function to create both normal and log y-scale adjusted graphs
    # Call the function to create *normal* scale adjusted graphs
    try:
        plot_adjusted_keyword_frequency(dataframes_dict, output_folder, now)  # Default normal y-scale requested
    except Exception as e:
        print(f"Error making adjusted chart (normal scale): {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()
    # Call the same function to create *log* scale adjusted graphs
    try:
        plot_adjusted_keyword_frequency(dataframes_dict, output_folder, now, scale="log")  # With log y-scale requested
    except Exception as e:
        print(f"Error making adjusted chart (log scale): {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

    # Make Wordcloud -- Disabled for testing
    '''
    try:
        all_messages = all_results['message'].tolist()
        output_name = os.path.join(output_folder, f'wordcloud_{now}.png')
        generate_wordcloud_from_messages(all_messages, output_name)
    except FileNotFoundError:
        print(f"Error: File '{output_name}' not found. Skipping word cloud.")
    '''

    try:
        generate_pdf(all_results, output_folder, dataframes_dict)
    except Exception as e:
        print(f"Error making PDF: {type(e).__name__}: {str(e)}\n Traceback:")
        traceback.print_exc()

def generate_txt_report(all_results, channels, search_terms, output_folder, now):
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

        result_overview = f"Number of results: {num_results}\n Date range of results: {date_range[0]} - {date_range[1]}\n\n"

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
now = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')  # The now variable is time at tool start, even if called later.
printC(SCRIPT_DESCRIPTION, Fore.LIGHTYELLOW_EX)
printC(SCRIPT_WARNING, Fore.LIGHTRED_EX)

client = connect_to_telegram()
dialogs = client.get_dialogs()  # Get all the channels you are a member of

# Create an empty DataFrame to store the results
all_results = pd.DataFrame(columns=['time', 'message', 'message_id', 'channel_id', 'search_term', 'link'])

printC('Select the .txt file with search terms. Each search term should be on a new line.', Fore.BLUE)
# search_terms_file = 'search_terms.txt'    # Commented out to allow for file search dialogue
search_terms_file = open_file_dialog()      # Open TKinter file dialogue - switch with line above for txt file in dir
search_terms = check_search_terms_file(search_terms_file)               # retrieve search terms
dataframes_dict = {search_term: [] for search_term in search_terms}     # Initialize dataframes_dict with empty lists

count, start_time, total_channels = 0, t.time(), sum(1 for dialog in dialogs if dialog.is_channel)

# colour codes assigned for readability (call the escape sequences with {colour_name} in fstring
reset_colour, green_colour, yellow_colour, pink_colour = '\033[0m', '\033[32m', '\033[33m', '\x1b[38;2;255;20;147m'

# -- Get user input for start and end dates, and convert them to timezone-aware datetime objects.
start_date_str = input("Enter the start date (dd/mm/yyyy) or leave it blank for no start date: ")
end_date_str = input("Enter the end date (dd/mm/yyyy) or leave it blank for no end date: ")
start_date = datetime.datetime.strptime(start_date_str, "%d/%m/%Y").replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.UTC) if start_date_str.strip() else None
end_date = datetime.datetime.strptime(end_date_str, "%d/%m/%Y").replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(pytz.UTC) if end_date_str.strip() else None

# Add a prompt to ask the user if they want to download media
download_media = input("Do you want to download media files? (yes/no): ").strip().lower()

# If the user wants to download media, open the folder selection dialog
if download_media == 'yes':
    print("Select the folder to save media files.")
    media_folder_path = open_folder_dialog()

# Iterate over each channel and process its messages
for dialog in dialogs:

    if dialog.is_channel:
        count = count + 1
        # Get the channel's InputPeerChannel object
        channel = client.get_input_entity(dialog)

        channels_progress = str(count) + "/" + str(total_channels)  # e.g 5/488 (how many channels processed)
        # Get the channel_id
        channel_id = channel.channel_id if channel.channel_id else channel.chat_id


        # ---- Select what reporting information you want
        # print(channel_progress + "¦ Searching..." + str(channel) + f"{dialog.title}")   # Channel ID details & Channel Name
        # print(channel_progress + "¦ Searching..." + str(channel))                       # Just Channel ID details
        print(channels_progress + "¦ Searching Channel: " + f"{dialog.title}")            # Just Channel name

        for search_string in search_terms:
            # Prints the "searching" statement and allows it to be overwritten
            print(f"{yellow_colour}Searching term: {reset_colour}" + search_string + "... [RUNNING]", end='',
                  flush=True)

            messages, time, message_ids = [], [], []

            pattern = re.compile(search_string, re.IGNORECASE)  # Perform a case-insensitive search using regex
            search_string = pattern.pattern  # Convert the pattern to a string

            for message in client.iter_messages(channel, search=search_string):
                # Filter messages within the specified date range
                if (start_date is None or message.date >= start_date) and (
                        end_date is None or message.date <= end_date):

                    message_text = message.message  # Extract the message text

                    # Download media files only if the user chose to do so
                    if download_media == 'yes' and message.media:

                        current_datetime = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        media_path = os.path.join(media_folder_path, f'media export - tg-keyword-trends - {now}')
                        if not os.path.exists(media_path):
                            os.makedirs(media_path)

                        filename = f"{channel_id}_{message.id}"
                        file_path = os.path.join(media_path, filename)

                        if os.path.exists(file_path):  # Check if the file already exists
                            print(f'\r{yellow_colour}Media file already exists: {reset_colour}{file_path}  ',
                                  flush=True)
                        else:
                            with tqdm(desc=f"Downloading {filename}", total=1, unit="B", unit_scale=True) as pbar:
                                def callback(update_bytes, total_bytes):
                                    pbar.update(update_bytes - pbar.n)
                                try:
                                    client.download_media(message, file_path, progress_callback=callback)

                                except Exception as e:
                                    print(f"\rError downloading media file: {e}  ", flush=True)

                        messages.append(message_text)  # Append the message text
                        time.append(message.date)  # Get timestamp
                        message_ids.append(message.id)

            if messages:  # If messages list is not empty
                channel_id = channel.channel_id if channel.channel_id else channel.chat_id
                links = ['https://t.me/c/' + str(channel_id) + '/' + str(message_id) for message_id in message_ids]
                data = {'time': time, 'message': messages, 'message_id': message_ids, 'channel_id': channel_id,
                        'link': links}
                data['search_term'] = search_string  # Add the search term to the data
                df = pd.DataFrame(data)

                print(
                    f'\r{reset_colour}✓{green_colour}Searched term: {reset_colour}{search_string} - {green_colour}Results: {len(messages)}{reset_colour}',
                    flush=True)

                all_results = pd.concat([all_results, pd.DataFrame(data)], ignore_index=True)  # Add to all_results DF
                dataframes_dict[search_string].append(df)  # Add the current DataFrame to the list
            else:
                print(
                    f'\r{reset_colour}✓{green_colour}Searched term: {reset_colour}{search_string} - {yellow_colour}No results{reset_colour}',
                    flush=True)

            t.sleep(1)  # Wait for 1 seconds to avoid rate limits - going lower seems to cause issues

        progress_display(start_time, total_channels, count)  # Runs the progress bar

try:
    output_folder = create_output_directory(f'TG-Search_{now}')

    filename_html = os.path.join(output_folder, f'all_results__{now}.html')
    filename_csv = os.path.join(output_folder, f'all_results__{now}.csv')
    filename_pickle = os.path.join(output_folder, f'all_results__{now}.pickle')
    filename_png = os.path.join(output_folder, f'keyword_frequency__{now}.png')

    try:
        # Export to HTML
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

        # Export to a CSV
        try:
            printC('Exporting to csv...', Fore.YELLOW)
            all_results.to_csv(filename_csv, index=False, encoding='utf-8')
            printC(f"Saved {filename_csv}", Fore.GREEN)
        except IOError as e:
            print(f'Error making CSV: {e}')
            traceback.print_exc()

        # Export to pickle file -- ERROR currently, disabled for now. Grab data from CSV for further processing instead
        '''
        try:
            printC('Saving data to a pickle file...', Fore.YELLOW)
            with open(filename_pickle, 'wb') as f:
                pickle.dump(all_results, f)
            printC(f"Saved {filename_pickle}", Fore.GREEN)
        except IOError as e:
            print(f'Error saving to pickle file: {e}')
            traceback.print_exc()
        '''

        # plot all time graphs
        plot_keyword_frequency(all_results, dataframes_dict, output_folder, now)

        # Generate the .txt report
        try:
            printC('Generating .txt report...', Fore.YELLOW)
            channels = [dialog for dialog in dialogs if dialog.is_channel]
            generate_txt_report(all_results, channels, search_terms, output_folder, now)
            printC('Report .txt generated.', Fore.GREEN)
        except Exception as e:
            print(f'Error generating .txt report: {e}')
            traceback.print_exc()

    except ValueError as e:
        printC('Error.', Fore.RED)
        traceback.print_exc()

except ValueError as e:
    printC('Error.', Fore.RED)

printC('\nProcess completed', Fore.GREEN)
client.disconnect()  # Disconnect the Telethon client from the Telegram server


