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
import os


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
