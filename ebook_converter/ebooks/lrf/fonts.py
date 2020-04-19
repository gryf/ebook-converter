"""
Default fonts used in the PRS500
"""
from PIL import ImageFont

from ebook_converter.utils.fonts.scanner import font_scanner


__license__ = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

LIBERATION_FONT_MAP = {'Swis721 BT Roman': 'Liberation Sans Regular',
                       'Dutch801 Rm BT Roman': 'Liberation Serif Regular',
                       'Courier10 BT Roman': 'Liberation Mono Regular'}
_LIB_CACHE = {}
FONT_FILE_MAP = {}


def get_font(name, size, encoding='unic'):
    """
    Get an ImageFont object by name.
    @param size: Font height in pixels. To convert from pts:
                 sz in pixels = (dpi/72) * size in pts
    @param encoding: Font encoding to use. E.g. 'unic', 'symbol', 'ADOB',
                     'ADBE', 'aprm'
    """
    if name in LIBERATION_FONT_MAP:
        if not _LIB_CACHE:
            for key in font_scanner.cache['fonts']:
                record = font_scanner.cache['fonts'][key]
                _LIB_CACHE[record['family_name'] + ' ' +
                           record['subfamily_name']] = record['path']

        fpath = _LIB_CACHE.get(LIBERATION_FONT_MAP[name])
        if not fpath:
            raise ValueError('There is no liberation font existing in the '
                             'system. Please install them before converter '
                             'use.')
        return ImageFont.truetype(fpath, size, encoding=encoding)
    elif name in FONT_FILE_MAP:
        return ImageFont.truetype(FONT_FILE_MAP[name], size, encoding=encoding)
