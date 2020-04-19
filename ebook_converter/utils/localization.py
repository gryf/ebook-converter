__license__ = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, io, sys
import json
from gettext import GNUTranslations, NullTranslations
import pkg_resources

from ebook_converter.polyglot.builtins import is_py3, iteritems, unicode_type

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


def set_translators():
    t = NullTranslations()
    set_translators.lang = t.info().get('language')
    t.install(names=('ngettext',))


set_translators.lang = None


_iso639 = None
_extra_lang_codes = {
        'pt_BR' : _('Brazilian Portuguese'),
        'en_GB' : _('English (UK)'),
        'zh_CN' : _('Simplified Chinese'),
        'zh_TW' : _('Traditional Chinese'),
        'en'    : _('English'),
        'en_US' : _('English (United States)'),
        'en_AR' : _('English (Argentina)'),
        'en_AU' : _('English (Australia)'),
        'en_JP' : _('English (Japan)'),
        'en_DE' : _('English (Germany)'),
        'en_BG' : _('English (Bulgaria)'),
        'en_EG' : _('English (Egypt)'),
        'en_NZ' : _('English (New Zealand)'),
        'en_CA' : _('English (Canada)'),
        'en_GR' : _('English (Greece)'),
        'en_IN' : _('English (India)'),
        'en_NP' : _('English (Nepal)'),
        'en_TH' : _('English (Thailand)'),
        'en_TR' : _('English (Turkey)'),
        'en_CY' : _('English (Cyprus)'),
        'en_CZ' : _('English (Czech Republic)'),
        'en_PH' : _('English (Philippines)'),
        'en_PK' : _('English (Pakistan)'),
        'en_PL' : _('English (Poland)'),
        'en_HR' : _('English (Croatia)'),
        'en_HU' : _('English (Hungary)'),
        'en_ID' : _('English (Indonesia)'),
        'en_IL' : _('English (Israel)'),
        'en_RU' : _('English (Russia)'),
        'en_SG' : _('English (Singapore)'),
        'en_YE' : _('English (Yemen)'),
        'en_IE' : _('English (Ireland)'),
        'en_CN' : _('English (China)'),
        'en_TW' : _('English (Taiwan)'),
        'en_ZA' : _('English (South Africa)'),
        'es_PY' : _('Spanish (Paraguay)'),
        'es_UY' : _('Spanish (Uruguay)'),
        'es_AR' : _('Spanish (Argentina)'),
        'es_CR' : _('Spanish (Costa Rica)'),
        'es_MX' : _('Spanish (Mexico)'),
        'es_CU' : _('Spanish (Cuba)'),
        'es_CL' : _('Spanish (Chile)'),
        'es_EC' : _('Spanish (Ecuador)'),
        'es_HN' : _('Spanish (Honduras)'),
        'es_VE' : _('Spanish (Venezuela)'),
        'es_BO' : _('Spanish (Bolivia)'),
        'es_NI' : _('Spanish (Nicaragua)'),
        'es_CO' : _('Spanish (Colombia)'),
        'de_AT' : _('German (AT)'),
        'fr_BE' : _('French (BE)'),
        'nl'    : _('Dutch (NL)'),
        'nl_BE' : _('Dutch (BE)'),
        'und'   : _('Unknown')
        }

if False:
    # Extra strings needed for Qt

    # NOTE: Ante Meridian (i.e. like 10:00 AM)
    _('AM')
    # NOTE: Post Meridian (i.e. like 10:00 PM)
    _('PM')
    # NOTE: Ante Meridian (i.e. like 10:00 am)
    _('am')
    # NOTE: Post Meridian (i.e. like 10:00 pm)
    _('pm')
    _('&Copy')
    _('Select All')
    _('Copy Link')
    _('&Select All')
    _('Copy &Link Location')
    _('&Undo')
    _('&Redo')
    _('Cu&t')
    _('&Paste')
    _('Paste and Match Style')
    _('Directions')
    _('Left to Right')
    _('Right to Left')
    _('Fonts')
    _('&Step up')
    _('Step &down')
    _('Close without Saving')
    _('Close Tab')

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


def get_language(lang):
    translate = _
    lang = _lcase_map.get(lang, lang)
    if lang in _extra_lang_codes:
        # The translator was not active when _extra_lang_codes was defined, so
        # re-translate
        return translate(_extra_lang_codes[lang])
    attr = 'gettext' if sys.version_info.major > 2 else 'ugettext'
    return get_iso_language(getattr(_lang_trans, attr, translate), lang)


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
    if not isinstance(raw, unicode_type):
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
        _lang_map = {k:translate(v) for k, v in iteritems(iso639['by_3'])}
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
    for k, v in iteritems(iso639['by_3']):
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
