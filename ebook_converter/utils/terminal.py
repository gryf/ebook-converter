import os, sys, re
import fcntl, termios, struct


def fmt(code):
    return '\033[%dm' % code


RATTRIBUTES = dict(
        zip(range(1, 9), (
            'bold',
            'dark',
            '',
            'underline',
            'blink',
            '',
            'reverse',
            'concealed'
            )
        ))
ATTRIBUTES = {v:fmt(k) for k, v in RATTRIBUTES.items()}
del ATTRIBUTES['']

RBACKGROUNDS = dict(
        zip(range(41, 48), (
            'red',
            'green',
            'yellow',
            'blue',
            'magenta',
            'cyan',
            'white'
            ),
    ))
BACKGROUNDS = {v:fmt(k) for k, v in RBACKGROUNDS.items()}

RCOLORS = dict(
        zip(range(31, 38), (
            'red',
            'green',
            'yellow',
            'blue',
            'magenta',
            'cyan',
            'white',
            ),
        ))
COLORS = {v:fmt(k) for k, v in RCOLORS.items()}

RESET = fmt(0)


def colored(text, fg=None, bg=None, bold=False):
    prefix = []
    if fg is not None:
        prefix.append(COLORS[fg])
    if bg is not None:
        prefix.append(BACKGROUNDS[bg])
    if bold:
        prefix.append(ATTRIBUTES['bold'])
    prefix = ''.join(prefix)
    suffix = RESET
    if isinstance(text, bytes):
        prefix = prefix.encode('ascii')
        suffix = suffix.encode('ascii')
    return prefix + text + suffix


class Detect(object):

    def __init__(self, stream):
        self.stream = stream or sys.stdout
        self.isatty = getattr(self.stream, 'isatty', lambda : False)()
        force_ansi = False
        if not self.isatty and force_ansi:
            self.isatty = True
        self.isansi = force_ansi or not False
        self.set_console = self.write_console = None
        self.is_console = False


class ColoredStream(Detect):

    def __init__(self, stream=None, fg=None, bg=None, bold=False):
        stream = getattr(stream, 'buffer', stream)
        Detect.__init__(self, stream)
        self.fg, self.bg, self.bold = fg, bg, bold

    def cwrite(self, what):
        if not isinstance(what, bytes):
            what = what.encode('ascii')
        self.stream.write(what)

    def __enter__(self):
        if not self.isatty:
            return self
        if self.isansi:
            if self.bold:
                self.cwrite(ATTRIBUTES['bold'])
            if self.bg is not None:
                self.cwrite(BACKGROUNDS[self.bg])
            if self.fg is not None:
                self.cwrite(COLORS[self.fg])
        elif self.set_console is not None:
            if self.wval != 0:
                self.set_console(self.file_handle, self.wval)
        return self

    def __exit__(self, *args, **kwargs):
        if not self.isatty:
            return
        if not self.fg and not self.bg and not self.bold:
            return
        if self.isansi:
            self.cwrite(RESET)
            self.stream.flush()
        elif self.set_console is not None:
            self.set_console(self.file_handle, self.default_console_text_attributes)


class ANSIStream(Detect):

    ANSI_RE = r'\033\[((?:\d|;)*)([a-zA-Z])'

    def __init__(self, stream=None):
        super(ANSIStream, self).__init__(stream)
        self.encoding = getattr(self.stream, 'encoding', 'utf-8') or 'utf-8'
        self.stream_takes_unicode = hasattr(self.stream, 'buffer')
        self.last_state = (None, None, False)
        self._ansi_re_bin = self._ansi_re_unicode = None

    def ansi_re(self, binary=False):
        attr = '_ansi_re_bin' if binary else '_ansi_re_unicode'
        ans = getattr(self, attr)
        if ans is None:
            expr = self.ANSI_RE
            if binary:
                expr = expr.encode('ascii')
            ans = re.compile(expr)
            setattr(self, attr, ans)
        return ans

    def write(self, text):
        if not self.isatty:
            return self.strip_and_write(text)

        if self.isansi:
            return self.stream.write(text)

        if not self.isansi and self.set_console is None:
            return self.strip_and_write(text)

        self.write_and_convert(text)

    def polyglot_write(self, text):
        binary = isinstance(text, bytes)
        stream = self.stream
        if self.stream_takes_unicode:
            if binary:
                stream = self.stream.buffer
        else:
            if not binary:
                text = text.encode(self.encoding, 'replace')
        stream.write(text)

    def strip_and_write(self, text):
        binary = isinstance(text, bytes)
        pat = self.ansi_re(binary)
        repl = b'' if binary else ''
        self.polyglot_write(pat.sub(repl, text))

    def write_and_convert(self, text):
        '''
        Write the given text to our wrapped stream, stripping any ANSI
        sequences from the text, and optionally converting them into win32
        calls.
        '''
        cursor = 0
        binary = isinstance(text, bytes)
        for match in self.ansi_re(binary).finditer(text):
            start, end = match.span()
            self.write_plain_text(text, cursor, start)
            self.convert_ansi(*match.groups())
            cursor = end
        self.write_plain_text(text, cursor, len(text))
        self.set_console(self.file_handle, self.default_console_text_attributes)
        self.stream.flush()

    def write_plain_text(self, text, start, end):
        if start < end:
            text = text[start:end]
            self.polyglot_write(text)

    def convert_ansi(self, paramstring, command):
        if isinstance(paramstring, bytes):
            paramstring = paramstring.decode('ascii', 'replace')
        if isinstance(command, bytes):
            command = command.decode('ascii', 'replace')
        params = self.extract_params(paramstring)
        self.call_win32(command, params)

    def extract_params(self, paramstring):
        def split(paramstring):
            for p in paramstring.split(';'):
                if p:
                    yield int(p)
        return tuple(split(paramstring))

    def call_win32(self, command, params):
        if command != 'm':
            return
        fg, bg, bold = self.last_state

        for param in params:
            if param in RCOLORS:
                fg = RCOLORS[param]
            elif param in RBACKGROUNDS:
                bg = RBACKGROUNDS[param]
            elif param == 1:
                bold = True
            elif param == 0:
                fg, bg, bold = None, None, False

        self.last_state = (fg, bg, bold)

        self.set_console(self.file_handle, self.default_console_text_attributes)


def get_term_geometry():

    def ioctl_GWINSZ(fd):
        try:
            return struct.unpack(b'HHHH', fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\0'*8))[:2]
        except Exception:
            return None, None

    for f in (sys.stdin, sys.stdout, sys.stderr):
        lines, cols = ioctl_GWINSZ(f.fileno())
        if lines is not None:
            return lines, cols
    try:
        fd = os.open(os.ctermid(), os.O_RDONLY)
        try:
            lines, cols = ioctl_GWINSZ(fd)
            if lines is not None:
                return lines, cols
        finally:
            os.close(fd)
    except Exception:
        pass
    return None, None


def geometry():
    try:
        lines, cols = get_term_geometry()
        if lines is not None:
            return cols, lines
    except Exception:
        pass
    return 80, 25
