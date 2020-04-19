"""
Decode unicode text to an ASCII representation of the text in Vietnamese.
"""

from ebook_converter.ebooks.unihandecode import unidecoder
from ebook_converter.ebooks.unihandecode import vncodepoints
from ebook_converter.ebooks.unihandecode import unicodepoints


__license__ = 'GPL 3'
__copyright__ = '2010, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'


class Vndecoder(unidecoder.Unidecoder):

    codepoints = {}

    def __init__(self):
        self.codepoints = unicodepoints.CODEPOINTS
        self.codepoints.update(vncodepoints.CODEPOINTS)
