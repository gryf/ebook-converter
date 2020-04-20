from collections import namedtuple
import json
import pkg_resources

from ebook_converter.utils.localization import canonicalize_lang


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

DictionaryLocale = namedtuple('DictionaryLocale', 'langcode countrycode')

ccodes, ccodemap, country_names = None, None, None


def get_codes():
    global ccodes, ccodemap, country_names
    if ccodes is None:
        src = pkg_resources.resource_filename('ebook_converter',
                                              'data/iso_3166-1.json')
        with open(src, 'rb') as f:
            db = json.load(f)
        codes = set()
        three_map = {}
        name_map = {}
        for x in db['3166-1']:
            two = x.get('alpha_2')
            if two:
                two = str(two)
            codes.add(two)
            name_map[two] = x.get('name')
            if name_map[two]:
                name_map[two] = str(name_map[two])
            three = x.get('alpha_3')
            if three:
                three_map[str(three)] = two
        data = {'names': name_map,
                'codes': frozenset(codes),
                'three_map': three_map}

        ccodes, ccodemap, country_names = (data['codes'], data['three_map'],
                                           data['names'])
    return ccodes, ccodemap


def parse_lang_code(raw):
    raw = raw or ''
    parts = raw.replace('_', '-').split('-')
    lc = canonicalize_lang(parts[0])
    if lc is None:
        raise ValueError('Invalid language code: %r' % raw)
    cc = None
    if len(parts) > 1:
        ccodes, ccodemap = get_codes()[:2]
        q = parts[1].upper()
        if q in ccodes:
            cc = q
        else:
            cc = ccodemap.get(q, None)
    return DictionaryLocale(lc, cc)
