"""
A simplified logging system
"""
import logging


class CustomFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors"""

    grey = "\x1b[38;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    fmt = "%(message)s"

    FORMATS = {logging.DEBUG: grey + fmt + reset,
               logging.INFO: grey + fmt + reset,
               logging.WARNING: yellow + fmt + reset,
               logging.ERROR: red + fmt + reset,
               logging.CRITICAL: bold_red + fmt + reset}

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class Logger:
    """
    Logger class with output on console only
    """
    def __init__(self, logger_name, color=False):
        """
        Initialize named logger
        """
        self._log = logging.getLogger(logger_name)
        self.setup_logger()
        self._log.set_verbose = self.set_verbose

    def __call__(self):
        """
        Calling this object will return configured logging.Logger object with
        additional set_verbose() method.
        """
        return self._log

    def set_verbose(self, verbose_level, quiet_level):
        """
        Change verbosity level. Default level is warning.
        """
        self._log.setLevel(logging.WARNING)

        if quiet_level:
            self._log.setLevel(logging.ERROR)
            if quiet_level > 1:
                self._log.setLevel(logging.CRITICAL)

        if verbose_level:
            self._log.setLevel(logging.INFO)
            if verbose_level > 1:
                self._log.setLevel(logging.DEBUG)

    def setup_logger(self):
        """
        Create setup instance and make output meaningful :)
        """
        if self._log.handlers:
            # need only one handler
            return

        console_handler = logging.StreamHandler()
        console_handler.set_name("console")
        console_formatter = CustomFormatter()
        console_handler.setFormatter(console_formatter)
        self._log.addHandler(console_handler)
        self._log.setLevel(logging.WARNING)


default_log = Logger('ebook-converter')()
# TODO(gryf): remove this after providing value from cmd line/config
default_log.set_verbose(2, 0)
