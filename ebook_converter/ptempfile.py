"""
Provides platform independent temporary files that persist even after
being closed.
"""
import atexit
import os
import tempfile

from ebook_converter.constants_old import __version__, __appname__, \
        filesystem_encoding
from ebook_converter import polyglot


def cleanup(path):
    try:
        import os as oss
        if oss.path.exists(path):
            oss.remove(path)
    except Exception:
        pass


_base_dir = None


def remove_dir(x):
    try:
        import shutil
        shutil.rmtree(x, ignore_errors=True)
    except Exception:
        pass


def determined_remove_dir(x):
    for i in range(10):
        try:
            import shutil
            shutil.rmtree(x)
            return
        except Exception:
            import os  # noqa
            if os.path.exists(x):
                # In case some other program has one of the temp files open.
                import time
                time.sleep(0.1)
            else:
                return
    try:
        import shutil
        shutil.rmtree(x, ignore_errors=True)
    except Exception:
        pass


def app_prefix(prefix):
    return '%s_%s_%s' % (__appname__, __version__, prefix)


_osx_cache_dir = None


def osx_cache_dir():
    global _osx_cache_dir
    if _osx_cache_dir:
        return _osx_cache_dir
    if _osx_cache_dir is None:
        _osx_cache_dir = False
        import ctypes
        libc = ctypes.CDLL(None)
        buf = ctypes.create_string_buffer(512)
        # _CS_DARWIN_USER_CACHE_DIR = 65538
        buflen = libc.confstr(65538, ctypes.byref(buf), len(buf))
        if 0 < buflen < len(buf):
            try:
                q = buf.value.decode('utf-8').rstrip('\0')
            except ValueError:
                pass
            if q and os.path.isdir(q) and os.access(q, os.R_OK | os.W_OK |
                                                    os.X_OK):
                _osx_cache_dir = q
                return q


def base_dir():
    global _base_dir
    if _base_dir is not None and not os.path.exists(_base_dir):
        # Some people seem to think that running temp file cleaners that
        # delete the temp dirs of running programs is a good idea!
        _base_dir = None
    if _base_dir is None:
        td = os.environ.get('CALIBRE_WORKER_TEMP_DIR', None)
        if td is not None:
            from ebook_converter.utils.serialize import msgpack_loads
            try:
                td = msgpack_loads(polyglot.from_hex_bytes(td))
            except Exception:
                td = None
        if td and os.path.exists(td):
            _base_dir = td
        else:
            base = os.environ.get('CALIBRE_TEMP_DIR', None)
            prefix = app_prefix('tmp_')
            _base_dir = tempfile.mkdtemp(prefix=prefix, dir=base)
            atexit.register(remove_dir, _base_dir)

        try:
            tempfile.gettempdir()
        except Exception:
            # Widows temp vars set to a path not encodable in mbcs
            # Use our temp dir
            tempfile.tempdir = _base_dir

    return _base_dir


def reset_base_dir():
    global _base_dir
    _base_dir = None
    base_dir()


def _force_unicode(x):
    # Cannot use the implementation in calibre.__init__ as it causes a circular
    # dependency
    # NOTE(gryf): Congratulations! that's a 3rd function in this codebase
    # called force_unicode! I guess that forcing unicode on text objects is
    # some kind of hobby.
    if isinstance(x, bytes):
        x = x.decode(filesystem_encoding)
    return x


def _make_file(suffix, prefix, base):
    suffix, prefix = map(_force_unicode, (suffix, prefix))  # no2to3
    return tempfile.mkstemp(suffix, prefix, dir=base)


def _make_dir(suffix, prefix, base):
    suffix, prefix = map(_force_unicode, (suffix, prefix))  # no2to3
    return tempfile.mkdtemp(suffix, prefix, base)


class PersistentTemporaryFile(object):
    """
    A file-like object that is a temporary file that is available even after
    being closed on all platforms. It is automatically deleted on normal
    program termination.
    """
    _file = None

    def __init__(self, suffix="", prefix="", dir=None, mode='w+b'):
        if prefix is None:
            prefix = ""
        if dir is None:
            dir = base_dir()
        fd, name = _make_file(suffix, prefix, dir)

        self._file = os.fdopen(fd, mode)
        self._name = name
        self._fd = fd
        atexit.register(cleanup, name)

    def __getattr__(self, name):
        if name == 'name':
            return self.__dict__['_name']
        return getattr(self.__dict__['_file'], name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def PersistentTemporaryDirectory(suffix='', prefix='', dir=None):
    """
    Return the path to a newly created temporary directory that will
    be automatically deleted on application exit.
    """
    if dir is None:
        dir = base_dir()
    tdir = _make_dir(suffix, prefix, dir)

    atexit.register(remove_dir, tdir)
    return tdir


class TemporaryDirectory(object):
    """
    A temporary directory to be used in a with statement.
    """

    def __init__(self, suffix='', prefix='', dir=None, keep=False):
        self.suffix = suffix
        self.prefix = prefix
        if dir is None:
            dir = base_dir()
        self.dir = dir
        self.keep = keep

    def __enter__(self):
        if not hasattr(self, 'tdir'):
            self.tdir = _make_dir(self.suffix, self.prefix, self.dir)
        return self.tdir

    def __exit__(self, *args):
        if not self.keep and os.path.exists(self.tdir):
            remove_dir(self.tdir)


class TemporaryFile(object):

    def __init__(self, suffix="", prefix="", dir=None, mode='w+b'):
        if prefix is None:
            prefix = ''
        if suffix is None:
            suffix = ''
        if dir is None:
            dir = base_dir()
        self.mode = mode
        self.dir = dir
        self.suffix = suffix
        self.prefix = prefix
        self._file = None

    def __enter__(self):
        fd, name = _make_file(self.suffix, self.prefix, self.dir)
        self._file = os.fdopen(fd, self.mode)
        self._name = name
        self._file.close()
        return name

    def __exit__(self, *args):
        cleanup(self._name)


class SpooledTemporaryFile(tempfile.SpooledTemporaryFile):

    def __init__(self, max_size=0, suffix="", prefix="", dir=None, mode='w+b',
                 bufsize=-1):
        if prefix is None:
            prefix = ''
        if suffix is None:
            suffix = ''
        if dir is None:
            dir = base_dir()
        self._name = None
        tempfile.SpooledTemporaryFile.__init__(self, max_size=max_size,
                                               suffix=suffix, prefix=prefix,
                                               dir=dir, mode=mode)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val):
        self._name = val

    def truncate(self, *args):
        # The stdlib SpooledTemporaryFile implementation of truncate() doesn't
        # allow specifying a size.
        self._file.truncate(*args)


def better_mktemp(*args, **kwargs):
    fd, path = tempfile.mkstemp(*args, **kwargs)
    os.close(fd)
    return path
