**This script searches messages containing specified search terms in Telegram channels the user is a member of. It exports the search results in HTML and CSV formats, generates a report, and plots the message count per day.**

It is designed to monitor trends of search terms in much the same way that Google Trends does. This can be very useful for identifying the emergence of hatespeech or discussion/narratives following certain events.

###### Example result exploring hate speech during the Russian full-scale invasion of Ukraine
[![Example result exploring hate speech during the Russian full-scale invasion of Ukraine](https://user-images.githubusercontent.com/118008765/230750727-0a4f74db-9ab2-41df-b49a-c1ec2c785753.png "Example result exploring hate speech during the Russian full-scale invasion of Ukraine")](https://user-images.githubusercontent.com/118008765/230750727-0a4f74db-9ab2-41df-b49a-c1ec2c785753.png "Example result exploring hate speech during the Russian full-scale invasion of Ukraine")
*This image is an example result showing how the channels under investigation saw a surge in specific terms.*

This tool has been tested on English and Russian language search terms.

***Currently English has full functionality and the tool works well with Cyrillic, but the generated report may have a few issues. All other features should work as expected.***

**WARNING:** This tool uses your list of followed groups as the list it searches from. It may include personal chats/groups. For the sake of OPSEC, it is recommended to use a burner account and follow only investigation-specific chats.



# Usage:

1. Add your API ID and API Hash as plain text in 'api_details.txt'.
2. Add the list of search terms, one per line, in 'search_terms.txt'.
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

# Dependencies:

Telethon
pandas
matplotlib
colorama
regex
reportlab
Python Version:

Python 3.11 or higher