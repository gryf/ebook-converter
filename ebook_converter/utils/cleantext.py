import re
import html.entities

from ebook_converter.constants import plugins, preferred_encoding


def ascii_pat(for_binary=False):
    attr = 'binary' if for_binary else 'text'
    ans = getattr(ascii_pat, attr, None)
    if ans is None:
        chars = set(range(32)) - {9, 10, 13}
        chars.add(127)
        pat = '|'.join(map(chr, chars))
        if for_binary:
            pat = pat.encode('ascii')
        ans = re.compile(pat)
        setattr(ascii_pat, attr, ans)
    return ans


def clean_ascii_chars(txt, charlist=None):
    r'''
    Remove ASCII control chars.
    This is all control chars except \t, \n and \r
    '''
    is_binary = isinstance(txt, bytes)
    empty = b'' if is_binary else ''
    if not txt:
        return empty

    if charlist is None:
        pat = ascii_pat(is_binary)
    else:
        pat = '|'.join(map(chr, charlist))
        if is_binary:
            pat = pat.encode('utf-8')
    return pat.sub(empty, txt)


def allowed(x):
    x = ord(x)
    return (x != 127 and (31 < x < 0xd7ff or x in (9, 10, 13))) or (0xe000 < x < 0xfffd) or (0x10000 < x < 0x10ffff)


def py_clean_xml_chars(unicode_string):
    return ''.join(filter(allowed, unicode_string))


clean_xml_chars = py_clean_xml_chars


def test_clean_xml_chars():
    raw = 'asd\x02a\U00010437x\ud801b\udffe\ud802'
    if native_clean_xml_chars(raw) != 'asda\U00010437xb':
        raise ValueError('Failed to XML clean: %r' % raw)


# Fredrik Lundh: http://effbot.org/zone/re-sub.htm#unescape-html
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text, rm=False, rchar=''):
    def fixup(m, rm=rm, rchar=rchar):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return chr(int(text[3:-1], 16))
                else:
                    return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = chr(html.entities
                                        .name2codepoint[text[1:-1]])
            except KeyError:
                pass
        if rm:
            return rchar  # replace by char
        return text  # leave as is
    return re.sub("&#?\\w+;", fixup, text)
