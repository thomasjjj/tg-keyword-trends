from colorama import Style


def printC(string, colour):
    """Print coloured text and then reset the terminal style."""
    print(colour + string + Style.RESET_ALL)
