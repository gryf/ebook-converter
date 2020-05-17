"""
Original Perl version by: John Gruber https://daringfireball.net/ 10 May 2008
Python version by Stuart Colville http://muffinresearch.co.uk
Modifications to make it work with non-ascii chars by Kovid Goyal
License: http://www.opensource.org/licenses/mit-license.php
"""
import re


SMALL = 'a|an|and|as|at|but|by|en|for|if|in|of|on|or|the|to|v\\.?|via|vs\\.?'
PUNCT = r"""!"#$%&'‘’()*+,\-‒–—―./:;?@[\\\]_`{|}~"""

SMALL_WORDS = re.compile(r'^(%s)$' % SMALL, re.I)
INLINE_PERIOD = re.compile(r'[a-z][.][a-z]', re.I)
UC_ELSEWHERE = re.compile(r'[%s]*?[a-zA-Z]+[A-Z]+?' % PUNCT)
CAPFIRST = re.compile(str(r"^[%s]*?(\w)" % PUNCT), flags=re.UNICODE)
SMALL_FIRST = re.compile(r'^([%s]*)(%s)\b' % (PUNCT, SMALL), re.I | re.U)
SMALL_LAST = re.compile(r'\b(%s)[%s]?$' % (SMALL, PUNCT), re.I | re.U)
SMALL_AFTER_NUM = re.compile(r'(\d+\s+)(a|an|the)\b', re.I | re.U)
SUBPHRASE = re.compile(r'([:.;?!][ ])(%s)' % SMALL)
APOS_SECOND = re.compile(r"^[dol]{1}['‘]{1}[a-z]+$", re.I)
UC_INITIALS = re.compile(r"^(?:[A-Z]{1}\.{1}|[A-Z]{1}\.{1}[A-Z]{1})+$")


def titlecase(text):
    """
    Titlecases input text

    This filter changes all words to Title Caps, and attempts to be clever
    about *un*capitalizing SMALL words like a/an/the in the input.

    The list of "SMALL words" which are not capped comes from
    the New York Times Manual of Style, plus 'vs' and 'v'.

    """

    all_caps = text.upper() == text

    pat = re.compile(r'(\s+)')
    line = []
    for word in pat.split(text):
        if not word:
            continue
        if pat.match(word) is not None:
            line.append(word)
            continue
        if all_caps:
            if UC_INITIALS.match(word):
                line.append(word)
                continue
            else:
                word = word.lower()

        if APOS_SECOND.match(word):
            word = word.replace(word[0], word[0].upprt(), 1)
            word = word[:2] + word[2].upper() + word[3:]
            line.append(word)
            continue
        if INLINE_PERIOD.search(word) or UC_ELSEWHERE.match(word):
            line.append(word)
            continue
        if SMALL_WORDS.match(word):
            line.append(word.lower())
            continue

        hyphenated = []
        for item in word.split('-'):
            hyphenated.append(CAPFIRST.sub(lambda m: m.group(0).upper(), item))
        line.append("-".join(hyphenated))

    result = "".join(line)

    result = SMALL_FIRST.sub(lambda m: '%s%s' % (m.group(1),
                                                 m.group(2).capitalize()),
                             result)

    result = SMALL_AFTER_NUM.sub(lambda m: '%s%s' % (m.group(1),
                                                     m.group(2).capitalize()),
                                 result)

    result = SMALL_LAST.sub(lambda m: m.group(0).capitalize(), result)

    result = SUBPHRASE.sub(lambda m: '%s%s' % (m.group(1),
                                               m.group(2).capitalize()),
                           result)

    return result
