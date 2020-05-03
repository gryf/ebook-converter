"""
PEP 302 based plugin loading mechanism, works around the bug in zipimport in
python 2.x that prevents importing from zip files in locations whose paths
have non ASCII characters
"""
import os, zipfile, posixpath, importlib, threading, re, imp, sys
from collections import OrderedDict
from functools import partial

from ebook_converter import as_unicode
from ebook_converter.customize import (Plugin, numeric_version, platform,
        InvalidPlugin, PluginNotFound)
from ebook_converter.polyglot.builtins import reload


__license__ = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


def get_resources(zfp, name_or_list_of_names):
    '''
    Load resources from the plugin zip file

    :param name_or_list_of_names: List of paths to resources in the zip file using / as
                separator, or a single path

    :return: A dictionary of the form ``{name : file_contents}``. Any names
                that were not found in the zip file will not be present in the
                dictionary. If a single path is passed in the return value will
                be just the bytes of the resource or None if it wasn't found.
    '''
    names = name_or_list_of_names
    if isinstance(names, (str, bytes)):
        names = [names]
    ans = {}
    with zipfile.ZipFile(zfp) as zf:
        for name in names:
            try:
                ans[name] = zf.read(name)
            except:
                import traceback
                traceback.print_exc()
    if len(names) == 1:
        ans = ans.pop(names[0], None)

    return ans


def get_icons(zfp, name_or_list_of_names):
    '''
    Load icons from the plugin zip file

    :param name_or_list_of_names: List of paths to resources in the zip file using / as
                separator, or a single path

    :return: A dictionary of the form ``{name : QIcon}``. Any names
                that were not found in the zip file will be null QIcons.
                If a single path is passed in the return value will
                be A QIcon.
    '''
    from PyQt5.Qt import QIcon, QPixmap
    names = name_or_list_of_names
    ans = get_resources(zfp, names)
    if isinstance(names, (str, bytes)):
        names = [names]
    if ans is None:
        ans = {}
    if isinstance(ans, (str, bytes)):
        ans = dict([(names[0], ans)])

    ians = {}
    for name in names:
        p = QPixmap()
        raw = ans.get(name, None)
        if raw:
            p.loadFromData(raw)
        ians[name] = QIcon(p)
    if len(names) == 1:
        ians = ians.pop(names[0])
    return ians


_translations_cache = {}


def load_translations(namespace, zfp):
    null = object()
    trans = _translations_cache.get(zfp, null)
    if trans is None:
        return
    if trans is null:
        from ebook_converter.utils.localization import get_lang
        lang = get_lang()
        if not lang or lang == 'en':  # performance optimization
            _translations_cache[zfp] = None
            return
        with zipfile.ZipFile(zfp) as zf:
            try:
                mo = zf.read('translations/%s.mo' % lang)
            except KeyError:
                mo = None  # No translations for this language present
        if mo is None:
            _translations_cache[zfp] = None
            return
        from gettext import GNUTranslations
        from io import BytesIO
        trans = _translations_cache[zfp] = GNUTranslations(BytesIO(mo))

    namespace['_'] = getattr(trans, 'gettext')
    namespace['ngettext'] = getattr(trans, 'ngettext')
