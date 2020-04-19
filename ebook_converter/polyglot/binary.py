from base64 import standard_b64decode, standard_b64encode
from binascii import hexlify, unhexlify

from ebook_converter.polyglot.builtins import unicode_type


def as_base64_bytes(x, enc='utf-8'):
    if isinstance(x, unicode_type):
        x = x.encode(enc)
    return standard_b64encode(x)


def as_base64_unicode(x, enc='utf-8'):
    if isinstance(x, unicode_type):
        x = x.encode(enc)
    return standard_b64encode(x).decode('ascii')


def from_base64_unicode(x, enc='utf-8'):
    if isinstance(x, unicode_type):
        x = x.encode('ascii')
    return standard_b64decode(x).decode(enc)


def from_base64_bytes(x):
    if isinstance(x, unicode_type):
        x = x.encode('ascii')
    return standard_b64decode(x)


def as_hex_bytes(x, enc='utf-8'):
    if isinstance(x, unicode_type):
        x = x.encode(enc)
    return hexlify(x)


def as_hex_unicode(x, enc='utf-8'):
    if isinstance(x, unicode_type):
        x = x.encode(enc)
    return hexlify(x).decode('ascii')


def from_hex_unicode(x, enc='utf-8'):
    if isinstance(x, unicode_type):
        x = x.encode('ascii')
    return unhexlify(x).decode(enc)


def from_hex_bytes(x):
    if isinstance(x, unicode_type):
        x = x.encode('ascii')
    return unhexlify(x)
