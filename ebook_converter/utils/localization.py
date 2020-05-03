__license__ = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
import io
import sys
import json
import pkg_resources

_available_translations = None


def sanitize_lang(lang):
    if lang:
        match = re.match('[a-z]{2,3}(_[A-Z]{2}){0,1}', lang)
        if match:
            lang = match.group()
    if lang == 'zh':
        lang = 'zh_CN'
    if not lang:
        lang = 'en'
    return lang


def get_lang():
    return 'en_US'


def is_rtl():
    return get_lang()[:2].lower() in {'he', 'ar'}


_lang_trans = None


lcdata = {
    'abday': ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'),
    'abmon': ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'),
    'd_fmt': '%m/%d/%Y',
    'd_t_fmt': '%a %d %b %Y %r %Z',
    'day': ('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'),
    'mon': ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'),
    'noexpr': '^[nN].*',
    'radixchar': '.',
    't_fmt': '%r',
    't_fmt_ampm': '%I:%M:%S %p',
    'thousep': ',',
    'yesexpr': '^[yY].*'
}


def load_po(path):
    from ebook_converter.translations.msgfmt import make
    buf = io.BytesIO()
    try:
        make(path, buf)
    except Exception:
        print(('Failed to compile translations file: %s, ignoring') % path)
        buf = None
    else:
        buf = io.BytesIO(buf.getvalue())
    return buf


_iso639 = None
_extra_lang_codes = {
        'pt_BR' : 'Brazilian Portuguese',
        'en_GB' : 'English (UK)',
        'zh_CN' : 'Simplified Chinese',
        'zh_TW' : 'Traditional Chinese',
        'en'    : 'English',
        'en_US' : 'English (United States)',
        'en_AR' : 'English (Argentina)',
        'en_AU' : 'English (Australia)',
        'en_JP' : 'English (Japan)',
        'en_DE' : 'English (Germany)',
        'en_BG' : 'English (Bulgaria)',
        'en_EG' : 'English (Egypt)',
        'en_NZ' : 'English (New Zealand)',
        'en_CA' : 'English (Canada)',
        'en_GR' : 'English (Greece)',
        'en_IN' : 'English (India)',
        'en_NP' : 'English (Nepal)',
        'en_TH' : 'English (Thailand)',
        'en_TR' : 'English (Turkey)',
        'en_CY' : 'English (Cyprus)',
        'en_CZ' : 'English (Czech Republic)',
        'en_PH' : 'English (Philippines)',
        'en_PK' : 'English (Pakistan)',
        'en_PL' : 'English (Poland)',
        'en_HR' : 'English (Croatia)',
        'en_HU' : 'English (Hungary)',
        'en_ID' : 'English (Indonesia)',
        'en_IL' : 'English (Israel)',
        'en_RU' : 'English (Russia)',
        'en_SG' : 'English (Singapore)',
        'en_YE' : 'English (Yemen)',
        'en_IE' : 'English (Ireland)',
        'en_CN' : 'English (China)',
        'en_TW' : 'English (Taiwan)',
        'en_ZA' : 'English (South Africa)',
        'es_PY' : 'Spanish (Paraguay)',
        'es_UY' : 'Spanish (Uruguay)',
        'es_AR' : 'Spanish (Argentina)',
        'es_CR' : 'Spanish (Costa Rica)',
        'es_MX' : 'Spanish (Mexico)',
        'es_CU' : 'Spanish (Cuba)',
        'es_CL' : 'Spanish (Chile)',
        'es_EC' : 'Spanish (Ecuador)',
        'es_HN' : 'Spanish (Honduras)',
        'es_VE' : 'Spanish (Venezuela)',
        'es_BO' : 'Spanish (Bolivia)',
        'es_NI' : 'Spanish (Nicaragua)',
        'es_CO' : 'Spanish (Colombia)',
        'de_AT' : 'German (AT)',
        'fr_BE' : 'French (BE)',
        'nl'    : 'Dutch (NL)',
        'nl_BE' : 'Dutch (BE)',
        'und'   : 'Unknown'
        }

if False:
    # Extra strings needed for Qt

    # NOTE: Ante Meridian (i.e. like 10:00 AM)
    'AM'
    # NOTE: Post Meridian (i.e. like 10:00 PM)
    'PM'
    # NOTE: Ante Meridian (i.e. like 10:00 am)
    'am'
    # NOTE: Post Meridian (i.e. like 10:00 pm)
    'pm'
    '&Copy'
    'Select All'
    'Copy Link'
    '&Select All'
    'Copy &Link Location'
    '&Undo'
    '&Redo'
    'Cu&t'
    '&Paste'
    'Paste and Match Style'
    'Directions'
    'Left to Right'
    'Right to Left'
    'Fonts'
    '&Step up'
    'Step &down'
    'Close without Saving'
    'Close Tab'

_lcase_map = {}
for k in _extra_lang_codes:
    _lcase_map[k.lower()] = k


def _load_iso639():
    global _iso639

    # NOTE(gryf): msgpacked data was originally added for speed purposes. In
    # my tests, I cannot see any speed gain either on python2 or python3. It
    # is even slower (around 4-8 times), than just using code below (which is
    # excerpt form Calibre transform code which is executed during Calibre
    # build).
    if _iso639 is None:
        src = pkg_resources.resource_filename('ebook_converter',
                                              'data/iso_639-3.json')

        with open(src, 'rb') as f:
            root = json.load(f)

        entries = root['639-3']
        by_2 = {}
        by_3 = {}
        m2to3 = {}
        m3to2 = {}
        nm = {}
        codes2, codes3 = set(), set()
        for x in entries:
            two = x.get('alpha_2')
            threeb = x.get('alpha_3')
            if threeb is None:
                continue
            name = x.get('inverted_name') or x.get('name')
            if not name or name[0] in '!~=/\'"':
                continue

            if two is not None:
                by_2[two] = name
                codes2.add(two)
                m2to3[two] = threeb
                m3to2[threeb] = two
            codes3.add(threeb)
            by_3[threeb] = name
            base_name = name.lower()
            nm[base_name] = threeb

        _iso639 = {'by_2': by_2,
                   'by_3': by_3,
                   'codes2': codes2,
                   'codes3': codes3,
                   '2to3': m2to3,
                   '3to2': m3to2,
                   'name_map': nm}

    return _iso639


def get_iso_language(lang_trans, lang):
    iso639 = _load_iso639()
    ans = lang
    lang = lang.split('_')[0].lower()
    if len(lang) == 2:
        ans = iso639['by_2'].get(lang, ans)
    elif len(lang) == 3:
        if lang in iso639['by_3']:
            ans = iso639['by_3'][lang]
    return lang_trans(ans)




def calibre_langcode_to_name(lc, localize=True):
    iso639 = _load_iso639()
    translate = _ if localize else lambda x: x
    try:
        return translate(iso639['by_3'][lc])
    except:
        pass
    return lc


def canonicalize_lang(raw):
    if not raw:
        return None
    if not isinstance(raw, str):
        raw = raw.decode('utf-8', 'ignore')
    raw = raw.lower().strip()
    if not raw:
        return None
    raw = raw.replace('_', '-').partition('-')[0].strip()
    if not raw:
        return None
    iso639 = _load_iso639()
    m2to3 = iso639['2to3']

    if len(raw) == 2:
        ans = m2to3.get(raw, None)
        if ans is not None:
            return ans
    elif len(raw) == 3:
        if raw in iso639['by_3']:
            return raw

    return iso639['name_map'].get(raw, None)


_lang_map = None


def lang_map():
    ' Return mapping of ISO 639 3 letter codes to localized language names '
    iso639 = _load_iso639()
    translate = _
    global _lang_map
    if _lang_map is None:
        _lang_map = {k:translate(v) for k, v in iso639['by_3'].items()}
    return _lang_map


def lang_map_for_ui():
    ans = getattr(lang_map_for_ui, 'ans', None)
    if ans is None:
        ans = lang_map().copy()
        for x in ('zxx', 'mis', 'mul'):
            ans.pop(x, None)
        lang_map_for_ui.ans = ans
    return ans


def langnames_to_langcodes(names):
    '''
    Given a list of localized language names return a mapping of the names to 3
    letter ISO 639 language codes. If a name is not recognized, it is mapped to
    None.
    '''
    iso639 = _load_iso639()
    translate = _
    ans = {}
    names = set(names)
    for k, v in iso639['by_3'].items():
        tv = translate(v)
        if tv in names:
            names.remove(tv)
            ans[tv] = k
        if not names:
            break
    for x in names:
        ans[x] = None

    return ans


def lang_as_iso639_1(name_or_code):
    code = canonicalize_lang(name_or_code)
    if code is not None:
        iso639 = _load_iso639()
        return iso639['3to2'].get(code, None)


_udc = None


def get_udc():
    global _udc
    if _udc is None:
        from ebook_converter.ebooks.unihandecode import Unihandecoder
        _udc = Unihandecoder(lang=get_lang())
    return _udc


def localize_user_manual_link(url):
    return url
