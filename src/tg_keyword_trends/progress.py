import time as t

from colorama import Fore

from .console import printC


def progress_display(start_time, total_channels, count):
    """
    Displays progress, elapsed time, and estimated time remaining.
    """

    def seconds_to_hms(seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return h, m, s

    elapsed_time = t.time() - start_time
    average_time_per_channel = elapsed_time / count
    remaining_channels = total_channels - count
    estimated_remaining_time = remaining_channels * average_time_per_channel
    h, m, s = seconds_to_hms(estimated_remaining_time)
    elapsed_h, elapsed_m, elapsed_s = seconds_to_hms(elapsed_time)
    total_time = elapsed_time + estimated_remaining_time
    progress_percentage = elapsed_time / total_time

    progress_bar_length = 74
    filled_length = int(progress_percentage * progress_bar_length)
    progress_bar = '#' * filled_length + '-' * (progress_bar_length - filled_length)

    time_message = f"Processed {count}/{total_channels} channels. Time elapsed: {elapsed_h:02d}:{elapsed_m:02d}:{elapsed_s:02d}. ETA: {h:02d}:{m:02d}:{s:02d}."
    progress_message = f"Progress: |{progress_bar}| {progress_percentage * 100:.1f}%"
    printC(time_message, Fore.CYAN)
    printC(progress_message, Fore.CYAN)
    print(f'\x1b[38;2;255;20;147m{"-" * 91}\x1b[0m')
