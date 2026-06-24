import os
from collections import Counter


def generate_txt_report(all_results, channels, search_terms, output_folder, now):
    """
    Generates a text report summarizing the search results for a list of channels and search terms.

    The function creates a new text file in the specified output folder and writes various summary statistics
    and information to the file, including the project date, the channels searched, the search terms used, summary stats
    on the search results (e.g. number of results, date range), and a table of the most common channels.
    """
    print(f"Generating report for {len(channels)} channels and {len(search_terms)} search terms...")
    output_file = os.path.join(output_folder, f'report_{now}.txt')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Project Date\n")
        f.write(f"{now}\n\n")

        f.write("Summary Stats\n")
        num_results = len(all_results)
        date_range = _result_date_range(all_results)
        f.write(f"Number of results: {num_results}\n")
        f.write(f"Date range of results: {date_range[0]} - {date_range[1]}\n\n")

        f.write("Channels Searched\n")
        for channel in channels:
            f.write(f"{channel.title}\n")
        f.write("\n")

        f.write("Search Terms Used\n")
        for term in _format_search_terms(search_terms):
            f.write(f"{term}\n")
        f.write("\n")

        f.write("Most Common Channels\n")
        for channel_label, count in _channel_counts(all_results):
            f.write(f"{channel_label}, Count: {count}\n")

    print(f"Saved {output_file}")


def _result_date_range(all_results):
    if 'time' not in all_results or all_results.empty:
        return (None, None)
    return (all_results['time'].min(), all_results['time'].max())


def _format_search_terms(search_terms):
    formatted_terms = []

    for item in search_terms:
        label = getattr(item, "label", None)
        terms = getattr(item, "terms", None)
        if label is None or terms is None:
            formatted_terms.append(str(item))
        elif tuple(terms) == (label,):
            formatted_terms.append(str(label))
        else:
            formatted_terms.append(f"{label}: {' | '.join(terms)}")

    return formatted_terms


def _channel_counts(all_results):
    if all_results.empty or 'channel_id' not in all_results:
        return []

    if 'channel_title' not in all_results:
        return [(f"Channel ID: {channel_id}", count) for channel_id, count in Counter(all_results['channel_id']).most_common()]

    labels = all_results.apply(
        lambda row: f"Channel: {row['channel_title']} ({row['channel_id']})",
        axis=1,
    )
    return Counter(labels).most_common()
