from base64 import standard_b64decode, standard_b64encode
from binascii import hexlify, unhexlify


def as_base64_unicode(x, enc='utf-8'):
    if isinstance(x, str):
        x = x.encode(enc)
    return standard_b64encode(x).decode('ascii')


def from_base64_bytes(x):
    if isinstance(x, str):
        x = x.encode('ascii')
    return standard_b64decode(x)


def as_hex_bytes(x, enc='utf-8'):
    if isinstance(x, str):
        x = x.encode(enc)
    return hexlify(x)


def from_hex_bytes(x):
    if isinstance(x, str):
        x = x.encode('ascii')
    return unhexlify(x)
