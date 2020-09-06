"""
Manage application-wide preferences.
"""
import copy
import optparse
import os
import traceback

from ebook_converter import constants
from ebook_converter import constants_old
from ebook_converter.utils.config_base import json_dumps, json_loads


class CustomHelpFormatter(optparse.IndentedHelpFormatter):

    def format_usage(self, usage):
        from ebook_converter.utils.terminal import colored
        parts = usage.split(' ')
        if parts:
            parts[0] = colored(parts[0], fg='yellow', bold=True)
        usage = ' '.join(parts)
        return colored('Usage', fg='blue', bold=True) + ': ' + usage

    def format_heading(self, heading):
        from ebook_converter.utils.terminal import colored
        return "%*s%s:\n" % (self.current_indent, '',
                             colored(heading, fg='blue', bold=True))

    def format_option(self, option):
        import textwrap
        from ebook_converter.utils.terminal import colored

        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "",
                                colored(opts, fg='green'))
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width +
                                  len(colored('', fg='green')),
                                  colored(opts, fg='green'))
            indent_first = 0
        result.append(opts)
        if option.help:
            help_text = self.expand_default(option).split('\n')
            help_lines = []

            for line in help_text:
                help_lines.extend(textwrap.wrap(line, self.help_width))
            result.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            result.extend(["%*s%s\n" % (self.help_position, "", line)
                           for line in help_lines[1:]])
        elif opts[-1] != "\n":
            result.append("\n")
        return "".join(result)+'\n'


class OptionParser(optparse.OptionParser):

    def __init__(self,
                 usage='%prog [options] filename',
                 version=None,
                 epilog=None,
                 gui_mode=False,
                 conflict_handler='resolve',
                 **kwds):
        import textwrap
        from ebook_converter.utils.terminal import colored

        usage = textwrap.dedent(usage)
        if epilog is None:
            epilog = 'Created by ' + colored(constants_old.__author__,
                                             fg='cyan')
        usage += ('\n\nWhenever you pass arguments to %prog that have spaces '
                  'in them, enclose the arguments in quotation marks. For '
                  'example: "{}"\n\n').format('/some path/with spaces')
        if version is None:
            version = '%%prog (%s %s)' % (constants_old.__appname__,
                                          constants.VERSION)
        optparse.OptionParser.__init__(self, usage=usage, version=version,
                                       epilog=epilog,
                                       formatter=CustomHelpFormatter(),
                                       conflict_handler=conflict_handler,
                                       **kwds)
        self.gui_mode = gui_mode

    def print_usage(self, file=None):
        from ebook_converter.utils.terminal import ANSIStream
        s = ANSIStream(file)
        optparse.OptionParser.print_usage(self, file=s)

    def print_help(self, file=None):
        from ebook_converter.utils.terminal import ANSIStream
        s = ANSIStream(file)
        optparse.OptionParser.print_help(self, file=s)

    def print_version(self, file=None):
        from ebook_converter.utils.terminal import ANSIStream
        s = ANSIStream(file)
        optparse.OptionParser.print_version(self, file=s)

    def error(self, msg):
        if self.gui_mode:
            raise Exception(msg)
        optparse.OptionParser.error(self, msg)

    def merge(self, parser):
        """
        Add options from parser to self. In case of conflicts, conflicting
        options from parser are skipped.
        """
        opts = list(parser.option_list)
        groups = list(parser.option_groups)

        def merge_options(options, container):
            for opt in copy.deepcopy(options):
                if not self.has_option(opt.get_opt_string()):
                    container.add_option(opt)

        merge_options(opts, self)

        for group in groups:
            g = self.add_option_group(group.title)
            merge_options(group.option_list, g)

    def subsume(self, group_name, msg=''):
        """
        Move all existing options into a subgroup named
        C{group_name} with description C{msg}.
        """
        opts = [opt for opt in self.options_iter()
                if opt.get_opt_string() not in ('--version', '--help')]
        self.option_groups = []
        subgroup = self.add_option_group(group_name, msg)
        for opt in opts:
            self.remove_option(opt.get_opt_string())
            subgroup.add_option(opt)

    def options_iter(self):
        for opt in self.option_list:
            if str(opt).strip():
                yield opt
        for gr in self.option_groups:
            for opt in gr.option_list:
                if str(opt).strip():
                    yield opt

    def option_by_dest(self, dest):
        for opt in self.options_iter():
            if opt.dest == dest:
                return opt

    def merge_options(self, lower, upper):
        """
        Merge options in lower and upper option lists into upper.
        Default values in upper are overridden by
        non default values in lower.
        """
        for dest in lower.__dict__.keys():
            if dest not in upper.__dict__:
                continue
            opt = self.option_by_dest(dest)
            if lower.__dict__[dest] != opt.default and \
               upper.__dict__[dest] == opt.default:
                upper.__dict__[dest] = lower.__dict__[dest]

    def add_option_group(self, *args, **kwargs):
        if isinstance(args[0], (str, bytes)):
            args = list(args)
        return optparse.OptionParser.add_option_group(self, *args, **kwargs)


class JSONConfig(dict):

    EXTENSION = '.json'

    def __init__(self, relative_conf_file):
        dict.__init__(self)
        self.no_commit = False
        self.defaults = {}
        self.file_path = os.path.join(self._get_cache_dir(),
                                      relative_conf_file)

        if not self.file_path.endswith(self.EXTENSION):
            self.file_path += self.EXTENSION

        self.refresh()

    def mtime(self):
        try:
            return os.path.getmtime(self.file_path)
        except EnvironmentError:
            return 0

    def touch(self):
        try:
            os.utime(self.file_path, None)
        except EnvironmentError:
            pass

    def raw_to_object(self, raw):
        return json_loads(raw)

    def to_raw(self):
        return json_dumps(self)

    def decouple(self, prefix):
        self.file_path = os.path.join(os.path.dirname(self.file_path),
                                      prefix +
                                      os.path.basename(self.file_path))
        self.refresh()

    def refresh(self, clear_current=True):
        d = {}
        if os.path.exists(self.file_path):
            with open(self.file_path) as f:
                raw = f.read()
                try:
                    d = self.raw_to_object(raw) if raw.strip() else {}
                except SystemError:
                    pass
                except Exception:
                    traceback.print_exc()
                    d = {}
        if clear_current:
            self.clear()
        self.update(d)

    def _get_cache_dir(self):
        if os.getenv('XDG_CACHE_HOME'):
            return os.getenv('XDG_CACHE_HOME')
        return os.path.join(os.path.expanduser('~/'), '.cache')

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]

    def get(self, key, default=None):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, default)

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)
        self.commit()

    def set(self, key, val):
        self.__setitem__(key, val)

    def __delitem__(self, key):
        try:
            dict.__delitem__(self, key)
        except KeyError:
            pass  # ignore missing keys
        else:
            self.commit()

    def commit(self):
        if self.no_commit:
            return
        if hasattr(self, 'file_path') and self.file_path:
            dpath = os.path.dirname(self.file_path)
            if not os.path.exists(dpath):
                os.makedirs(dpath, mode=constants_old.CONFIG_DIR_MODE)
            with open(self.file_path, 'w') as f:
                raw = self.to_raw()
                f.seek(0)
                f.truncate()
                # TODO(gryf): get rid of another proxy for json module which
                # stubbornly insist on using bytes instead of unicode objects
                f.write(raw.decode('utf-8'))

    def __enter__(self):
        self.no_commit = True

    def __exit__(self, *args):
        self.no_commit = False
        self.commit()
