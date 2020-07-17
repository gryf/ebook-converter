import codecs
import collections
import importlib
import locale
import os
import sys


__appname__ = 'ebook-converter'
numeric_version = (4, 12, 0)
__version__ = '.'.join([str(x) for x in numeric_version])
__author__ = "foobar"

'''
Various run time constants.
'''


_plat = sys.platform.lower()
isosx = 'darwin' in _plat
isnewosx = isosx and getattr(sys, 'new_app_bundle', False)
isfreebsd = 'freebsd' in _plat
isnetbsd = 'netbsd' in _plat
isdragonflybsd = 'dragonfly' in _plat
ishaiku = 'haiku1' in _plat
isfrozen = hasattr(sys, 'frozen')
isunix = True
isportable = os.getenv('CALIBRE_PORTABLE_BUILD') is not None
isxp = isoldvista = False
is64bit = sys.maxsize > (1 << 32)
FAKE_PROTOCOL, FAKE_HOST = 'clbr', 'internal.invalid'
VIEWER_APP_UID = 'com.calibre-ebook.viewer'
EDITOR_APP_UID = 'com.calibre-ebook.edit-book'
MAIN_APP_UID = 'com.calibre-ebook.main-gui'
STORE_DIALOG_APP_UID = 'com.calibre-ebook.store-dialog'
TOC_DIALOG_APP_UID = 'com.calibre-ebook.toc-editor'
try:
    preferred_encoding = locale.getpreferredencoding()
    codecs.lookup(preferred_encoding)
except Exception:
    preferred_encoding = 'utf-8'

fcntl = importlib.import_module('fcntl')
dark_link_color = '#6cb4ee'

_osx_ver = None


def get_osx_version():
    global _osx_ver
    if _osx_ver is None:
        import platform
        from collections import namedtuple
        OSX = namedtuple('OSX', 'major minor tertiary')
        try:
            ver = platform.mac_ver()[0].split('.')
            if len(ver) == 2:
                ver.append(0)
            _osx_ver = OSX(*map(int, ver))  # no2to3
        except Exception:
            _osx_ver = OSX(0, 0, 0)
    return _osx_ver


filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None:
    filesystem_encoding = 'utf-8'
else:
    try:
        if codecs.lookup(filesystem_encoding).name == 'ascii':
            filesystem_encoding = 'utf-8'
            # On linux, unicode arguments to os file functions are coerced to an ascii
            # bytestring if sys.getfilesystemencoding() == 'ascii', which is
            # just plain dumb. This is fixed by the icu.py module which, when
            # imported changes ascii to utf-8
    except Exception:
        filesystem_encoding = 'utf-8'


DEBUG = os.getenv('CALIBRE_DEBUG') is not None


def debug():
    global DEBUG
    DEBUG = True


def _get_cache_dir():
    import errno
    confcache = os.path.join(config_dir, 'caches')
    try:
        os.makedirs(confcache)
    except EnvironmentError as err:
        if err.errno != errno.EEXIST:
            raise
    if isportable:
        return confcache
    ccd = os.getenv('CALIBRE_CACHE_DIRECTORY')
    if ccd is not None:
        ans = os.path.abspath(ccd)
        try:
            os.makedirs(ans)
            return ans
        except EnvironmentError as err:
            if err.errno == errno.EEXIST:
                return ans

    candidate = os.getenv('XDG_CACHE_HOME', '~/.cache')
    candidate = os.path.join(os.path.expanduser(candidate),
                                __appname__)
    if isinstance(candidate, bytes):
        try:
            candidate = candidate.decode(filesystem_encoding)
        except ValueError:
            candidate = confcache
    try:
        os.makedirs(candidate)
    except EnvironmentError as err:
        if err.errno != errno.EEXIST:
            candidate = confcache
    return candidate


def cache_dir():
    ans = getattr(cache_dir, 'ans', None)
    if ans is None:
        ans = cache_dir.ans = os.path.realpath(_get_cache_dir())
    return ans



# plugins {{{


class Plugins(collections.Mapping):

    def __init__(self):
        self._plugins = {}
        self.plugins = frozenset([])

    def load_plugin(self, name):
        if name in self._plugins:
            return
        # sys.path.insert(0, plugins_loc)
        try:
            del sys.modules[name]
        except KeyError:
            pass
        plugin_err = ''
        try:
            p = importlib.import_module(name)
        except Exception as err:
            p = None
            plugin_err = str(err)
        self._plugins[name] = p, plugin_err

    def __iter__(self):
        return iter(self.plugins)

    def __len__(self):
        return len(self.plugins)

    def __contains__(self, name):
        return name in self.plugins

    def __getitem__(self, name):
        if name not in self.plugins:
            raise KeyError('No plugin named %r'%name)
        self.load_plugin(name)
        return self._plugins[name]


plugins = Plugins()
# }}}

# config_dir {{{

CONFIG_DIR_MODE = 0o700

cconfd = os.getenv('CALIBRE_CONFIG_DIRECTORY')
if cconfd is not None:
    config_dir = os.path.abspath(cconfd)

bdir = os.path.abspath(os.path.expanduser(os.getenv('XDG_CONFIG_HOME', '~/.config')))
config_dir = os.path.join(bdir, 'calibre')
try:
    os.makedirs(config_dir, mode=CONFIG_DIR_MODE)
except:
    pass
if not os.path.exists(config_dir) or \
        not os.access(config_dir, os.W_OK) or not \
        os.access(config_dir, os.X_OK):
    print('No write acces to', config_dir, 'using a temporary dir instead')
    import tempfile, atexit
    config_dir = tempfile.mkdtemp(prefix='calibre-config-')

    def cleanup_cdir():
        try:
            import shutil
            shutil.rmtree(config_dir)
        except:
            pass
    atexit.register(cleanup_cdir)
# }}}


dv = os.getenv('CALIBRE_DEVELOP_FROM')
is_running_from_develop = bool(getattr(sys, 'frozen', False) and dv and os.path.abspath(dv) in sys.path)
del dv


def get_version():
    '''Return version string for display to user '''
    v = __version__
    if numeric_version[-1] == 0:
        v = v[:-2]
    if is_running_from_develop:
        v += '*'

    return v


def get_portable_base():
    'Return path to the directory that contains calibre-portable.exe or None'
    if isportable:
        return os.path.dirname(os.path.dirname(os.getenv('CALIBRE_PORTABLE_BUILD')))
