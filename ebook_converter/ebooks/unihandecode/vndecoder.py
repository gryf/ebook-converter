# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

__license__ = 'GPL 3'
__copyright__ = '2010, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'

'''
Decode unicode text to an ASCII representation of the text in Vietnamese.

'''

from ebook_converter.ebooks.unihandecode.unidecoder import Unidecoder
from ebook_converter.ebooks.unihandecode.vncodepoints import CODEPOINTS as HANCODES
from ebook_converter.ebooks.unihandecode.unicodepoints import CODEPOINTS


class Vndecoder(Unidecoder):

    codepoints = {}

    def __init__(self):
        self.codepoints = CODEPOINTS
        self.codepoints.update(HANCODES)
