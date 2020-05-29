__license__ = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Perform various initialization tasks.
'''

import builtins
import locale
import sys

from ebook_converter import constants_old

# For backwards compat with some third party plugins
builtins.__dict__['dynamic_property'] = lambda func: func(None)



_run_once = False
winutil = winutilerror = None

if not _run_once:
    _run_once = True
    from importlib import import_module

    class DeVendor(object):

        def find_spec(self, fullname, path, target=None):
            spec = None
            if fullname == 'calibre.web.feeds.feedparser':
                m = import_module('feedparser')
                spec = m.__spec__
            elif fullname.startswith('calibre.ebooks.markdown'):
                m = import_module(fullname[len('calibre.ebooks.'):])
                spec = m.__spec__
            return spec


    sys.meta_path.insert(0, DeVendor())

    #
    # Platform specific modules
    if constants_old.iswindows:
        winutil, winutilerror = constants_old.plugins['winutil']
        if not winutil:
            raise RuntimeError('Failed to load the winutil plugin: %s'%winutilerror)
        if len(sys.argv) > 1 and not isinstance(sys.argv[1], str):
            sys.argv[1:] = winutil.argv()[1-len(sys.argv):]

    # Ensure that all temp files/dirs are created under a calibre tmp dir
    from ebook_converter.ptempfile import base_dir
    try:
        base_dir()
    except EnvironmentError:
        pass  # Ignore this error during startup, so we can show a better error message to the user later.

    #
    # Convert command line arguments to unicode
    enc = constants_old.preferred_encoding
    if constants_old.isosx:
        enc = 'utf-8'
    for i in range(1, len(sys.argv)):
        if not isinstance(sys.argv[i], str):
            sys.argv[i] = sys.argv[i].decode(enc, 'replace')

    #
    # Ensure that the max number of open files is at least 1024
    if constants_old.iswindows:
        # See https://msdn.microsoft.com/en-us/library/6e3b887c.aspx
        if hasattr(winutil, 'setmaxstdio'):
            winutil.setmaxstdio(max(1024, winutil.getmaxstdio()))
    else:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft < 1024:
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, (min(1024, hard), hard))
            except Exception:
                if constants_old.DEBUG:
                    import traceback
                    traceback.print_exc()

    #
    # Setup resources
    import ebook_converter.utils.resources as resources
    resources

    #
    # Initialize locale
    # Import string as we do not want locale specific
    # string.whitespace/printable, on windows especially, this causes problems.
    # Before the delay load optimizations, string was loaded before this point
    # anyway, so we preserve the old behavior explicitly.
    import string
    string
    try:
        locale.setlocale(locale.LC_ALL, '')  # set the locale to the user's default locale
    except:
        dl = locale.getdefaultlocale()
        try:
            if dl:
                locale.setlocale(locale.LC_ALL, dl[0])
        except:
            pass

    def connect_lambda(bound_signal, self, func, **kw):
        import weakref
        r = weakref.ref(self)
        del self
        num_args = func.__code__.co_argcount - 1
        if num_args < 0:
            raise TypeError('lambda must take at least one argument')

        def slot(*args):
            ctx = r()
            if ctx is not None:
                if len(args) != num_args:
                    args = args[:num_args]
                func(ctx, *args)

        bound_signal.connect(slot, **kw)
    builtins.__dict__['connect_lambda'] = connect_lambda

    if constants_old.islinux or constants_old.isosx or constants_old.isfreebsd:
        # Name all threads at the OS level created using the threading module, see
        # http://bugs.python.org/issue15500
        import threading

        orig_start = threading.Thread.start

        def new_start(self):
            orig_start(self)
            try:
                name = self.name
                if not name or name.startswith('Thread-'):
                    name = self.__class__.__name__
                    if name == 'Thread':
                        name = self.name
                if name:
                    if isinstance(name, str):
                        name = name.encode('ascii', 'replace').decode('ascii')
                    constants_old.plugins['speedup'][0].set_thread_name(name[:15])
            except Exception:
                pass  # Don't care about failure to set name
        threading.Thread.start = new_start


def test_lopen():
    from ebook_converter.ptempfile import TemporaryDirectory
    from ebook_converter import CurrentDir
    n = 'f\xe4llen'
    print('testing open()')

    if constants_old.iswindows:
        import msvcrt, win32api

        def assert_not_inheritable(f):
            if win32api.GetHandleInformation(msvcrt.get_osfhandle(f.fileno())) & 0b1:
                raise SystemExit('File handle is inheritable!')
    else:
        import fcntl

        def assert_not_inheritable(f):
            if not fcntl.fcntl(f, fcntl.F_GETFD) & fcntl.FD_CLOEXEC:
                raise SystemExit('File handle is inheritable!')

    def copen(*args):
        ans = open(*args)
        assert_not_inheritable(ans)
        return ans

    with TemporaryDirectory() as tdir, CurrentDir(tdir):
        with copen(n, 'w') as f:
            f.write('one')

        print('O_CREAT tested')
        with copen(n, 'w+b') as f:
            f.write(b'two')
        with copen(n, 'r') as f:
            if f.read() == 'two':
                print('O_TRUNC tested')
            else:
                raise Exception('O_TRUNC failed')
        with copen(n, 'ab') as f:
            f.write(b'three')
        with copen(n, 'r+') as f:
            if f.read() == 'twothree':
                print('O_APPEND tested')
            else:
                raise Exception('O_APPEND failed')
        with copen(n, 'r+') as f:
            f.seek(3)
            f.write('xxxxx')
            f.seek(0)
            if f.read() == 'twoxxxxx':
                print('O_RANDOM tested')
            else:
                raise Exception('O_RANDOM failed')
