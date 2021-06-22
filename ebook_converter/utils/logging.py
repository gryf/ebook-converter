"""
A simplified logging system
"""
import functools
import io
import os
import sys
import traceback

# how about making it really simplified?
import logging

from ebook_converter import constants_old


DEBUG = 0
INFO = 1
WARN = 2
ERROR = 3


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

        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.set_name("console")
        console_formatter = CustomFormatter()
        console_handler.setFormatter(console_formatter)
        self._log.addHandler(console_handler)
        self._log.setLevel(logging.WARNING)


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

#The background is set with 40 plus the number of the color, and the foreground with 30

#These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

def formatter_message(message, use_color = True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace("$BOLD",
                                                               BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message

class ColoredFormatter(logging.Formatter):
    COLORS = {'WARNING': YELLOW,
              'INFO': WHITE,
              'DEBUG': BLUE,
              'CRITICAL': YELLOW,
              'ERROR': RED}

    def __init__(self, msg, use_color=True):
        logging.Formatter.__init__(self, msg)
        self.use_color = use_color

    def format(self, record):
        levelname = record.levelname
        if self.use_color and levelname in self.COLORS:
            levelname_color = COLOR_SEQ % (30 + self.COLORS[levelname]) + \
                    levelname + RESET_SEQ
            record.levelname = levelname_color
        return logging.Formatter.format(self, record)









class Stream(object):

    def __init__(self, stream=None):
        if stream is None:
            stream = io.BytesIO()
        self.stream = getattr(stream, 'buffer', stream)
        # self._prints = partial(prints, safe_encode=True, file=stream)

    def flush(self):
        self.stream.flush()

    def prints(self, level, *args, **kwargs):
        raise NotImplementedError()


class ANSIStream(Stream):

    def __init__(self, stream=sys.stdout):
        Stream.__init__(self, stream)
        self.color = {
            DEBUG: 'green',
            INFO: None,
            WARN: 'yellow',
            ERROR: 'red',
        }

    def prints(self, level, *args, **kwargs):
        fobj = kwargs.get('file', sys.stdout)
        sep = kwargs.get('sep', ' ')
        enc = ('utf-8' if os.getenv('CALIBRE_WORKER')
               else constants_old.preferred_encoding)
        if isinstance(sep, bytes):
            sep = sep.decode(enc)
        end = kwargs.get('end', '\n')
        if isinstance(end, bytes):
            end = end.decode(enc)
        count = 0
        for i, arg in enumerate(args):
            if isinstance(arg, bytes):
                arg = arg.decode(enc)
            arg = repr(arg)
            try:
                fobj.write(arg)
                count += len(arg)
            except Exception:
                arg = repr(arg)
                fobj.write(arg)
                count += len(arg)
            if i != len(args)-1:
                fobj.write(sep)
                count += len(sep)
            count += len(end)

    def flush(self):
        self.stream.flush()


class Log(object):

    DEBUG = DEBUG
    INFO = INFO
    WARN = WARN
    ERROR = ERROR

    def __init__(self, level=INFO):
        self.filter_level = level
        default_output = ANSIStream()
        self.outputs = [default_output]

        self.debug = functools.partial(self.print_with_flush, DEBUG)
        self.info = functools.partial(self.print_with_flush, INFO)
        self.warn = self.warning = functools.partial(self.print_with_flush,
                                                     WARN)
        self.error = functools.partial(self.print_with_flush, ERROR)

    def prints(self, level, *args, **kwargs):
        if level < self.filter_level:
            return
        for output in self.outputs:
            output.prints(level, *args, **kwargs)

    def print_with_flush(self, level, *args, **kwargs):
        if level < self.filter_level:
            return
        for output in self.outputs:
            output.prints(level, *args, **kwargs)
        self.flush()

    def exception(self, *args, **kwargs):
        limit = kwargs.pop('limit', None)
        self.print_with_flush(ERROR, *args, **kwargs)
        self.print_with_flush(DEBUG, traceback.format_exc(limit))

    def __call__(self, *args, **kwargs):
        self.info(*args, **kwargs)

    def __enter__(self):
        self.orig_filter_level = self.filter_level
        self.filter_level = self.ERROR + 100

    def __exit__(self, *args):
        self.filter_level = self.orig_filter_level

    def flush(self):
        for o in self.outputs:
            if hasattr(o, 'flush'):
                o.flush()

    def close(self):
        for o in self.outputs:
            if hasattr(o, 'close'):
                o.close()


default_log = Logger('ebook-converter')()
# TODO(gryf): remove this after providing value from cmd line/config
default_log.set_verbose(2, 0)
