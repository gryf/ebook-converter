import glob
import os

from ebook_converter.ebooks.mobi import MobiError
from ebook_converter.ebooks.mobi.reader.mobi6 import MobiReader
from ebook_converter.ebooks.mobi.reader.headers import MetadataHeader
from ebook_converter import logging
from ebook_converter.ebooks import DRMError
from ebook_converter.ebooks.mobi.reader.mobi8 import Mobi8Reader
from ebook_converter.ebooks.conversion.plumber import Plumber, create_oebbook
from ebook_converter.customize.ui import plugin_for_input_format
from ebook_converter.customize.ui import plugin_for_output_format
from ebook_converter.utils import directory
from ebook_converter.utils.ipc.simple_worker import fork_job


LOG = logging.default_log


class BadFormat(ValueError):
    pass


def do_explode(path, dest):
    with open(path, 'rb') as stream:
        mr = MobiReader(stream, LOG, None, None)

        with directory.CurrentDir(dest):
            mr = Mobi8Reader(mr, LOG)
            opf = os.path.abspath(mr())
            try:
                os.remove('debug-raw.html')
            except Exception:
                pass

    return opf


def explode(path, dest, question=lambda x: True):
    with open(path, 'rb') as stream:
        raw = stream.read(3)
        stream.seek(0)
        if raw == b'TPZ':
            raise BadFormat('This is not a MOBI file. It is a Topaz file.')

        try:
            header = MetadataHeader(stream, LOG)
        except MobiError:
            raise BadFormat('This is not a MOBI file.')

        if header.encryption_type != 0:
            raise DRMError('This file is locked with DRM. It cannot be '
                           'tweaked.')

        kf8_type = header.kf8_type

        if kf8_type is None:
            raise BadFormat('This MOBI file does not contain a KF8 format '
                            'book. KF8 is the new format from Amazon. calibre '
                            'can only tweak MOBI files that contain KF8 '
                            'books. Older MOBI files without KF8 are not '
                            'tweakable.')

        if kf8_type == 'joint':
            if not question('This MOBI file contains both KF8 and older Mobi6 '
                            'data. Tweaking it will remove the Mobi6 data, '
                            'which means the file will not be usable on older '
                            'Kindles. Are you sure?'):
                return None

    return fork_job('ebook_converter.ebooks.mobi.tweak', 'do_explode',
                    args=(path, dest), no_output=True)['result']


def set_cover(oeb):
    if 'cover' not in oeb.guide or oeb.metadata['cover']:
        return
    cover = oeb.guide['cover']
    if cover.href in oeb.manifest.hrefs:
        item = oeb.manifest.hrefs[cover.href]
        oeb.metadata.clear('cover')
        oeb.metadata.add('cover', item.id)


def do_rebuild(opf, dest_path):
    plumber = Plumber(opf, dest_path, LOG)
    plumber.setup_options()
    inp = plugin_for_input_format('azw3')
    outp = plugin_for_output_format('azw3')

    plumber.opts.mobi_passthrough = True
    oeb = create_oebbook(LOG, opf, plumber.opts)
    set_cover(oeb)
    outp.convert(oeb, dest_path, inp, plumber.opts, LOG)


def rebuild(src_dir, dest_path):
    opf = glob.glob(os.path.join(src_dir, '*.opf'))
    if not opf:
        raise ValueError('No OPF file found in %s' % src_dir)
    opf = opf[0]
    # For debugging, uncomment the following two lines
    # def fork_job(a, b, args=None, no_output=True):
    #     do_rebuild(*args)
    fork_job('ebook_converter.ebooks.mobi.tweak', 'do_rebuild',
             args=(opf, dest_path), no_output=True)
