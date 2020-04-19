"""
Decode unicode text to an ASCII representation of the text in Korean.
Based on unidecoder.
"""
from ebook_converter.ebooks.unihandecode.unidecoder import Unidecoder
from ebook_converter.ebooks.unihandecode.krcodepoints import CODEPOINTS as HANCODES
from ebook_converter.ebooks.unihandecode.unicodepoints import CODEPOINTS


__license__ = 'GPL 3'
__copyright__ = '2010, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'


class Krdecoder(Unidecoder):

    codepoints = {}

    def __init__(self):
        self.codepoints = CODEPOINTS
        self.codepoints.update(HANCODES)
