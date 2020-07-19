"""
Created on 4 Jun 2010

@author: charles
"""
from ebook_converter.constants_old import preferred_encoding


def object_to_unicode(obj, enc=preferred_encoding):

    def dec(x):
        return x.decode(enc, 'replace')

    if isinstance(obj, bytes):
        return dec(obj)
    if isinstance(obj, (list, tuple)):
        return [dec(x) if isinstance(x, bytes) else object_to_unicode(x)
                for x in obj]
    if isinstance(obj, dict):
        ans = {}
        for k, v in obj.items():
            k = object_to_unicode(k)
            v = object_to_unicode(v)
            ans[k] = v
        return ans
    return obj


def encode_is_multiple(fm):
    if fm.get('is_multiple', None):
        # migrate is_multiple back to a character
        fm['is_multiple2'] = fm.get('is_multiple', {})
        dt = fm.get('datatype', None)
        if dt == 'composite':
            fm['is_multiple'] = ','
        else:
            fm['is_multiple'] = '|'
    else:
        fm['is_multiple'] = None
        fm['is_multiple2'] = {}


def decode_is_multiple(fm):
    im = fm.get('is_multiple2',  None)
    if im:
        fm['is_multiple'] = im
        del fm['is_multiple2']
    else:
        # Must migrate the is_multiple from char to dict
        im = fm.get('is_multiple',  {})
        if im:
            dt = fm.get('datatype', None)
            if dt == 'composite':
                im = {'cache_to_list': ',', 'ui_to_list': ',',
                      'list_to_ui': ', '}
            elif fm.get('display', {}).get('is_names', False):
                im = {'cache_to_list': '|', 'ui_to_list': '&',
                      'list_to_ui': ', '}
            else:
                im = {'cache_to_list': '|', 'ui_to_list': ',',
                      'list_to_ui': ', '}
        elif im is None:
            im = {}
        fm['is_multiple'] = im
