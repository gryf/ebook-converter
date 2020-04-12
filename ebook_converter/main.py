#!/usr/bin/env python
import sys

from ebook_converter.ebooks.conversion.cli import main


def run():
    sys.exit(main())


if __name__ == '__main__':
    run()
