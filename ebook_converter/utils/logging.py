"""
A simplified logging system
"""
import sys
import traceback
import io
import os
from functools import partial

from ebook_converter import constants_old


DEBUG = 0
INFO = 1
WARN = 2
ERROR = 3


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

        self.debug = partial(self.print_with_flush, DEBUG)
        self.info = partial(self.print_with_flush, INFO)
        self.warn = self.warning = partial(self.print_with_flush, WARN)
        self.error = partial(self.print_with_flush, ERROR)

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


default_log = Log()
