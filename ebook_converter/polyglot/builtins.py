import importlib


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


def error_message(exc):
    args = getattr(exc, 'args', None)
    if args and isinstance(args[0], str):
        return args[0]
    return str(exc)


def exec_path(path, ctx=None):
    ctx = ctx or {}
    with open(path, 'rb') as f:
        code = f.read()
    code = compile(code, f.name, 'exec')
    exec(code, ctx)


def cmp(a, b):
    return (a > b) - (a < b)


def reload(module):
    return importlib.reload(module)
