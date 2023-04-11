# Telegram Keyword Trends
An analysis tool to explore the emergence of hatespeech, disinformation, and narratives of interest on the Telegram chat platform. Please use this tool with caution as it does not have content moderation or filtering. You are responsible for the content that may be exported.

##### Key Features
- This tool is designed to work with sockpuppets that follow many channels covering a particular topic.
- You can change your API details to use different accounts by editing the **api_values.txt** file.
- The tool is designed to work like Google Trends showing daily volume of key terms and map over time.
- Date filtering allows you to narrow a search into a shorter time period. If left blank, it automatically scales to the maximum range of the data.
- The tool uses Telegram search which means it is particularly good for Russian language searches and generally handles word endings well.
- Generates individual graphs for each key term.
- Generates aggregated graph showing all key terms in a search on the same graph for comparison.
- Compiles a report PDF that shows the graphs and prints the full code for auditing of data and validation of evidence.
- Outputs a TXT file summary including all the main stats, e.g, date run, channels searched, and relative volume per channel.


###### Screenshot of tool in action, exploring hate speech during the Russian full-scale invasion of Ukraine
[![Screenshot of tool in action](https://user-images.githubusercontent.com/118008765/230943146-8c7fc77f-0b2f-4bf3-8f07-9e3d959ca30c.png "Screenshot of tool in action")](https://user-images.githubusercontent.com/118008765/230943146-8c7fc77f-0b2f-4bf3-8f07-9e3d959ca30c.png "Screenshot of tool in action")

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

# Usage:

1. Add the search terms, one per line, into a .txt file. You will be prompted to enter the file location shortly.
2. Make sure you have your Telegram API details ready [https://my.telegram.org/auth]
3. The script will search through all the channels the user is a member of.
4. The search results will be exported as HTML and CSV files in a timestamped output folder.
5. The script will generate a report containing the search results for each channel.
6. The script will plot the message count per day for each search term in a graph and save it as an image.


# Functions:

- **retrieve_api_details**: Read API details from 'api_details.txt'.
- **check_search_terms_file**: Read search terms from 'search_terms.txt' or prompt the user to enter search terms.
- **create_output_directory**: Create a timestamped directory for storing output files.
- **print_colored**: Print text in specified color using the colorama module.
- **render_url**: Generate HTML code for a hyperlink using a URL and message text.
- **generate_report**: Generate a report containing search results for each channel.
- **plot_keyword_frequency**: Plot the message count per day for each search term in a graph.

# Tips:
- The tool handles timezones automatically and adjusts for them. Be particularly careful when editing any section of the code relating to time and date formats as this was difficult to debug. 
- It is recommended that you create a dedicated Telegram account for each subject matter. This will allow you to target only relevant channels and removes noise. 
- You don't need to search singular and plural nouns separately as this is handled by Telegram's search, (generally speaking, for English and Russian language).

# Dependencies:

- Telethon
- pandas
- matplotlib
- colorama
- regex
- reportlab

Python Version: Python 3.11 or higher

# TODO

------------

- [ ] prevent opened graph png from disappearing
- [ ] add error handling to user date inputs
- [x] make graph production per term as well as aggregated to remove scaling issues
- [x] insert all graphs into PDF report (separate from TXT file report)
- [x] use the txt report to populate the PDF report with contextual data.
- [ ] add asyncio options to optimise performance
- [ ] better graphing, eg percent usage over time to adjust for new channels or surges in activity
- [x] time range selection
- [ ] custom channel list
- [ ] wordcloud generation of all matching messages to extract additional context, terms, and insights
- [ ] set ability to group terms into single line on graph (e.g translations/transliterations)