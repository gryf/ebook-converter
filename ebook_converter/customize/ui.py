import collections
import functools
import itertools
import os
import shutil
import sys
import traceback

from ebook_converter import customize
from ebook_converter.customize import conversion
from ebook_converter.customize import profiles
from ebook_converter.customize import builtins
from ebook_converter.ebooks import metadata
from ebook_converter.utils import config as cfg
from ebook_converter.utils import config_base


builtin_names = frozenset(p.name for p in builtins.plugins)
BLACKLISTED_PLUGINS = frozenset({'Marvin XD', 'iOS reader applications'})


class NameConflict(ValueError):
    pass


def _config():
    c = config_base.Config('customize')
    c.add_opt('plugins', default={}, help='Installed plugins')
    c.add_opt('filetype_mapping', default={},
              help='Mapping for filetype plugins')
    c.add_opt('plugin_customization', default={},
              help='Local plugin customization')
    c.add_opt('disabled_plugins', default=set(), help='Disabled plugins')
    c.add_opt('enabled_plugins', default=set(), help='Enabled plugins')

    return config_base.ConfigProxy(c)


config = _config()


# File type plugins
_on_import = {}
_on_postimport = {}
_on_preprocess = {}
_on_postprocess = {}
_on_postadd = []


def reread_filetype_plugins():
    global _on_import, _on_postimport, _on_preprocess, _on_postprocess
    global _on_postadd
    _on_import = collections.defaultdict(list)
    _on_postimport = collections.defaultdict(list)
    _on_preprocess = collections.defaultdict(list)
    _on_postprocess = collections.defaultdict(list)
    _on_postadd = []

    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.FileTypePlugin):
            for ft in plugin.file_types:
                if plugin.on_import:
                    _on_import[ft].append(plugin)
                if plugin.on_postimport:
                    _on_postimport[ft].append(plugin)
                    _on_postadd.append(plugin)
                if plugin.on_preprocess:
                    _on_preprocess[ft].append(plugin)
                if plugin.on_postprocess:
                    _on_postprocess[ft].append(plugin)


def plugins_for_ft(ft, occasion):
    op = {'import': _on_import,
          'preprocess': _on_preprocess,
          'postprocess': _on_postprocess,
          'postimport': _on_postimport}[occasion]
    for p in itertools.chain(op.get(ft, ()), op.get('*', ())):
        yield p


def _run_filetype_plugins(path_to_file, ft=None, occasion='preprocess'):
    customization = config['plugin_customization']
    if ft is None:
        ft = os.path.splitext(path_to_file)[-1].lower().replace('.', '')
    nfp = path_to_file
    for plugin in plugins_for_ft(ft, occasion):
        plugin.site_customization = customization.get(plugin.name, '')
        # Some file type plugins out there override the output streams with
        # buggy implementations
        oo, oe = sys.stdout, sys.stderr
        with plugin:
            try:
                plugin.original_path_to_file = path_to_file
            except Exception:
                pass
            try:
                nfp = plugin.run(nfp) or nfp
            except Exception:
                print('Running file type plugin %s failed with traceback:' %
                      plugin.name, file=oe)
                traceback.print_exc(file=oe)
        sys.stdout, sys.stderr = oo, oe

    def norm(string):
        return os.path.normpath(os.path.normcase(string))

    if occasion == 'postprocess' and norm(nfp) != norm(path_to_file):
        shutil.copyfile(nfp, path_to_file)
        nfp = path_to_file
    return nfp


run_plugins_on_import = functools.partial(_run_filetype_plugins,
                                          occasion='import')
run_plugins_on_preprocess = functools.partial(_run_filetype_plugins,
                                              occasion='preprocess')
run_plugins_on_postprocess = functools.partial(_run_filetype_plugins,
                                               occasion='postprocess')


def run_plugins_on_postimport(db, book_id, fmt):
    customization = config['plugin_customization']
    fmt = fmt.lower()
    for plugin in plugins_for_ft(fmt, 'postimport'):
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postimport(book_id, fmt, db)
            except Exception:
                print('Running file type plugin %s failed with traceback:' %
                      plugin.name)
                traceback.print_exc()


def run_plugins_on_postadd(db, book_id, fmt_map):
    customization = config['plugin_customization']
    for plugin in _on_postadd:
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postadd(book_id, fmt_map, db)
            except Exception:
                print('Running file type plugin %s failed with traceback:' %
                      plugin.name)
                traceback.print_exc()


# Plugin customization
def customize_plugin(plugin, custom):
    d = config['plugin_customization']
    d[plugin.name] = custom.strip()
    config['plugin_customization'] = d


def plugin_customization(plugin):
    return config['plugin_customization'].get(plugin.name, '')


# Input/Output profiles
def input_profiles():
    for plugin in _initialized_plugins:
        if isinstance(plugin, profiles.InputProfile):
            yield plugin


def output_profiles():
    for plugin in _initialized_plugins:
        if isinstance(plugin, profiles.OutputProfile):
            yield plugin


# Interface Actions #
def interface_actions():
    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.InterfaceActionBase):
            yield plugin


# Preferences Plugins
def preferences_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.PreferencesPlugin):
            plugin.site_customization = customization.get(plugin.name, '')
            yield plugin


# Library Closed Plugins
def available_library_closed_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.LibraryClosedPlugin):
            plugin.site_customization = customization.get(plugin.name, '')
            yield plugin


def has_library_closed_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.LibraryClosedPlugin):
            return True
    return False


# Store Plugins
def store_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.StoreBase):
            plugin.site_customization = customization.get(plugin.name, '')
            yield plugin


def available_store_plugins():
    for plugin in store_plugins():
        yield plugin


def stores():
    stores = set()
    for plugin in store_plugins():
        stores.add(plugin.name)
    return stores


def available_stores():
    stores = set()
    for plugin in available_store_plugins():
        stores.add(plugin.name)
    return stores


# Metadata read/write
_metadata_readers = {}
_metadata_writers = {}


def reread_metadata_plugins():
    global _metadata_readers
    global _metadata_writers
    _metadata_readers = collections.defaultdict(list)
    _metadata_writers = collections.defaultdict(list)
    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.MetadataReaderPlugin):
            for ft in plugin.file_types:
                _metadata_readers[ft].append(plugin)
        elif isinstance(plugin, customize.MetadataWriterPlugin):
            for ft in plugin.file_types:
                _metadata_writers[ft].append(plugin)

    # Ensure custom metadata plugins are used in preference to builtin
    # ones for a given filetype
    def key(plugin):
        return (1 if plugin.plugin_path is None else 0), plugin.name

    for group in (_metadata_readers, _metadata_writers):
        for plugins in group.values():
            if len(plugins) > 1:
                plugins.sort(key=key)


def metadata_readers():
    ans = set()
    for plugins in _metadata_readers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans


def metadata_writers():
    ans = set()
    for plugins in _metadata_writers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans


class QuickMetadata(object):

    def __init__(self):
        self.quick = False

    def __enter__(self):
        self.quick = True

    def __exit__(self, *args):
        self.quick = False


quick_metadata = QuickMetadata()


class ApplyNullMetadata(object):

    def __init__(self):
        self.apply_null = False

    def __enter__(self):
        self.apply_null = True

    def __exit__(self, *args):
        self.apply_null = False


apply_null_metadata = ApplyNullMetadata()


class ForceIdentifiers(object):

    def __init__(self):
        self.force_identifiers = False

    def __enter__(self):
        self.force_identifiers = True

    def __exit__(self, *args):
        self.force_identifiers = False


def get_file_type_metadata(stream, ftype):
    mi = metadata.MetaInformation(None, None)

    ftype = ftype.lower().strip()
    if ftype in _metadata_readers:
        for plugin in _metadata_readers[ftype]:
            with plugin:
                try:
                    plugin.quick = quick_metadata.quick
                    if hasattr(stream, 'seek'):
                        stream.seek(0)
                    mi = plugin.get_metadata(stream, ftype.lower().strip())
                    break
                except Exception:
                    traceback.print_exc()
                    continue
    return mi


def set_file_type_metadata(stream, mi, ftype, report_error=None):
    fi = ForceIdentifiers()
    ftype = ftype.lower().strip()
    if ftype in _metadata_writers:
        customization = config['plugin_customization']
        for plugin in _metadata_writers[ftype]:
            with plugin:
                try:
                    plugin.apply_null = apply_null_metadata.apply_null
                    plugin.force_identifiers = fi.force_identifiers
                    plugin.site_customization = customization.get(
                        plugin.name, '')
                    plugin.set_metadata(stream, mi, ftype.lower().strip())
                    break
                except Exception:
                    if report_error is None:
                        print('Failed to set metadata for the', ftype.upper(),
                              'format of:', getattr(mi, 'title', ''))
                        traceback.print_exc()
                    else:
                        report_error(mi, ftype, traceback.format_exc())


def can_set_metadata(ftype):
    ftype = ftype.lower().strip()
    for plugin in _metadata_writers.get(ftype, ()):
        return True
    return False


# Input/Output format plugins
def input_format_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, conversion.InputFormatPlugin):
            yield plugin


def plugin_for_input_format(fmt):
    customization = config['plugin_customization']
    for plugin in input_format_plugins():
        if fmt.lower() in plugin.file_types:
            plugin.site_customization = customization.get(plugin.name, None)
            return plugin


def all_input_formats():
    formats = set()
    for plugin in input_format_plugins():
        for format in plugin.file_types:
            formats.add(format)
    return formats


def available_input_formats():
    formats = set()
    for plugin in input_format_plugins():
        for format in plugin.file_types:
            formats.add(format)
    formats.add('zip')
    formats.add('rar')
    return formats


def output_format_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, conversion.OutputFormatPlugin):
            yield plugin


def plugin_for_output_format(fmt):
    customization = config['plugin_customization']
    for plugin in output_format_plugins():
        if fmt.lower() == plugin.file_type:
            plugin.site_customization = customization.get(plugin.name, None)
            return plugin


def available_output_formats():
    formats = set()
    for plugin in output_format_plugins():
        formats.add(plugin.file_type)
    return formats


# Catalog plugins
def catalog_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.CatalogPlugin):
            yield plugin


def available_catalog_formats():
    formats = set()
    for plugin in catalog_plugins():
        for format in plugin.file_types:
            formats.add(format)
    return formats


def plugin_for_catalog_format(fmt):
    for plugin in catalog_plugins():
        if fmt.lower() in plugin.file_types:
            return plugin


# Editor plugins
def all_edit_book_tool_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, customize.EditBookToolPlugin):
            yield plugin


# Initialize plugins
_initialized_plugins = []


def initialize_plugin(plugin, path_to_zip_file):
    try:
        p = plugin(path_to_zip_file)
        p.initialize()
        return p
    except Exception:
        print('Failed to initialize plugin:', plugin.name, plugin.version)
        tb = traceback.format_exc()
        raise customize.InvalidPlugin(('Initialization of plugin %s failed '
                                       'with traceback:' % tb) + '\n'+tb)


def has_external_plugins():
    'True if there are updateable (ZIP file based) plugins'
    return bool(config['plugins'])


def initialize_plugins():
    global _initialized_plugins
    _initialized_plugins = []
    external_plugins = config['plugins'].copy()
    for name in BLACKLISTED_PLUGINS:
        external_plugins.pop(name, None)
    ostdout, ostderr = sys.stdout, sys.stderr

    for zfp in list(external_plugins) + builtins.plugins:
        try:
            plugin = initialize_plugin(zfp, None)
            _initialized_plugins.append(plugin)
        except Exception:
            print('Failed to initialize plugin:', repr(zfp))
    sys.stdout, sys.stderr = ostdout, ostderr
    _initialized_plugins.sort(key=lambda x: x.priority, reverse=True)
    reread_filetype_plugins()
    reread_metadata_plugins()


initialize_plugins()


def initialized_plugins():
    for plugin in _initialized_plugins:
        yield plugin


# CLI

def option_parser():
    parser = cfg.OptionParser(usage='''\
    %prog options

    Customize calibre by loading external plugins.
    ''')
    parser.add_option('-a', '--add-plugin', default=None,
                      help='Add a plugin by specifying the path to the ZIP '
                      'file containing it.')
    parser.add_option('-b', '--build-plugin', default=None,
                      help='For plugin developers: Path to the directory '
                      'where you are developing the plugin. This command will '
                      'automatically zip up the plugin and update it in '
                      'calibre.')
    parser.add_option('-r', '--remove-plugin', default=None,
                      help='Remove a custom plugin by name. Has no effect on '
                      'builtin plugins')
    parser.add_option('--customize-plugin', default=None,
                      help='Customize plugin. Specify name of plugin and '
                      'customization string separated by a comma.')
    parser.add_option('-l', '--list-plugins', default=False,
                      action='store_true', help='List all installed plugins')
    parser.add_option('--enable-plugin', default=None,
                      help='Enable the named plugin')
    parser.add_option('--disable-plugin', default=None,
                      help='Disable the named plugin')
    return parser
