"""
Make strings safe for use as ASCII filenames, while trying to preserve as much
meaning as possible.
"""
import errno
import os
import re
import shutil
from math import ceil

from ebook_converter import constants_old
from ebook_converter import force_unicode
from ebook_converter.constants_old import (filesystem_encoding,
                                           preferred_encoding)
from ebook_converter.utils.localization import get_udc


def sanitize_file_name(name, substitute='_'):
    """
    Sanitize the filename `name`. All invalid characters are replaced by
    `substitute`. The set of invalid characters is the union of the invalid
    characters in Windows, macOS and Linux. Also removes leading and trailing
    whitespace.

    **WARNING:** This function also replaces path separators, so only pass
    file names and not full paths to it.
    """

    if isinstance(name, bytes):
        name = name.decode(constants_old.filesystem_encoding, 'replace')
    if isinstance(substitute, bytes):
        substitute = substitute.decode(constants_old.filesystem_encoding,
                                       'replace')
    chars = (substitute
             if c in set(('\\', '|', '?', '*', '<', '"', ':', '>', '+', '/') +
                         tuple(map(chr, range(32)))) else c for c in name)
    one = ''.join(chars)
    one = re.sub(r'\s', ' ', one).strip()
    bname, ext = os.path.splitext(one)
    one = re.sub(r'^\.+$', '_', bname)
    one = one.replace('..', substitute)
    one += ext
    # Windows doesn't like path components that end with a period or space
    if one and one[-1] in ('.', ' '):
        one = one[:-1]+'_'
    # Names starting with a period are hidden on Unix
    if one.startswith('.'):
        one = '_' + one[1:]
    return one


def ascii_text(orig):
    udc = get_udc()
    try:
        ascii = udc.decode(orig)
    except Exception:
        if isinstance(orig, str):
            orig = orig.encode('ascii', 'replace')
        ascii = orig.decode(preferred_encoding, 'replace')
    if isinstance(ascii, bytes):
        ascii = ascii.decode('ascii', 'replace')
    return ascii


def ascii_filename(orig, substitute='_'):
    if isinstance(substitute, bytes):
        substitute = substitute.decode(filesystem_encoding)
    orig = ascii_text(orig).replace('?', '_')
    ans = ''.join(x if ord(x) >= 32 else substitute for x in orig)
    return sanitize_file_name(ans, substitute=substitute)


def shorten_component(s, by_what):
    l = len(s)
    if l < by_what:
        return s
    l = (l - by_what)//2
    if l <= 0:
        return s
    return s[:l] + s[-l:]


def limit_component(x, limit=254):
    # windows and macs use utf-16 codepoints for length, linux uses arbitrary
    # binary data, but we will assume utf-8
    filename_encoding_for_length = 'utf-8'

    def encoded_length():
        q = x if isinstance(x, bytes) else x.encode(filename_encoding_for_length)
        return len(q)

    while encoded_length() > limit:
        delta = encoded_length() - limit
        x = shorten_component(x, max(2, delta // 2))

    return x


def shorten_components_to(length, components, more_to_take=0, last_has_extension=True):
    components = [limit_component(cx) for cx in components]
    filepath = os.sep.join(components)
    extra = len(filepath) - (length - more_to_take)
    if extra < 1:
        return components
    deltas = []
    for x in components:
        pct = len(x)/float(len(filepath))
        deltas.append(int(ceil(pct*extra)))
    ans = []

    for i, x in enumerate(components):
        delta = deltas[i]
        if delta > len(x):
            r = x[0] if x is components[-1] else ''
        else:
            if last_has_extension and x is components[-1]:
                b, e = os.path.splitext(x)
                if e == '.':
                    e = ''
                r = shorten_component(b, delta)+e
                if r.startswith('.'):
                    r = x[0]+r
            else:
                r = shorten_component(x, delta)
            r = r.strip()
            if not r:
                r = x.strip()[0] if x.strip() else 'x'
        ans.append(r)
    if len(os.sep.join(ans)) > length:
        return shorten_components_to(length, components, more_to_take+2)
    return ans


def find_executable_in_path(name, path=None):
    if path is None:
        path = os.environ.get('PATH', '')
    exts = ('',)
    path = path.split(os.pathsep)
    for x in path:
        for ext in exts:
            q = os.path.abspath(os.path.join(x, name)) + ext
            if os.access(q, os.X_OK):
                return q


def is_case_sensitive(path):
    '''
    Return True if the filesystem is case sensitive.

    path must be the path to an existing directory. You must have permission
    to create and delete files in this directory. The results of this test
    apply to the filesystem containing the directory in path.
    '''
    is_case_sensitive = False
    name1, name2 = ('calibre_test_case_sensitivity.txt',
                    'calibre_TesT_CaSe_sensitiVitY.Txt')
    f1, f2 = os.path.join(path, name1), os.path.join(path, name2)
    if os.path.exists(f1):
        os.remove(f1)
    open(f1, 'w').close()
    is_case_sensitive = not os.path.exists(f2)
    os.remove(f1)
    return is_case_sensitive


def case_preserving_open_file(path, mode='wb', mkdir_mode=0o777):
    '''
    Open the file pointed to by path with the specified mode. If any
    directories in path do not exist, they are created. Returns the
    opened file object and the path to the opened file object. This path is
    guaranteed to have the same case as the on disk path. For case insensitive
    filesystems, the returned path may be different from the passed in path.
    The returned path is always unicode and always an absolute path.

    If mode is None, then this function assumes that path points to a directory
    and return the path to the directory as the file object.

    mkdir_mode specifies the mode with which any missing directories in path
    are created.
    '''
    if isinstance(path, bytes):
        path = path.decode(filesystem_encoding)

    path = os.path.abspath(path)

    sep = force_unicode(os.sep, 'ascii')

    if path.endswith(sep):
        path = path[:-1]
    if not path:
        raise ValueError('Path must not point to root')

    components = path.split(sep)
    if not components:
        raise ValueError('Invalid path: %r'%path)

    cpath = sep

    bdir = path if mode is None else os.path.dirname(path)
    if not os.path.exists(bdir):
        os.makedirs(bdir, mkdir_mode)

    # Walk all the directories in path, putting the on disk case version of
    # the directory into cpath
    dirs = components[1:] if mode is None else components[1:-1]
    for comp in dirs:
        cdir = os.path.join(cpath, comp)
        cl = comp.lower()
        try:
            candidates = [c for c in os.listdir(cpath) if c.lower() == cl]
        except:
            # Dont have permission to do the listdir, assume the case is
            # correct as we have no way to check it.
            pass
        else:
            if len(candidates) == 1:
                cdir = os.path.join(cpath, candidates[0])
            # else: We are on a case sensitive file system so cdir must already
            # be correct
        cpath = cdir

    if mode is None:
        ans = fpath = cpath
    else:
        fname = components[-1]
        ans = open(os.path.join(cpath, fname), mode)
        # Ensure file and all its metadata is written to disk so that subsequent
        # listdir() has file name in it. I don't know if this is actually
        # necessary, but given the diversity of platforms, best to be safe.
        ans.flush()
        os.fsync(ans.fileno())

        cl = fname.lower()
        try:
            candidates = [c for c in os.listdir(cpath) if c.lower() == cl]
        except EnvironmentError:
            # The containing directory, somehow disappeared?
            candidates = []
        if len(candidates) == 1:
            fpath = os.path.join(cpath, candidates[0])
        else:
            # We are on a case sensitive filesystem
            fpath = os.path.join(cpath, fname)
    return ans, fpath


def samefile(src, dst):
    '''
    Check if two paths point to the same actual file on the filesystem. Handles
    symlinks, case insensitivity, mapped drives, etc.

    Returns True iff both paths exist and point to the same file on disk.

    Note: On windows will return True if the two string are identical (up to
    case) even if the file does not exist. This is because I have no way of
    knowing how reliable the GetFileInformationByHandle method is.
    '''
    if hasattr(os.path, 'samefile'):
        # Unix
        try:
            return os.path.samefile(src, dst)
        except EnvironmentError:
            return False

    # All other platforms: check for same pathname.
    samestring = (os.path.normcase(os.path.abspath(src)) ==
            os.path.normcase(os.path.abspath(dst)))
    return samestring


def hardlink_file(src, dest):
    os.link(src, dest)


def nlinks_file(path):
    ' Return number of hardlinks to the file '
    return os.stat(path).st_nlink


def atomic_rename(oldpath, newpath):
    '''Replace the file newpath with the file oldpath. Can fail if the files
    are on different volumes. If succeeds, guaranteed to be atomic. newpath may
    or may not exist. If it exists, it is replaced. '''
    os.rename(oldpath, newpath)


def remove_dir_if_empty(path, ignore_metadata_caches=False):
    ''' Remove a directory if it is empty or contains only the folder metadata
    caches from different OSes. To delete the folder if it contains only
    metadata caches, set ignore_metadata_caches to True.'''
    try:
        os.rmdir(path)
    except OSError as e:
        if e.errno == errno.ENOTEMPTY or len(os.listdir(path)) > 0:
            # Some linux systems appear to raise an EPERM instead of an
            # ENOTEMPTY, see https://bugs.launchpad.net/bugs/1240797
            if ignore_metadata_caches:
                try:
                    found = False
                    for x in os.listdir(path):
                        if x.lower() in {'.ds_store', 'thumbs.db'}:
                            found = True
                            x = os.path.join(path, x)
                            if os.path.isdir(x):
                                import shutil
                                shutil.rmtree(x)
                            else:
                                os.remove(x)
                except Exception:  # We could get an error, if, for example, windows has locked Thumbs.db
                    found = False
                if found:
                    remove_dir_if_empty(path)
            return
        raise


expanduser = os.path.expanduser


def format_permissions(st_mode):
    import stat
    for func, letter in (x.split(':') for x in 'REG:- DIR:d BLK:b CHR:c FIFO:p LNK:l SOCK:s'.split()):
        if getattr(stat, 'S_IS' + func)(st_mode):
            break
    else:
        letter = '?'
    rwx = ('---', '--x', '-w-', '-wx', 'r--', 'r-x', 'rw-', 'rwx')
    ans = [letter] + list(rwx[(st_mode >> 6) & 7]) + list(rwx[(st_mode >> 3) & 7]) + list(rwx[(st_mode & 7)])
    if st_mode & stat.S_ISUID:
        ans[3] = 's' if (st_mode & stat.S_IXUSR) else 'S'
    if st_mode & stat.S_ISGID:
        ans[6] = 's' if (st_mode & stat.S_IXGRP) else 'l'
    if st_mode & stat.S_ISVTX:
        ans[9] = 't' if (st_mode & stat.S_IXUSR) else 'T'
    return ''.join(ans)


def copyfile(src, dest):
    shutil.copyfile(src, dest)
    try:
        shutil.copystat(src, dest)
    except Exception:
        pass


def get_hardlink_function(src, dest):
    return os.link


def copyfile_using_links(path, dest, dest_is_dir=True, filecopyfunc=copyfile):
    path, dest = os.path.abspath(path), os.path.abspath(dest)
    if dest_is_dir:
        dest = os.path.join(dest, os.path.basename(path))
    hardlink = get_hardlink_function(path, dest)
    try:
        hardlink(path, dest)
    except Exception:
        filecopyfunc(path, dest)


def copytree_using_links(path, dest, dest_is_parent=True, filecopyfunc=copyfile):
    path, dest = os.path.abspath(path), os.path.abspath(dest)
    if dest_is_parent:
        dest = os.path.join(dest, os.path.basename(path))
    hardlink = get_hardlink_function(path, dest)
    try:
        os.makedirs(dest)
    except EnvironmentError as e:
        if e.errno != errno.EEXIST:
            raise
    for dirpath, dirnames, filenames in os.walk(path):
        base = os.path.relpath(dirpath, path)
        dest_base = os.path.join(dest, base)
        for dname in dirnames:
            try:
                os.mkdir(os.path.join(dest_base, dname))
            except EnvironmentError as e:
                if e.errno != errno.EEXIST:
                    raise
        for fname in filenames:
            src, df = os.path.join(dirpath, fname), os.path.join(dest_base, fname)
            try:
                hardlink(src, df)
            except Exception:
                filecopyfunc(src, df)
