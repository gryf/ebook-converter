import importlib
import os
import sys


is_py3 = sys.version_info.major >= 3
native_string_type = str
iterkeys = iter


def hasenv(x):
    return getenv(x) is not None


def as_bytes(x, encoding='utf-8'):
    if isinstance(x, str):
        return x.encode(encoding)
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return bytes(x)
    if isinstance(x, memoryview):
        return x.tobytes()
    return str(x).encode(encoding)


def as_unicode(x, encoding='utf-8', errors='strict'):
    if isinstance(x, bytes):
        return x.decode(encoding, errors)
    return str(x)


def reraise(tp, value, tb=None):
    try:
        if value is None:
            value = tp()
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value
    finally:
        value = None
        tb = None


raw_input = input
getcwd = os.getcwd
getenv = os.getenv


def error_message(exc):
    args = getattr(exc, 'args', None)
    if args and isinstance(args[0], str):
        return args[0]
    return str(exc)


def iteritems(d):
    return iter(d.items())


def itervalues(d):
    return iter(d.values())


def environ_item(x):
    if isinstance(x, bytes):
        x = x.decode('utf-8')
    return x


def exec_path(path, ctx=None):
    ctx = ctx or {}
    with open(path, 'rb') as f:
        code = f.read()
    code = compile(code, f.name, 'exec')
    exec(code, ctx)


def cmp(a, b):
    return (a > b) - (a < b)


def int_to_byte(x):
    return bytes((x,))


def reload(module):
    return importlib.reload(module)


def print_to_binary_file(fileobj, encoding='utf-8'):

    def print(*a, **kw):
        f = kw.get('file', fileobj)
        if a:
            sep = as_bytes(kw.get('sep', ' '), encoding)
            for x in a:
                x = as_bytes(x, encoding)
                f.write(x)
                if x is not a[-1]:
                    f.write(sep)
        f.write(as_bytes(kw.get('end', '\n')))

    return print
