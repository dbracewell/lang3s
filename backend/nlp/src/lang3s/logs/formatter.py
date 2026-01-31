import logging

RESET = "\033[0m"
COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[41m\033[97m",  # white on red bg
}


class ColoredFormatter(logging.Formatter):
    def __init__(self, use_colors=True):
        self.use_colors = use_colors
        super().__init__(
            fmt="%(levelname)s | %(asctime)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        if self.use_colors and level in COLORS:
            record.levelname = COLORS[level] + level + RESET
        return super().format(record)
