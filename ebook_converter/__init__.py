import math
import os
import pkg_resources
import re
import sys
import time
import mimetypes

from functools import partial

try:
    os.getcwd()
except EnvironmentError:
    os.chdir(os.path.expanduser('~'))

from ebook_converter.constants_old import (iswindows, isosx, islinux, isfrozen,
        isbsd, preferred_encoding, __appname__, __version__, __author__,
        win32event, win32api, winerror, fcntl,
        filesystem_encoding, plugins, config_dir)
from ebook_converter.startup import winutil, winutilerror
from ebook_converter.utils.icu import safe_chr

if False:
    # Prevent pyflakes from complaining
    winutil, winutilerror, __appname__, islinux, __version__
    fcntl, win32event, isfrozen, __author__
    winerror, win32api, isbsd, config_dir


def init_mimetypes():
    mimetypes.init([pkg_resources.resource_filename('ebook_converter',
                                                    'data/mime.types')])


def guess_extension(*args, **kwargs):
    ext = mimetypes.guess_extension(*args, **kwargs)
    if not ext and args and args[0] == 'application/x-palmreader':
        ext = '.pdb'
    return ext


def to_unicode(raw, encoding='utf-8', errors='strict'):
    if isinstance(raw, str):
        return raw
    return raw.decode(encoding, errors)


def unicode_path(path, abs=False):
    if isinstance(path, bytes):
        path = path.decode(filesystem_encoding)
    if abs:
        path = os.path.abspath(path)
    return path


def confirm_config_name(name):
    return name + '_again'


_filename_sanitize_unicode = frozenset(('\\', '|', '?', '*', '<',        # no2to3
    '"', ':', '>', '+', '/') + tuple(map(chr, range(32))))  # no2to3


def sanitize_file_name(name, substitute='_'):
    '''
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    macOS and Linux. Also removes leading and trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    '''
    if isinstance(name, bytes):
        name = name.decode(filesystem_encoding, 'replace')
    if isinstance(substitute, bytes):
        substitute = substitute.decode(filesystem_encoding, 'replace')
    chars = (substitute if c in _filename_sanitize_unicode else c for c in name)
    one = ''.join(chars)
    one = re.sub(r'\s', ' ', one).strip()
    bname, ext = os.path.splitext(one)
    one = re.sub(r'^\.+$', '_', bname)
    one = one.replace('..', substitute)
    one += ext
    # Windows doesn't like path components that end with a period or space
    if one and one[-1] in ('.', ' '):
        one = one[:-1]+'_'
    # Names starting with a period are hidden on Unix
    if one.startswith('.'):
        one = '_' + one[1:]
    return one


def prints(*args, **kwargs):
    """
    Print unicode arguments safely by encoding them to preferred_encoding
    Has the same signature as the print function from Python 3, except for the
    additional keyword argument safe_encode, which if set to True will cause the
    function to use repr when encoding fails.

    Returns the number of bytes written.
    """
    file = kwargs.get('file', sys.stdout)
    file = getattr(file, 'buffer', file)
    enc = 'utf-8' if os.getenv('CALIBRE_WORKER') else preferred_encoding
    sep = kwargs.get('sep', ' ')
    if not isinstance(sep, bytes):
        sep = sep.encode(enc)
    end = kwargs.get('end', '\n')
    if not isinstance(end, bytes):
        end = end.encode(enc)
    safe_encode = kwargs.get('safe_encode', False)
    count = 0
    for i, arg in enumerate(args):
        if isinstance(arg, str):
            if iswindows:
                from ebook_converter.utils.terminal import Detect
                cs = Detect(file)
                if cs.is_console:
                    cs.write_unicode_text(arg)
                    count += len(arg)
                    if i != len(args)-1:
                        file.write(sep)
                        count += len(sep)
                    continue
            try:
                arg = arg.encode(enc)
            except UnicodeEncodeError:
                try:
                    arg = arg.encode('utf-8')
                except:
                    if not safe_encode:
                        raise
                    arg = repr(arg)
        if not isinstance(arg, bytes):
            if isinstance(arg, str):
                try:
                    arg = arg.encode(enc)
                except UnicodeEncodeError:
                    try:
                        arg = arg.encode('utf-8')
                    except:
                        if not safe_encode:
                            raise
                        arg = repr(arg)

        try:
            file.write(arg)
            count += len(arg)
        except:
            from polyglot import reprlib
            arg = reprlib.repr(arg)
            file.write(arg)
            count += len(arg)
        if i != len(args)-1:
            file.write(sep)
            count += len(sep)
    file.write(end)
    count += len(end)
    return count


def setup_cli_handlers(logger, level):
    import logging
    if os.getenv('CALIBRE_WORKER') and logger.handlers:
        return
    logger.setLevel(level)
    if level == logging.WARNING:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        handler.setLevel(logging.WARNING)
    elif level == logging.INFO:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter())
        handler.setLevel(logging.INFO)
    elif level == logging.DEBUG:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(filename)s:%(lineno)s: %(message)s'))

    logger.addHandler(handler)


def load_library(name, cdll):
    if iswindows:
        return cdll.LoadLibrary(name)
    if isosx:
        name += '.dylib'
        if hasattr(sys, 'frameworks_dir'):
            return cdll.LoadLibrary(os.path.join(getattr(sys, 'frameworks_dir'), name))
        return cdll.LoadLibrary(name)
    return cdll.LoadLibrary(name+'.so')


def extract(path, dir):
    extractor = None
    # First use the file header to identify its type
    with open(path, 'rb') as f:
        id_ = f.read(3)
    if id_ == b'Rar':
        from ebook_converter.utils.unrar import extract as rarextract
        extractor = rarextract
    elif id_.startswith(b'PK'):
        from ebook_converter.libunzip import extract as zipextract
        extractor = zipextract
    if extractor is None:
        # Fallback to file extension
        ext = os.path.splitext(path)[1][1:].lower()
        if ext in ['zip', 'cbz', 'epub', 'oebzip']:
            from ebook_converter.libunzip import extract as zipextract
            extractor = zipextract
        elif ext in ['cbr', 'rar']:
            from ebook_converter.utils.unrar import extract as rarextract
            extractor = rarextract
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)


def fit_image(width, height, pwidth, pheight):
    '''
    Fit image in box of width pwidth and height pheight.
    @param width: Width of image
    @param height: Height of image
    @param pwidth: Width of box
    @param pheight: Height of box
    @return: scaled, new_width, new_height. scaled is True iff new_width and/or new_height is different from width or height.
    '''
    scaled = height > pheight or width > pwidth
    if height > pheight:
        corrf = pheight / float(height)
        width, height = math.floor(corrf*width), pheight
    if width > pwidth:
        corrf = pwidth / float(width)
        width, height = pwidth, math.floor(corrf*height)
    if height > pheight:
        corrf = pheight / float(height)
        width, height = math.floor(corrf*width), pheight

    return scaled, int(width), int(height)


class CurrentDir(object):

    def __init__(self, path):
        self.path = path
        self.cwd = None

    def __enter__(self, *args):
        self.cwd = os.getcwd()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args):
        try:
            os.chdir(self.cwd)
        except EnvironmentError:
            # The previous CWD no longer exists
            pass


relpath = os.path.relpath


def walk(dir):
    ''' A nice interface to os.walk '''
    for record in os.walk(dir):
        for f in record[-1]:
            yield os.path.join(record[0], f)


def strftime(fmt, t=None):
    ''' A version of strftime that returns unicode strings and tries to handle dates
    before 1900 '''
    if not fmt:
        return ''
    if t is None:
        t = time.localtime()
    if hasattr(t, 'timetuple'):
        t = t.timetuple()
    early_year = t[0] < 1900
    if early_year:
        replacement = 1900 if t[0]%4 == 0 else 1901
        fmt = fmt.replace('%Y', '_early year hack##')
        t = list(t)
        orig_year = t[0]
        t[0] = replacement
        t = time.struct_time(t)
    ans = None
    if iswindows:
        if isinstance(fmt, bytes):
            fmt = fmt.decode('mbcs', 'replace')
        fmt = fmt.replace('%e', '%#d')
        ans = plugins['winutil'][0].strftime(fmt, t)
    else:
        ans = time.strftime(fmt, t)
        if isinstance(ans, bytes):
            ans = ans.decode(preferred_encoding, 'replace')
    if early_year:
        ans = ans.replace('_early year hack##', str(orig_year))
    return ans


def my_unichr(num):
    try:
        return safe_chr(num)
    except (ValueError, OverflowError):
        return '?'


def entity_to_unicode(match, exceptions=[], encoding='cp1252',
        result_exceptions={}):
    '''
    :param match: A match object such that '&'+match.group(1)';' is the entity.

    :param exceptions: A list of entities to not convert (Each entry is the name of the entity, for e.g. 'apos' or '#1234'

    :param encoding: The encoding to use to decode numeric entities between 128 and 256.
    If None, the Unicode UCS encoding is used. A common encoding is cp1252.

    :param result_exceptions: A mapping of characters to entities. If the result
    is in result_exceptions, result_exception[result] is returned instead.
    Convenient way to specify exception for things like < or > that can be
    specified by various actual entities.
    '''
    def check(ch):
        return result_exceptions.get(ch, ch)

    ent = match.group(1)
    if ent in exceptions:
        return '&'+ent+';'
    if ent in {'apos', 'squot'}:  # squot is generated by some broken CMS software
        return check("'")
    if ent == 'hellips':
        ent = 'hellip'
    if ent.startswith('#'):
        try:
            if ent[1] in ('x', 'X'):
                num = int(ent[2:], 16)
            else:
                num = int(ent[1:])
        except:
            return '&'+ent+';'
        if encoding is None or num > 255:
            return check(my_unichr(num))
        try:
            return check(bytes(bytearray((num,))).decode(encoding))
        except UnicodeDecodeError:
            return check(my_unichr(num))
    from ebook_converter.ebooks.html_entities import html5_entities
    try:
        return check(html5_entities[ent])
    except KeyError:
        pass
    from polyglot.html_entities import name2codepoint
    try:
        return check(my_unichr(name2codepoint[ent]))
    except KeyError:
        return '&'+ent+';'


_ent_pat = re.compile(r'&(\S+?);')
xml_entity_to_unicode = partial(entity_to_unicode,
                                result_exceptions={'"': '&quot;',
                                                   "'": '&apos;',
                                                   '<': '&lt;',
                                                   '>': '&gt;',
                                                   '&': '&amp;'})


def replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(entity_to_unicode, encoding=encoding), raw)


def xml_replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(xml_entity_to_unicode, encoding=encoding), raw)


def prepare_string_for_xml(raw, attribute=False):
    raw = _ent_pat.sub(entity_to_unicode, raw)
    raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attribute:
        raw = raw.replace('"', '&quot;').replace("'", '&apos;')
    return raw


def force_unicode(obj, enc=preferred_encoding):
    if isinstance(obj, bytes):
        try:
            obj = obj.decode(enc)
        except Exception:
            try:
                obj = obj.decode(filesystem_encoding if enc ==
                                 preferred_encoding else preferred_encoding)
            except Exception:
                try:
                    obj = obj.decode('utf-8')
                except Exception:
                    obj = repr(obj)
                    if isinstance(obj, bytes):
                        obj = obj.decode('utf-8')
    return obj


def as_unicode(obj, enc=preferred_encoding):
    if not isinstance(obj, bytes):
        try:
            obj = str(obj)
        except Exception:
            obj = repr(obj)
    return force_unicode(obj, enc=enc)


def url_slash_cleaner(url):
    '''
    Removes redundant /'s from url's.
    '''
    return re.sub(r'(?<!:)/{2,}', '/', url)


def human_readable(size, sep=' '):
    """ Convert a size in bytes into a human readable form """
    divisor, suffix = 1, "B"
    for i, candidate in enumerate(('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB')):
        if size < (1 << ((i + 1) * 10)):
            divisor, suffix = (1 << (i * 10)), candidate
            break
    size = str(float(size)/divisor)
    if size.find(".") > -1:
        size = size[:size.find(".")+2]
    if size.endswith('.0'):
        size = size[:-2]
    return size + sep + suffix
