#!/usr/bin/env python
import sys

# TODO: remove this crap
sys.resources_location = ''
sys.extensions_location = '/usr/lib64/calibre/calibre/plugins'
sys.executables_location = '/usr/bin'

from ebook_converter.ebooks.conversion.cli import main


def run():
    sys.exit(main())


if __name__ == '__main__':
    run()
