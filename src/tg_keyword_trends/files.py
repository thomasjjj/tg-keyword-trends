import os
import sys
import tkinter as tk
from tkinter import filedialog

from colorama import Fore

from .console import printC


def create_output_directory(directory_name):
    os.makedirs(directory_name, exist_ok=True)
    print('Directory created.')
    return directory_name


def open_file_dialog(title="Select the search terms file"):
    """
   Opens a file dialog to allow the user to select a .txt file.

   The function creates a hidden Tkinter window, brings it to the top, and opens a file dialog.
   The file dialog is restricted to selecting .txt files. Once the user selects a file and closes
   the dialog, the function destroys the hidden Tkinter window and returns the selected file path.

   Returns:
       str: The path of the selected .txt file.
   """
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', True)
    file_path = filedialog.askopenfilename(title=title, filetypes=[("Text files", "*.txt")])
    root.destroy()
    if not file_path:
        sys.exit("Process cancelled.")
    return file_path


def open_folder_dialog():
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', True)
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
