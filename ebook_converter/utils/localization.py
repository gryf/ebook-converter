import json
import pkg_resources


def get_lang():
    return 'en_US'


def is_rtl():
    return get_lang()[:2].lower() in {'he', 'ar'}


_lang_trans = None


lcdata = {'abday': ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'),
          'abmon': ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                    'Sep', 'Oct', 'Nov', 'Dec'),
          'd_fmt': '%m/%d/%Y',
          'd_t_fmt': '%a %d %b %Y %r %Z',
          'day': ('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday',
                  'Friday', 'Saturday'),
          'mon': ('January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November',
                  'December'),
          'noexpr': '^[nN].*',
          'radixchar': '.',
          't_fmt': '%r',
          't_fmt_ampm': '%I:%M:%S %p',
          'thousep': ',',
          'yesexpr': '^[yY].*'}


_iso639 = None


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


def langcode_to_name(lc, localize=True):
    iso639 = _load_iso639()
    try:
        return iso639['by_3'][lc]
    except Exception:
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
