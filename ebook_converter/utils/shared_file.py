"""
This module defines a share_open() function which is a replacement for
python's builtin open() function.

This replacement, opens 'shareable' files on all platforms. That is files that
can be read from and written to and deleted at the same time by multiple
processes. All file handles are non-inheritable, as in Python 3, but unlike,
Python 2. Non-inheritance is atomic.

Caveats on windows: On windows sharing is co-operative, i.e. it only works if
all processes involved open the file with share_open(). Also while you can
delete a file that is open, you cannot open a new file with the same filename
until all open file handles are closed. You also cannot delete the containing
directory until all file handles are closed. To get around this, rename the
file before deleting it.
"""
import os, sys

from ebook_converter.polyglot.builtins import reraise
from ebook_converter.constants import iswindows, plugins


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

# speedup, err = plugins['speedup']

# if not speedup:
    # raise RuntimeError('Failed to load the speedup plugin with error: %s' % err)

valid_modes = {'a', 'a+', 'a+b', 'ab', 'r', 'rb', 'r+', 'r+b', 'w', 'wb', 'w+', 'w+b'}


def validate_mode(mode):
    return mode in valid_modes


class FlagConstants(object):

    def __init__(self):
        for x in 'APPEND CREAT TRUNC EXCL RDWR RDONLY WRONLY'.split():
            x = 'O_' + x
            setattr(self, x, getattr(os, x))
        for x in 'RANDOM SEQUENTIAL TEXT BINARY'.split():
            x = 'O_' + x
            setattr(self, x, getattr(os, x, 0))


fc = FlagConstants()


def flags_from_mode(mode):
    if not validate_mode(mode):
        raise ValueError('The mode is invalid')
    m = mode[0]
    random = '+' in mode
    binary = 'b' in mode
    if m == 'a':
        flags = fc.O_APPEND | fc.O_CREAT
        if random:
            flags |= fc.O_RDWR | fc.O_RANDOM
        else:
            flags |= fc.O_WRONLY | fc.O_SEQUENTIAL
    elif m == 'r':
        if random:
            flags = fc.O_RDWR | fc.O_RANDOM
        else:
            flags = fc.O_RDONLY | fc.O_SEQUENTIAL
    elif m == 'w':
        if random:
            flags = fc.O_RDWR | fc.O_RANDOM
        else:
            flags = fc.O_WRONLY | fc.O_SEQUENTIAL
        flags |= fc.O_TRUNC | fc.O_CREAT
    flags |= (fc.O_BINARY if binary else fc.O_TEXT)
    return flags


share_open = open


def find_tests():
    import unittest
    from ebook_converter.ptempfile import TemporaryDirectory

    class SharedFileTest(unittest.TestCase):

        def test_shared_file(self):
            eq = self.assertEqual

            with TemporaryDirectory() as tdir:
                fname = os.path.join(tdir, 'test.txt')
                with share_open(fname, 'wb') as f:
                    f.write(b'a' * 20 * 1024)
                    eq(fname, f.name)
                f = share_open(fname, 'rb')
                eq(f.read(1), b'a')
                if iswindows:
                    os.rename(fname, fname+'.moved')
                    os.remove(fname+'.moved')
                else:
                    os.remove(fname)
                eq(f.read(1), b'a')
                f2 = share_open(fname, 'w+b')
                f2.write(b'b' * 10 * 1024)
                f2.seek(0)
                eq(f.read(10000), b'a'*10000)
                eq(f2.read(100), b'b' * 100)
                f3 = share_open(fname, 'rb')
                eq(f3.read(100), b'b' * 100)

    return unittest.defaultTestLoader.loadTestsFromTestCase(SharedFileTest)
