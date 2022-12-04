#!/usr/bin/env python
import argparse
import os
import sys

from ebook_converter import logging
from ebook_converter.ebooks.conversion.plumber import Plumber


LOG = logging.default_log


def abspath(x):
    if x.startswith('http:') or x.startswith('https:'):
        return x
    return os.path.abspath(os.path.expanduser(x))


def progress_bar(frac, msg=''):
    # TODO(gryf): get rid of this crap - this is used by plumber under
    # ui_reporter and self.global_reporter
    if msg:
        percent = int(frac * 100)
        LOG.info('%d%% %s' % (percent, msg))


def create_option_parser(args):

    # parser = option_parser()

    input_file, output_file = args.from_file, args.to_file

    if os.path.abspath(input_file) == os.path.abspath(output_file):
        raise ValueError('Input file is the same as the output file')

    # TODO(gryf): Plumber has to be imported late, because first mimetypes
    # needs to be updated.
    plumber = Plumber(input_file, output_file, LOG, progress_bar)
    # add_input_output_options(parser, plumber)
    # add_pipeline_options(parser, plumber)

    return plumber


def run(args):

    plumber = create_option_parser(args)

    # TODO(gryf): perhaps there is a need to recreate commandline options for
    # certain formats - for sure it's needed to consider if they have some
    # sense or not.

    # opts, leftover_args = parser.parse_args(args)

    # for x in ('read_metadata_from_opf', 'cover'):
        # if getattr(opts, x, None) is not None:
            # setattr(opts, x, abspath(getattr(opts, x)))

    # recommendations = [(n.dest, getattr(opts, n.dest),
    # OptionRecommendation.HIGH)
    # for n in parser.options_iter() if n.dest]
    # plumber.merge_ui_recommendations(recommendations)

    plumber.run()

    LOG.info('Output saved to %s', plumber.output)

    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('from_file', help="Input file to be converted")
    parser.add_argument('to_file', help="Output file to be written to")
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='be verbose. Adding more "v" will increase '
                        'verbosity')
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='suppress output. Adding more "q" will make '
                        'boxpy to shut up.')

    args = parser.parse_args()

    LOG.set_verbose(args.verbose, args.quiet)

    sys.exit(run(args))
