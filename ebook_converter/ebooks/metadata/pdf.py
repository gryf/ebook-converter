"""
Read meta information from PDF files
"""
import functools
import os
import re
import shutil
import subprocess

from ebook_converter.ptempfile import TemporaryDirectory
from ebook_converter.ebooks.metadata import (
    MetaInformation, string_to_authors, check_isbn, check_doi)


def read_info(outputdir, get_cover):
    ''' Read info dict and cover from a pdf file named src.pdf in outputdir.
    Note that this function changes the cwd to outputdir and is therefore not
    thread safe. Run it using fork_job. This is necessary as there is no safe
    way to pass unicode paths via command line arguments. This also ensures
    that if poppler crashes, no stale file handles are left for the original
    file, only for src.pdf.'''
    pdfinfo = 'pdfinfo'
    pdftoppm = 'pdftoppm'
    source_file = os.path.join(outputdir, 'src.pdf')
    cover_file = os.path.join(outputdir, 'cover')
    ans = {}

    try:
        raw = subprocess.check_output([pdfinfo, '-enc', 'UTF-8', '-isodates',
                                       source_file])
    except subprocess.CalledProcessError as e:
        print(f'pdfinfo errored out with return code: {e.returncode}')
        return None
    try:
        info_raw = raw.decode('utf-8')
    except UnicodeDecodeError:
        print('pdfinfo returned no UTF-8 data')
        return None

    for line in info_raw.splitlines():
        if ':' not in line:
            continue
        field, val = line.partition(':')[::2]
        val = val.strip()
        if field and val:
            ans[field] = val.strip()

    # Now read XMP metadata
    # Versions of poppler before 0.47.0 used to print out both the Info dict
    # and XMP metadata packet together. However, since that changed in
    # https://cgit.freedesktop.org/poppler/poppler/commit/?id=c91483aceb1b640771f572cb3df9ad707e5cad0d
    # we can no longer rely on it.
    try:
        raw = subprocess.check_output([pdfinfo, '-meta', source_file]).strip()
    except subprocess.CalledProcessError as e:
        print('pdfinfo failed to read XML metadata with return code: '
              f'{e.returncode}')
    else:
        parts = re.split(br'^Metadata:', raw, 1, flags=re.MULTILINE)
        if len(parts) > 1:
            # old poppler < 0.47.0
            raw = parts[1].strip()
        if raw:
            ans['xmp_metadata'] = raw

    if get_cover:
        try:
            subprocess.check_call([pdftoppm, '-singlefile', '-jpeg',
                                   '-cropbox', source_file, cover_file])
        except subprocess.CalledProcessError as e:
            print(f'pdftoppm errored out with return code: {e.returncode}')

    return ans


def page_images(pdfpath, outputdir='.', first=1, last=1, image_format='jpeg',
                prefix='page-images'):
    pdftoppm = 'pdftoppm'
    outputdir = os.path.abspath(outputdir)
    args = {}
    try:
        subprocess.check_call([
            pdftoppm, '-cropbox', '-' + image_format, '-f', str(first),
            '-l', str(last), pdfpath, os.path.join(outputdir, prefix)
        ], **args)
    except subprocess.CalledProcessError as e:
        raise ValueError('Failed to render PDF, pdftoppm errorcode: %s' %
                         e.returncode)


def is_pdf_encrypted(path_to_pdf):
    pdfinfo = 'pdfinfo'
    raw = subprocess.check_output([pdfinfo, path_to_pdf])
    q = re.search(br'^Encrypted:\s*(\S+)', raw, flags=re.MULTILINE)
    if q is not None:
        return q.group(1) == b'yes'
    return False


def get_metadata(stream, cover=True):
    with TemporaryDirectory('_pdf_metadata_read') as pdfpath:
        stream.seek(0)
        with open(os.path.join(pdfpath, 'src.pdf'), 'wb') as f:
            shutil.copyfileobj(stream, f)
        info = read_info(pdfpath, bool(cover))
        if info is None:
            raise ValueError('Could not read info dict from PDF')
        covpath = os.path.join(pdfpath, 'cover.jpg')
        cdata = None
        if cover and os.path.exists(covpath):
            with open(covpath, 'rb') as f:
                cdata = f.read()

    title = info.get('Title', None) or 'Unknown'
    au = info.get('Author', None)
    if au is None:
        au = ['Unknown']
    else:
        au = string_to_authors(au)
    mi = MetaInformation(title, au)

    creator = info.get('Creator', None)
    if creator:
        mi.book_producer = creator

    keywords = info.get('Keywords', None)
    mi.tags = []
    if keywords:
        mi.tags = [x.strip() for x in keywords.split(',')]
        isbn = [check_isbn(x) for x in mi.tags if check_isbn(x)]
        if isbn:
            mi.isbn = isbn = isbn[0]
        mi.tags = [x for x in mi.tags if check_isbn(x) != isbn]

    subject = info.get('Subject', None)
    if subject:
        mi.tags.insert(0, subject)

    if 'xmp_metadata' in info:
        from ebook_converter.ebooks.metadata.xmp import consolidate_metadata
        mi = consolidate_metadata(mi, info)

    # Look for recognizable identifiers in the info dict, if they were not
    # found in the XMP metadata
    for scheme, check_func in {'doi': check_doi, 'isbn': check_isbn}.items():
        if scheme not in mi.get_identifiers():
            for k, v in info.items():
                if k != 'xmp_metadata':
                    val = check_func(v)
                    if val:
                        mi.set_identifier(scheme, val)
                        break

    if cdata:
        mi.cover_data = ('jpeg', cdata)
    return mi


get_quick_metadata = functools.partial(get_metadata, cover=False)


def set_metadata(stream, mi):
    return None
