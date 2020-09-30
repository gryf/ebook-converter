"""
Command line interface to conversion sub-system
"""
import collections
import json
import mimetypes
import numbers
import optparse
import os
import pkg_resources
import re
import sys

from ebook_converter.utils.config import OptionParser
from ebook_converter.utils.logging import Log
from ebook_converter.customize.conversion import OptionRecommendation


USAGE = '%prog ' + '''\
input_file output_file [options]

Convert an e-book from one format to another.

input_file is the input and output_file is the output. Both must be \
specified as the first two arguments to the command.

The output e-book format is guessed from the file extension of \
output_file. output_file can also be of the special format .EXT where \
EXT is the output file extension. In this case, the name of the output \
file is derived from the name of the input file. Note that the filenames must \
not start with a hyphen. Finally, if output_file has no extension, then \
it is treated as a directory and an "open e-book" (OEB) consisting of HTML \
files is written to that directory. These files are the files that would \
normally have been passed to the output plugin.

After specifying the input \
and output file you can customize the conversion by specifying various \
options. The available options depend on the input and output file types. \
To get help on them specify the input and output file and then use the -h \
option.

For full documentation of the conversion system see
https://manual.calibre-ebook.com/conversion.html
'''

HEURISTIC_OPTIONS = ['markup_chapter_headings', 'italicize_common_cases',
                     'fix_indents', 'html_unwrap_factor', 'unwrap_lines',
                     'delete_blank_paragraphs', 'format_scene_breaks',
                     'dehyphenate', 'renumber_headings',
                     'replace_scene_breaks']

DEFAULT_TRUE_OPTIONS = HEURISTIC_OPTIONS + ['remove_fake_margins']


def print_help(parser):
    parser.print_help()


def check_command_line_options(parser, args, log):
    if len(args) < 3 or args[1].startswith('-') or args[2].startswith('-'):
        print_help(parser)
        log.error('\n\nYou must specify the input AND output files')
        raise SystemExit(1)

    input_file = os.path.abspath(args[1])
    if (not input_file.endswith('.recipe') and
            not os.access(input_file, os.R_OK) and
            not ('-h' in args or '--help' in args)):
        log.error('Cannot read from', input_file)
        raise SystemExit(1)
    if input_file.endswith('.recipe') and not os.access(input_file, os.R_OK):
        input_file = args[1]

    output_file = args[2]
    if (output_file.startswith('.') and
            output_file[:2] not in {'..', '.'} and
            '/' not in output_file and '\\' not in output_file):
        output_file = os.path.splitext(os.path
                                       .basename(input_file))[0] + output_file
    output_file = os.path.abspath(output_file)

    return input_file, output_file


def option_recommendation_to_cli_option(add_option, rec):
    opt = rec.option
    switches = ['-'+opt.short_switch] if opt.short_switch else []
    switches.append('--'+opt.long_switch)
    attrs = dict(dest=opt.name, help=opt.help, choices=opt.choices,
                 default=rec.recommended_value)
    if isinstance(rec.recommended_value, type(True)):
        attrs['action'] = 'store_false' if rec.recommended_value else \
                          'store_true'
    else:
        if isinstance(rec.recommended_value, numbers.Integral):
            attrs['type'] = 'int'
        if isinstance(rec.recommended_value, numbers.Real):
            attrs['type'] = 'float'

    if opt.long_switch == 'verbose':
        attrs['action'] = 'count'
        attrs.pop('type', '')
    if opt.name == 'read_metadata_from_opf':
        switches.append('--from-opf')
    if opt.name == 'transform_css_rules':
        attrs['help'] = ('Path to a file containing rules to transform the '
                         'CSS styles in this book. The easiest way to create '
                         'such a file is to use the wizard for creating rules '
                         'in the calibre GUI. Access it in the "Look & '
                         'feel->Transform styles" section of the conversion '
                         'dialog. Once you create the rules, you can use the '
                         '"Export" button to save them to a file.')
    if opt.name in DEFAULT_TRUE_OPTIONS and rec.recommended_value is True:
        switches = ['--disable-'+opt.long_switch]
    add_option(optparse.Option(*switches, **attrs))


def group_titles():
    return 'INPUT OPTIONS', 'OUTPUT OPTIONS'


def recipe_test(option, opt_str, value, parser):
    assert value is None
    value = []

    def floatable(s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    for arg in parser.rargs:
        # stop on --foo like options
        if arg[:2] == "--":
            break
        # stop on -a, but not on -3 or -3.0
        if arg[:1] == "-" and len(arg) > 1 and not floatable(arg):
            break
        try:
            value.append(int(arg))
        except (TypeError, ValueError, AttributeError):
            break
        if len(value) == 2:
            break
    del parser.rargs[:len(value)]

    while len(value) < 2:
        value.append(2)

    setattr(parser.values, option.dest, tuple(value))


def add_input_output_options(parser, plumber):
    input_options, output_options = \
                                plumber.input_options, plumber.output_options

    def add_options(group, options):
        for opt in options:
            if (plumber.input_fmt == 'recipe' and
                    opt.option.long_switch == 'test'):
                group(optparse.Option('--test', dest='test',
                                      action='callback', callback=recipe_test))
            else:
                option_recommendation_to_cli_option(group, opt)

    if input_options:
        title = group_titles()[0]
        io = optparse.OptionGroup(parser, title, 'Options to control the '
                                  'processing of the input %s file' %
                                  plumber.input_fmt)
        add_options(io.add_option, input_options)
        parser.add_option_group(io)

    if output_options:
        title = group_titles()[1]
        oo = optparse.OptionGroup(parser, title, 'Options to control the '
                                  'processing of the output %s' %
                                  plumber.output_fmt)
        add_options(oo.add_option, output_options)
        parser.add_option_group(oo)


def add_pipeline_options(parser, plumber):
    groups = collections.OrderedDict(
        (('', ('', ['input_profile', 'output_profile'])),
         ('LOOK AND FEEL', ('Options to control the look and feel of the '
                            'output',
                            ['base_font_size', 'disable_font_rescaling',
                             'font_size_mapping', 'embed_font_family',
                             'subset_embedded_fonts', 'embed_all_fonts',
                             'line_height', 'minimum_line_height',
                             'linearize_tables', 'extra_css', 'filter_css',
                             'transform_css_rules', 'expand_css',
                             'smarten_punctuation', 'unsmarten_punctuation',
                             'margin_top', 'margin_left', 'margin_right',
                             'margin_bottom', 'change_justification',
                             'insert_blank_line', 'insert_blank_line_size',
                             'remove_paragraph_spacing',
                             'remove_paragraph_spacing_indent_size',
                             'asciiize', 'keep_ligatures'])),

         ('HEURISTIC PROCESSING', ('Modify the document text and structure '
                                   'using common patterns. Disabled by '
                                   'default. Use %(en)s to enable. Individual '
                                   'actions can be disabled with the %(dis)s '
                                   'options.' % dict(en='--enable-heuristics',
                                                     dis='--disable-*'),
                                   ['enable_heuristics'] + HEURISTIC_OPTIONS)),

         ('SEARCH AND REPLACE', ('Modify the document text and structure '
                                 'using user defined patterns.',
                                 ['sr1_search', 'sr1_replace', 'sr2_search',
                                  'sr2_replace', 'sr3_search', 'sr3_replace',
                                  'search_replace'])),

         ('STRUCTURE DETECTION', ('Control auto-detection of document '
                                  'structure.',
                                  ['chapter', 'chapter_mark',
                                   'prefer_metadata_cover',
                                   'remove_first_image', 'insert_metadata',
                                   'page_breaks_before', 'remove_fake_margins',
                                   'start_reading_at'])),

         ('TABLE OF CONTENTS', ('Control the automatic generation of a Table '
                                'of Contents. By default, if the source file '
                                'has a Table of Contents, it will be used in '
                                'preference to the automatically generated '
                                'one.',
                                ['level1_toc', 'level2_toc', 'level3_toc',
                                 'toc_threshold', 'max_toc_links',
                                 'no_chapters_in_toc', 'use_auto_toc',
                                 'toc_filter', 'duplicate_links_in_toc'])),

         ('METADATA', ('Options to set metadata in the output',
                       plumber.metadata_option_names +
                       ['read_metadata_from_opf'])),
         ('DEBUG', ('Options to help with debugging the conversion',
                    ['verbose', 'debug_pipeline']))))

    for group, (desc, options) in groups.items():
        if group:
            group = optparse.OptionGroup(parser, group, desc)
            parser.add_option_group(group)
        add_option = group.add_option if group != '' else parser.add_option

        for name in options:
            rec = plumber.get_option_by_name(name)
            if rec.level < rec.HIGH:
                option_recommendation_to_cli_option(add_option, rec)


def option_parser():
    parser = OptionParser(usage=USAGE)
    parser.add_option('--list-recipes', default=False, action='store_true',
                      help='List builtin recipe names. You can create an '
                      'e-book from a builtin recipe like this: ebook-convert '
                      '"Recipe Name.recipe" output.epub')
    return parser


class ProgressBar(object):

    def __init__(self, log):
        self.log = log

    def __call__(self, frac, msg=''):
        if msg:
            percent = int(frac*100)
            self.log('%d%% %s' % (percent, msg))


def create_option_parser(args, log):
    if '--version' in args:
        from ebook_converter.constants_old import __appname__
        from ebook_converter.constants_old import __author__
        from ebook_converter.constants_old import __version__
        log(os.path.basename(args[0]), '('+__appname__, __version__+')')
        log('Created by:', __author__)
        raise SystemExit(0)
    if '--list-recipes' in args:
        from ebook_converter.web.feeds.recipes.collection import \
                get_builtin_recipe_titles
        log('Available recipes:')
        titles = sorted(get_builtin_recipe_titles())
        for title in titles:
            try:
                log('\t'+title)
            except Exception:
                log('\t'+repr(title))
        log('%d recipes available' % len(titles))
        raise SystemExit(0)

    parser = option_parser()
    if len(args) < 3:
        print_help(parser)
        if any(x in args for x in ('-h', '--help')):
            raise SystemExit(0)
        else:
            raise SystemExit(1)

    input_file, output_file = check_command_line_options(parser, args, log)

    from ebook_converter.ebooks.conversion.plumber import Plumber

    reporter = ProgressBar(log)
    if os.path.abspath(input_file) == os.path.abspath(output_file):
        raise ValueError('Input file is the same as the output file')

    plumber = Plumber(input_file, output_file, log, reporter)
    add_input_output_options(parser, plumber)
    add_pipeline_options(parser, plumber)

    return parser, plumber


def abspath(x):
    if x.startswith('http:') or x.startswith('https:'):
        return x
    return os.path.abspath(os.path.expanduser(x))


def escape_sr_pattern(exp):
    return exp.replace('\n', '\ue123')


def read_sr_patterns(path, log=None):
    pats = []
    with open(path, 'rb') as f:
        lines = f.read().decode('utf-8').splitlines()
    pat = None
    for line in lines:
        if pat is None:
            if not line.strip():
                continue
            line = line.replace('\ue123', '\n')
            try:
                re.compile(line)
            except Exception:
                msg = 'Invalid regular expression: %r from file: %r' % (line,
                                                                        path)
                if log is not None:
                    log.error(msg)
                    raise SystemExit(1)
                else:
                    raise ValueError(msg)
            pat = line
        else:
            pats.append((pat, line))
            pat = None
    return json.dumps(pats)


def main(args=sys.argv):
    log = Log()
    mimetypes.init([pkg_resources.resource_filename('ebook_converter',
                                                    'data/mime.types')])
    parser, plumber = create_option_parser(args, log)
    opts, leftover_args = parser.parse_args(args)
    if len(leftover_args) > 3:
        log.error('Extra arguments not understood: %s',
                  ', '.join(leftover_args[3:]))
        return 1
    for x in ('read_metadata_from_opf', 'cover'):
        if getattr(opts, x, None) is not None:
            setattr(opts, x, abspath(getattr(opts, x)))
    if opts.search_replace:
        opts.search_replace = read_sr_patterns(opts.search_replace, log)
    if opts.transform_css_rules:
        from ebook_converter.ebooks.css_transform_rules import import_rules
        from ebook_converter.ebooks.css_transform_rules import validate_rule
        with open(opts.transform_css_rules, 'rb') as tcr:
            opts.transform_css_rules = rules = list(import_rules(tcr.read()))
            for rule in rules:
                title, msg = validate_rule(rule)
                if title and msg:
                    log.error('Failed to parse CSS transform rules')
                    log.error(title)
                    log.error(msg)
                    return 1

    recommendations = [(n.dest, getattr(opts, n.dest),
                        OptionRecommendation.HIGH)
                       for n in parser.options_iter() if n.dest]
    plumber.merge_ui_recommendations(recommendations)

    plumber.run()

    log('Output saved to', ' ', plumber.output)

    return 0


def manual_index_strings():
    return '''\
The options and default values for the options change depending on both the
input and output formats, so you should always check with::

    %s

Below are the options that are common to all conversion, followed by the
options specific to every input and output format.'''


if __name__ == '__main__':
    sys.exit(main())
