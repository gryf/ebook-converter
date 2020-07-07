import urllib.parse


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
