import atexit
import collections
import importlib
import locale
import os
import shutil
import sys
import tempfile


__appname__ = 'ebook-converter'
numeric_version = (4, 12, 0)
__version__ = '.'.join([str(x) for x in numeric_version])
__author__ = "foobar"

"""
Various run time constants.
"""


FAKE_PROTOCOL = 'ebco'
preferred_encoding = locale.getpreferredencoding()
filesystem_encoding = sys.getfilesystemencoding() or 'utf-8'
DEBUG = os.getenv('CALIBRE_DEBUG') is not None


def debug():
    global DEBUG
    DEBUG = True


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
            raise KeyError('No plugin named %r' % name)
        self.load_plugin(name)
        return self._plugins[name]


plugins = Plugins()
# }}}

# config_dir {{{

CONFIG_DIR_MODE = 0o700

bdir = os.path.abspath(os.path.expanduser(os.getenv('XDG_CONFIG_HOME',
                                                    '~/.config')))
config_dir = os.path.join(bdir, 'ebook-converter')
try:
    os.makedirs(config_dir, mode=CONFIG_DIR_MODE)
except IOError:
    pass

if not os.path.exists(config_dir) or \
        not os.access(config_dir, os.W_OK) or not \
        os.access(config_dir, os.X_OK):
    print('No write acces to', config_dir, 'using a temporary dir instead')
    config_dir = tempfile.mkdtemp(prefix='ec-config-')

    def cleanup_cdir():
        try:
            shutil.rmtree(config_dir)
        except OSError:
            pass
    atexit.register(cleanup_cdir)
# }}}


def get_version():
    '''Return version string for display to user '''
    v = __version__
    if numeric_version[-1] == 0:
        v = v[:-2]

    return v
