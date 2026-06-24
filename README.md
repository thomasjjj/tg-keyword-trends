# Telegram Keyword Trends
An analysis tool to explore the emergence of hatespeech, disinformation, and narratives of interest on the Telegram chat platform. Please use this tool with caution as it does not have content moderation or filtering. You are responsible for the content that may be exported.

In short, this tool allows you to search all the channels you follow with a list of keywords/phrases and returns all matching results in various formats with graph visualisations. It also optionally downloads the media and thus can be used as a media search engine (currently some bugs with this feature - do not use as exhaustive media search tool).

###### Screenshot of tool in action, exploring hate speech during the Russian full-scale invasion of Ukraine
[![Screenshot of tool in action](https://user-images.githubusercontent.com/118008765/230943146-8c7fc77f-0b2f-4bf3-8f07-9e3d959ca30c.png "Screenshot of tool in action")](https://user-images.githubusercontent.com/118008765/230943146-8c7fc77f-0b2f-4bf3-8f07-9e3d959ca30c.png "Screenshot of tool in action")


##### Key Features
- This tool is designed to work with sockpuppets that follow many channels covering a particular topic.
- You can change your API details to use different accounts by editing the **.env** file.
- The tool is designed to work like Google Trends showing daily volume of key terms and map over time.
- Date filtering allows you to narrow a search into a shorter time period. If left blank, it automatically scales to the maximum range of the data.
- The tool uses Telegram search which means it is particularly good for Russian language searches and generally handles word endings well.
- Generates individual graphs for each key term.
- Generates aggregated graph showing all key terms in a search on the same graph for comparison.
- Compiles a report PDF that shows the graphs and prints the full code for auditing of data and validation of evidence.
- Outputs a TXT file summary including all the main stats, e.g, date run, channels searched, and relative volume per channel.
- Optional media download for results (this massively (like really massively) prolongs the time needed to run the tool)
- Downloaded media has filename channelid_postid so it is easy to find the original.



This script searches messages containing specified search terms in Telegram channels the user is a member of. It exports the search results in HTML and CSV formats, generates a report, and plots the message count per day.

It is designed to monitor trends of search terms in much the same way that Google Trends does. This can be very useful for identifying the emergence of hatespeech or discussion/narratives following certain events.

This current version does not do any significant adjustment to the data, for example, the graph does not display incidence of terms adjusted to the incidence of all messages. This means further analysis should be conducted to ensure that a sharp spike in terms is not confounded by a sharp spike in general activity. For this reason, the graph output should be treated as indicative of need for further research and statistical analysis.

###### Example result exploring hate speech during the Russian full-scale invasion of Ukraine
[![Example result exploring hate speech during the Russian full-scale invasion of Ukraine](https://user-images.githubusercontent.com/118008765/230750727-0a4f74db-9ab2-41df-b49a-c1ec2c785753.png "Example result exploring hate speech during the Russian full-scale invasion of Ukraine")](https://user-images.githubusercontent.com/118008765/230750727-0a4f74db-9ab2-41df-b49a-c1ec2c785753.png "Example result exploring hate speech during the Russian full-scale invasion of Ukraine")
*This image is an example result showing how the channels under investigation saw a surge in usage of specific terms.*

###### Example of the report generated 
[![Example of the report generated](https://user-images.githubusercontent.com/118008765/231264336-74be2122-dcec-4146-ac51-a5062a79e436.png "Example of the report generated")](https://user-images.githubusercontent.com/118008765/231264336-74be2122-dcec-4146-ac51-a5062a79e436.png "Example of the report generated")
*This image is an example result from the report, a PDF document that outlines the code and prints the script at the end. This means that no matter what changes or what version of the script is being used, the exact process can be scrutinised.*

###### Screenshot of some of the information generated in the txt stats report

[![Screenshot of some of the information generated in the report](https://user-images.githubusercontent.com/118008765/230942324-d42d96da-8df4-4a87-8201-360852b2f662.png "xxx")](https://user-images.githubusercontent.com/118008765/230942324-d42d96da-8df4-4a87-8201-360852b2f662.png "xxx")

This tool has been tested on English and Russian language search terms.

**WARNING:** This tool uses your list of followed groups as the list it searches from. It may include personal chats/groups. For the sake of OPSEC, it is recommended to use a burner account and follow only investigation-specific chats.

# Installation
Clone the tg-keyword-trends repository by running the following command in your terminal or command prompt:

``` git clone https://github.com/thomasjjj/tg-keyword-trends.git```

Navigate into the tg-keyword-trends directory:

```cd tg-keyword-trends```

Install the required Python dependencies using pip:

```pip install -r requirements.txt```

# Features
- Graph adjusts scale to oldest and newest posts.
- CSV generated for further processing.
- HTML file generated for opening links.
- Generates report documenting the key details of the scrape (date, channels accessed, etc) for auditability of findings.
- Media download

# Usage:

1. Add the search terms, one per line, into a .txt file. You will be prompted to enter the file location shortly.
2. Make sure you have your Telegram API details ready [https://my.telegram.org/auth]. On first run, the script saves the API ID, API hash, phone number, and optional 2FA password to **.env**.
3. The script will search through all the channels the user is a member of.
4. The search results will be exported as HTML and CSV files in a timestamped output folder.
5. The script will generate a report containing the search results for each channel.
6. The script will plot the message count per day for each search term in a graph and save it as an image.

# Telegram Authentication:

The script checks **.env** first for Telegram credentials. If required values are missing, it prompts for them and writes them to **.env** for future runs.

Telethon also keeps a local session file so future runs should not ask for a login code again unless that session file is deleted, expired, or invalidated.

Supported **.env** keys:

- TELEGRAM_API_ID
- TELEGRAM_API_HASH
- TELEGRAM_PHONE
- TELEGRAM_2FA_PASSWORD
- TELEGRAM_SESSION

If your Telegram account has two-factor authentication enabled, the script prompts for the password in plaintext so it works in terminals that do not support hidden password prompts. That password is saved in **.env** as plaintext. Keep **.env** private and do not commit it.

Existing **api_values.txt** API credentials are migrated into **.env** automatically when **.env** does not already contain them.


# Functions:

- **connect_to_telegram**: Read Telegram credentials from '.env', prompt for missing values, and connect to Telegram.
- **check_search_terms_file**: Read search terms from 'search_terms.txt' or prompt the user to enter search terms.
- **create_output_directory**: Create a timestamped directory for storing output files.
- **print_colored**: Print text in specified color using the colorama module.
- **render_url**: Generate HTML code for a hyperlink using a URL and message text.
- **generate_report**: Generate a report containing search results for each channel.
- **plot_keyword_frequency**: Plot the message count per day for each search term in a graph.

# Tips:
- Due to the date filtering feature, this tool also works well as a Telegram search engine that allows date-filtered results. Simply run the search in the date window needed and open up the output html file for a list of messages that match and their links.
- The tool handles timezones automatically and adjusts for them. Be particularly careful when editing any section of the code relating to time and date formats as this was difficult to debug. 
- It is recommended that you create a dedicated Telegram account for each subject matter. This will allow you to target only relevant channels and removes noise. 
- You don't need to search singular and plural nouns separately as this is handled by Telegram's search, (generally speaking, for English and Russian language).

[![Demonstration of graph](https://user-images.githubusercontent.com/118008765/232030941-aa506853-48ba-4433-8abf-1ee454ea1e5b.png "Demonstration of graph")](https://user-images.githubusercontent.com/118008765/232030941-aa506853-48ba-4433-8abf-1ee454ea1e5b.png "Demonstration of graph")
*This image shows the useage of the various placenames for "Bakmut", including the old Soviet names. One use of this tool could be for validating the search terms used in OSINT research. As can be seen here, one may limit their collection potential if they only use the official current name for the city rather than past and controversial names too. *

# Dependencies:

- pandas~=3.0.3
- matplotlib~=3.11.0
- Telethon~=1.44.0
- colorama~=0.4.6
- Pillow~=12.2.0
- reportlab~=5.0.0
- numpy~=2.5.0
- pytz~=2026.2
- tqdm~=4.68.3

Python Version: Python 3.11 or higher

# Testing:

Run the test suite with:

```python -m unittest discover -s tests```

# TODO

------------

- [ ] prevent opened graph png from disappearing
- [ ] add error handling to user date inputs
- [x] make graph production per term as well as aggregated to remove scaling issues
- [x] insert all graphs into PDF report (separate from TXT file report)
- [x] use the txt report to populate the PDF report with contextual data.
- [ ] add asyncio options to optimise performance - particularly for media download.
- [ ] better graphing, eg percent usage over time to adjust for new channels or surges in activity (ongoing improvements and new graphs - never complete this, just add more)
- [ ] make sure the above is included in the report pdf
- [x] time range selection
- [ ] custom channel list
- [ ] wordcloud generation of all matching messages to extract additional context, terms, and insights
- [ ] set ability to group terms into single line on graph (e.g translations/transliterations)
- [ ] possible feature: set default location for all downloaded media with a list file of media previously downloaded to prevent duplicate
