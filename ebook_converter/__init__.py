import os
import re

from functools import partial

from ebook_converter import constants_old
from ebook_converter.utils import entities


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


_ent_pat = re.compile(r'&(\S+?);')
xml_entity_to_unicode = partial(entities.entity_to_unicode,
                                result_exceptions={'"': '&quot;',
                                                   "'": '&apos;',
                                                   '<': '&lt;',
                                                   '>': '&gt;',
                                                   '&': '&amp;'})


def replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(entities.entity_to_unicode, encoding=encoding),
                        raw)


def xml_replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(xml_entity_to_unicode, encoding=encoding), raw)


def prepare_string_for_xml(raw, attribute=False):
    raw = _ent_pat.sub(entities.entity_to_unicode, raw)
    raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attribute:
        raw = raw.replace('"', '&quot;').replace("'", '&apos;')
    return raw
