"""
Misc converting functions from polyglot module.
Most of the have something to do with converting between string and binary
"""
import base64
import binascii
import urllib


def as_base64_unicode(x, enc='utf-8'):
    if isinstance(x, str):
        x = x.encode(enc)
    return base64.standard_b64encode(x).decode('ascii')


def from_base64_bytes(x):
    if isinstance(x, str):
        x = x.encode('ascii')
    return base64.standard_b64decode(x)


def as_hex_bytes(x, enc='utf-8'):
    if isinstance(x, str):
        x = x.encode(enc)
    return binascii.hexlify(x)


def from_hex_bytes(x):
    if isinstance(x, str):
        x = x.encode('ascii')
    return binascii.unhexlify(x)


def as_bytes(x, encoding='utf-8'):
    if isinstance(x, str):
        return x.encode(encoding)
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return bytes(x)
    if isinstance(x, memoryview):
        return x.tobytes()
    return str(x).encode(encoding)


def unquote(x, encoding='utf-8', errors='replace'):
    # TODO(gryf): this works like that: if x is a binary, convert it to
    # string using encoding and make unquote. After that make it binary again.
    # If x is string, just pass it to the unquote.
    # This approach is mostly used within lxml etree strings, which suppose to
    # be binary because of its inner representation. I'm wondering, if
    # xml.etree could be used instead - to be checked.
    binary = isinstance(x, bytes)
    if binary:
        x = x.decode(encoding, errors)
    ans = urllib.parse.unquote(x, encoding, errors)
    if binary:
        ans = ans.encode(encoding, errors)
    return ans
