import base64
import collections
import copy
import datetime
import functools
import json
import numbers
import os
import pickle
import pkg_resources
import re
import traceback

from ebook_converter.constants_old import config_dir
from ebook_converter.constants_old import filesystem_encoding
from ebook_converter.constants_old import preferred_encoding
from ebook_converter.utils.date import isoformat
from ebook_converter.utils import iso8601

plugin_dir = os.path.join(config_dir, 'plugins')


def parse_old_style(src):
    options = {'cPickle': pickle}
    try:
        if not isinstance(src, str):
            src = src.decode('utf-8')
        src = src.replace('PyQt%d.QtCore' % 4, 'PyQt5.QtCore')
        src = re.sub(r'cPickle\.loads\(([\'"])', r'cPickle.loads(b\1', src)
        exec(src, options)
    except Exception as err:
        try:
            print('Failed to parse old style options string with error: '
                  '{}'.format(err))
        except Exception:
            pass
    return options


def to_json(obj):
    if isinstance(obj, bytearray):
        return {'__class__': 'bytearray',
                '__value__': base64.standard_b64encode(bytes(obj))
                             .decode('ascii')}
    if isinstance(obj, datetime.datetime):
        return {'__class__': 'datetime.datetime',
                '__value__': isoformat(obj, as_utc=True)}
    if isinstance(obj, (set, frozenset)):
        return {'__class__': 'set', '__value__': tuple(obj)}
    if isinstance(obj, bytes):
        return obj.decode('utf-8')
    if hasattr(obj, 'toBase64'):  # QByteArray
        return {'__class__': 'bytearray',
                '__value__': bytes(obj.toBase64()).decode('ascii')}
    raise TypeError(repr(obj) + ' is not JSON serializable')


def safe_to_json(obj):
    try:
        return to_json(obj)
    except Exception:
        pass


def from_json(obj):
    custom = obj.get('__class__')
    if custom is not None:
        if custom == 'bytearray':
            return bytearray(base64.standard_b64decode(obj['__value__']
                                                       .encode('ascii')))
        if custom == 'datetime.datetime':
            return iso8601.parse_iso8601(obj['__value__'], assume_utc=True)
        if custom == 'set':
            return set(obj['__value__'])
    return obj


def force_unicode(x):
    try:
        return x.decode(preferred_encoding)
    except UnicodeDecodeError:
        try:
            return x.decode(filesystem_encoding)
        except UnicodeDecodeError:
            return x.decode('utf-8', 'replace')


def force_unicode_recursive(obj):
    if isinstance(obj, bytes):
        return force_unicode(obj)
    if isinstance(obj, (list, tuple)):
        return type(obj)(map(force_unicode_recursive, obj))
    if isinstance(obj, dict):
        return {force_unicode_recursive(k): force_unicode_recursive(v)
                for k, v in obj.items()}
    return obj


def json_dumps(obj, ignore_unserializable=False):
    try:
        ans = json.dumps(obj, indent=2, default=safe_to_json
                         if ignore_unserializable
                         else to_json, sort_keys=True, ensure_ascii=False)
    except UnicodeDecodeError:
        obj = force_unicode_recursive(obj)
        ans = json.dumps(obj, indent=2, default=safe_to_json
                         if ignore_unserializable
                         else to_json, sort_keys=True, ensure_ascii=False)
    if not isinstance(ans, bytes):
        ans = ans.encode('utf-8')
    return ans


def json_loads(raw):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    return json.loads(raw, object_hook=from_json)


class Option(object):

    def __init__(self, name, switches=[], help='', type=None, choices=None,
                 check=None, group=None, default=None, action=None,
                 metavar=None):
        if choices:
            type = 'choice'

        self.name = name
        self.switches = switches
        self.help = help.replace('%default', repr(default)) if help else None
        self.type = type
        if self.type is None and action is None and choices is None:
            if isinstance(default, float):
                self.type = 'float'
            elif (isinstance(default, numbers.Integral) and
                  not isinstance(default, bool)):
                self.type = 'int'

        self.choices = choices
        self.check = check
        self.group = group
        self.default = default
        self.action = action
        self.metavar = metavar

    def __eq__(self, other):
        return self.name == getattr(other, 'name', other)

    def __repr__(self):
        return 'Option: '+self.name

    def __str__(self):
        return repr(self)


class OptionValues(object):

    def copy(self):
        return copy.deepcopy(self)


class OptionSet(object):

    OVERRIDE_PAT = re.compile(r'#{3,100} Override Options #{15}(.*?)#{3,100} '
                              'End Override #{3,100}',
                              re.DOTALL | re.IGNORECASE)

    def __init__(self, description=''):
        self.description = description
        self.defaults = {}
        self.preferences = []
        self.group_list = []
        self.groups = {}
        self.set_buffer = {}
        self.loads_pat = None

    def has_option(self, name_or_option_object):
        if name_or_option_object in self.preferences:
            return True
        for p in self.preferences:
            if p.name == name_or_option_object:
                return True
        return False

    def get_option(self, name_or_option_object):
        idx = self.preferences.index(name_or_option_object)
        if idx > -1:
            return self.preferences[idx]
        for p in self.preferences:
            if p.name == name_or_option_object:
                return p

    def add_group(self, name, description=''):
        if name in self.group_list:
            raise ValueError('A group by the name %s already exists in this '
                             'set' % name)
        self.groups[name] = description
        self.group_list.append(name)
        return functools.partial(self.add_opt, group=name)

    def update(self, other):
        for name in other.groups.keys():
            self.groups[name] = other.groups[name]
            if name not in self.group_list:
                self.group_list.append(name)
        for pref in other.preferences:
            if pref in self.preferences:
                self.preferences.remove(pref)
            self.preferences.append(pref)

    def smart_update(self, opts1, opts2):
        """
        Updates the preference values in opts1 using only the non-default
        preference values in opts2.
        """
        for pref in self.preferences:
            new = getattr(opts2, pref.name, pref.default)
            if new != pref.default:
                setattr(opts1, pref.name, new)

    def remove_opt(self, name):
        if name in self.preferences:
            self.preferences.remove(name)

    def add_opt(self, name, switches=[], help=None, type=None, choices=None,
                group=None, default=None, action=None, metavar=None):
        """
        Add an option to this section.

        :param name: The name of this option. Must be a valid Python
                     identifier. Must also be unique in this OptionSet and all
                     its subsets.
        :param switches: List of command line switches for this option (as
                         supplied to :module:`optparse`). If empty, this option
                         will not be added to the command line parser.
        :param help: Help text.
        :param type: Type checking of option values. Supported types are:
                     `None, 'choice', 'complex', 'float', 'int', 'string'`.
        :param choices: List of strings or `None`.
        :param group: Group this option belongs to. You must previously
                      have created this group with a call to
                      :method:`add_group`.
        :param default: The default value for this option.
        :param action: The action to pass to optparse. Supported values are:
                       `None, 'count'`. For choices and boolean options,
                       action is automatically set correctly.
        """
        pref = Option(name, switches=switches, help=help, type=type,
                      choices=choices, group=group, default=default,
                      action=action, metavar=None)
        if group is not None and group not in self.groups.keys():
            raise ValueError('Group %s has not been added to this section' %
                             group)

        if pref in self.preferences:
            raise ValueError('An option with the name %s already exists in '
                             'this set.' % name)
        self.preferences.append(pref)
        self.defaults[name] = default

    def option_parser(self, user_defaults=None, usage='', gui_mode=False):
        from ebook_converter.utils.config import OptionParser
        parser = OptionParser(usage, gui_mode=gui_mode)
        groups = collections.defaultdict(lambda: parser)
        for group, desc in self.groups.items():
            groups[group] = parser.add_option_group(group.upper(), desc)

        for pref in self.preferences:
            if not pref.switches:
                continue
            g = groups[pref.group]
            action = pref.action
            if action is None:
                action = 'store'
                if pref.default is True or pref.default is False:
                    action = 'store_' + ('false' if pref.default else 'true')
            args = {'dest': pref.name,
                    'help': pref.help,
                    'metavar': pref.metavar,
                    'type': pref.type,
                    'choices': pref.choices,
                    'default': getattr(user_defaults, pref.name, pref.default),
                    'action': action}
            g.add_option(*pref.switches, **args)

        return parser

    def get_override_section(self, src):
        match = self.OVERRIDE_PAT.search(src)
        if match:
            return match.group()
        return ''

    def parse_string(self, src):
        options = {}
        if src:
            is_old_style = (isinstance(src, bytes) and
                            src.startswith(b'#')) or (isinstance(src, str) and
                                                      src.startswith(u'#'))
            if is_old_style:
                options = parse_old_style(src)
            else:
                try:
                    options = json_loads(src)
                    if not isinstance(options, dict):
                        raise Exception('options is not a dictionary')
                except Exception as err:
                    try:
                        print('Failed to parse options string with error: {}'
                              .format(err))
                    except Exception:
                        pass
        opts = OptionValues()
        for pref in self.preferences:
            val = options.get(pref.name, pref.default)
            formatter = __builtins__.get(pref.type, None)
            if callable(formatter):
                val = formatter(val)
            setattr(opts, pref.name, val)

        return opts

    def serialize(self, opts, ignore_unserializable=False):
        data = {pref.name: getattr(opts, pref.name, pref.default)
                for pref in self.preferences}
        return json_dumps(data, ignore_unserializable=ignore_unserializable)


class ConfigInterface(object):

    def __init__(self, description):
        self.option_set = OptionSet(description=description)
        self.add_opt = self.option_set.add_opt
        self.add_group = self.option_set.add_group
        self.remove_opt = self.remove = self.option_set.remove_opt
        self.parse_string = self.option_set.parse_string
        self.get_option = self.option_set.get_option
        self.preferences = self.option_set.preferences

    def update(self, other):
        self.option_set.update(other.option_set)

    def option_parser(self, usage='', gui_mode=False):
        return self.option_set.option_parser(user_defaults=self.parse(),
                                             usage=usage, gui_mode=gui_mode)

    def smart_update(self, opts1, opts2):
        self.option_set.smart_update(opts1, opts2)


class Config(ConfigInterface):
    """
    A file based configuration.
    """

    def __init__(self, basename, description=''):
        ConfigInterface.__init__(self, description)
        self.filename_base = basename

    @property
    def config_file_path(self):
        return os.path.join(config_dir, self.filename_base + '.py.json')

    def parse(self):
        src = ''
        migrate = False
        path = self.config_file_path
        if os.path.exists(path):
            with open(path) as f:
                try:
                    src = f.read()
                except ValueError:
                    print("Failed to parse", path)
                    traceback.print_exc()
        if not src:
            path = path.rpartition('.')[0]
            try:
                with open(path, 'rb') as f:
                    src = f.read()
            except Exception:
                pass
            else:
                migrate = bool(src)
        ans = self.option_set.parse_string(src)
        if migrate:
            new_src = self.option_set.serialize(ans,
                                                ignore_unserializable=True)
            with open(self.config_file_path, 'w') as f:
                f.seek(0), f.truncate()
                f.write(new_src)
        return ans

    def set(self, name, val):
        if not self.option_set.has_option(name):
            raise ValueError('The option %s is not defined.' % name)


class StringConfig(ConfigInterface):
    """
    A string based configuration
    """

    def __init__(self, src, description=''):
        ConfigInterface.__init__(self, description)
        self.set_src(src)

    def set_src(self, src):
        self.src = src
        if isinstance(self.src, bytes):
            self.src = self.src.decode('utf-8')

    def parse(self):
        return self.option_set.parse_string(self.src)

    def set(self, name, val):
        if not self.option_set.has_option(name):
            raise ValueError('The option %s is not defined.' % name)

        opts = self.option_set.parse_string(self.src)
        setattr(opts, name, val)
        self.set_src(self.option_set.serialize(opts))


class ConfigProxy(object):
    """
    A Proxy to minimize file reads for widely used config settings
    """

    def __init__(self, config):
        self.__config = config
        self.__opts = None

    @property
    def defaults(self):
        return self.__config.option_set.defaults

    def refresh(self):
        self.__opts = self.__config.parse()

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, val):
        return self.set(key, val)

    def __delitem__(self, key):
        self.set(key, self.defaults[key])

    def get(self, key):
        if self.__opts is None:
            self.refresh()
        return getattr(self.__opts, key)

    def set(self, key, val):
        if self.__opts is None:
            self.refresh()
        setattr(self.__opts, key, val)
        return self.__config.set(key, val)

    def help(self, key):
        return self.__config.get_option(key).help


def create_global_prefs(conf_obj=None):
    c = Config('global',
               'calibre wide preferences') if conf_obj is None else conf_obj
    c.add_opt('database_path',
              default=os.path.expanduser('~/library1.db'),
              help='Path to the database in which books are stored')
    c.add_opt('filename_pattern', default=u'(?P<title>.+) - (?P<author>[^_]+)',
              help='Pattern to guess metadata from filenames')
    c.add_opt('isbndb_com_key', default='',
              help='Access key for isbndb.com')
    c.add_opt('network_timeout', default=5,
              help='Default timeout for network operations (seconds)')
    c.add_opt('library_path', default=None,
              help='Path to directory in which your library of books is '
              'stored')
    c.add_opt('language', default=None,
              help='The language in which to display the user interface')
    c.add_opt('output_format', default='EPUB', help='The default output '
              'format for e-book conversions. When auto-converting to send to '
              'a device this can be overridden by individual device '
              'preferences. These can be changed by right clicking the device '
              'icon in calibre and choosing "Configure".')
    c.add_opt('input_format_order',
              default=['EPUB', 'AZW3', 'MOBI', 'LIT', 'PRC', 'FB2', 'HTML',
                       'HTM', 'XHTM', 'SHTML', 'XHTML', 'ZIP', 'DOCX', 'ODT',
                       'RTF', 'PDF', 'TXT'],
              help='Ordered list of formats to prefer for input.')
    c.add_opt('read_file_metadata', default=True,
              help='Read metadata from files')
    c.add_opt('worker_process_priority', default='normal',
              help='The priority of worker processes. A higher priority '
              'means they run faster and consume more resources. '
              'Most tasks like conversion/news download/adding books/etc. '
              'are affected by this setting.')
    c.add_opt('swap_author_names', default=False,
              help='Swap author first and last names when reading metadata')
    c.add_opt('add_formats_to_existing', default=False,
              help='Add new formats to existing book records')
    c.add_opt('check_for_dupes_on_ctl', default=False,
              help='Check for duplicates when copying to another library')
    c.add_opt('new_book_tags', default=[],
              help='Tags to apply to books added to the library')
    c.add_opt('mark_new_books', default=False, help='Mark newly added books. '
              'The mark is a temporary mark that is automatically removed '
              'when calibre is restarted.')

    # these are here instead of the gui preferences because calibredb and
    # calibre server can execute searches
    c.add_opt('saved_searches', default={},
              help='List of named saved searches')
    c.add_opt('user_categories', default={},
              help='User-created Tag browser categories')
    c.add_opt('manage_device_metadata', default='manual',
              help='How and when calibre updates metadata on the device.')
    c.add_opt('limit_search_columns', default=False,
              help='When searching for text without using lookup '
              'prefixes, as for example, Red instead of title:Red, '
              'limit the columns searched to those named below.')
    c.add_opt('limit_search_columns_to',
              default=['title', 'authors', 'tags', 'series', 'publisher'],
              help='Choose columns to be searched when not using prefixes, '
              'as for example, when searching for Red instead of '
              'title:Red. Enter a list of search/lookup names '
              'separated by commas. Only takes effect if you set the option '
              'to limit search columns above.')
    c.add_opt('use_primary_find_in_search', default=True,
              help=u'Characters typed in the search box will match their '
              'accented versions, based on the language you have chosen '
              'for the calibre interface. For example, in '
              u'English, searching for n will match both {} and n, but if '
              'your language is Spanish it will only match n. Note that '
              'this is much slower than a simple search on very large '
              'libraries. Also, this option will have no effect if you turn '
              'on case-sensitive searching')
    c.add_opt('case_sensitive', default=False,
              help='Make searches case-sensitive')

    c.add_opt('migrated', default=False,
              help='For Internal use. Don\'t modify.')
    return c


prefs = ConfigProxy(create_global_prefs())

# Read tweaks


def tweaks_file():
    return os.path.join(config_dir, 'tweaks.json')


def make_unicode(obj):
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return obj.decode(preferred_encoding, errors='replace')
    if isinstance(obj, (list, tuple)):
        return list(map(make_unicode, obj))
    if isinstance(obj, dict):
        return {make_unicode(k): make_unicode(v) for k, v in obj.items()}
    return obj


def normalize_tweak(val):
    if isinstance(val, (list, tuple)):
        return tuple(map(normalize_tweak, val))
    if isinstance(val, dict):
        return {k: normalize_tweak(v) for k, v in val.items()}
    return val


def exec_tweaks(path):
    if isinstance(path, bytes):
        raw = path
        fname = '<string>'
    else:
        with open(path, 'rb') as f:
            raw = f.read()
            fname = f.name
    code = compile(raw, fname, 'exec')
    x = {}
    g = {'__file__': fname}
    exec(code, g, x)
    return x


def default_tweaks_raw():
    return pkg_resources.resource_filename('ebook_converter',
                                           'data/default_tweaks.py')


def read_tweaks():
    return exec_tweaks(default_tweaks_raw())


tweaks = read_tweaks()


def reset_tweaks_to_default():
    default_tweaks = exec_tweaks(default_tweaks_raw())
    tweaks.clear()
    tweaks.update(default_tweaks)


class Tweak(object):

    def __init__(self, name, value):
        self.name, self.value = name, value

    def __enter__(self):
        self.origval = tweaks[self.name]
        tweaks[self.name] = self.value

    def __exit__(self, *args):
        tweaks[self.name] = self.origval
