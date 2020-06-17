import glob
import mimetypes
import os
import re

from ebook_converter.constants_old import numeric_version
from ebook_converter.customize import FileTypePlugin
from ebook_converter.customize import InterfaceActionBase
from ebook_converter.customize import MetadataReaderPlugin
from ebook_converter.customize import MetadataWriterPlugin
from ebook_converter.ebooks.html.to_zip import HTML2ZIP
from ebook_converter.ebooks.metadata.archive import ArchiveExtract
from ebook_converter.ebooks.metadata.archive import KPFExtract
from ebook_converter.ebooks.metadata.archive import get_comic_metadata


plugins = []

# To archive plugins {{{


class PML2PMLZ(FileTypePlugin):
    name = 'PML to PMLZ'
    author = 'John Schember'
    description = ('Create a PMLZ archive containing the PML file '
                   'and all images in the directory pmlname_img or images. '
                   'This plugin is run every time you add '
                   'a PML file to the library.')
    version = numeric_version
    file_types = {'pml'}
    supported_platforms = ['osx', 'linux']
    on_import = True

    def run(self, pmlfile):
        import zipfile

        of = self.temporary_file('_plugin_pml2pmlz.pmlz')
        pmlz = zipfile.ZipFile(of.name, 'w')
        pmlz.write(pmlfile, os.path.basename(pmlfile), zipfile.ZIP_DEFLATED)

        pml_img = os.path.splitext(pmlfile)[0] + '_img'
        i_img = os.path.join(os.path.dirname(pmlfile), 'images')
        img_dir = pml_img if os.path.isdir(pml_img) else i_img if \
            os.path.isdir(i_img) else ''
        if img_dir:
            for image in glob.glob(os.path.join(img_dir, '*.png')):
                pmlz.write(image, os.path.join('images',
                                               (os.path.basename(image))))
        pmlz.close()

        return of.name


class TXT2TXTZ(FileTypePlugin):
    name = 'TXT to TXTZ'
    author = 'John Schember'
    description = ('Create a TXTZ archive when a TXT file is imported '
                   'containing Markdown or Textile references to images. The '
                   'referenced images as well as the TXT file are added to '
                   'the archive.')
    version = numeric_version
    file_types = {'txt', 'text'}
    supported_platforms = ['osx', 'linux']
    on_import = True

    def _get_image_references(self, txt, base_dir):
        from ebook_converter.ebooks.oeb.base import OEB_IMAGES

        images = []

        # Textile
        for m in re.finditer(r'(?mu)(?:[\[{])?\!(?:\. )?(?P<path>[^\s(!]+)\s?(?:\(([^\)]+)\))?\!(?::(\S+))?(?:[\]}]|(?=\s|$))', txt):
            path = m.group('path')
            if path and not os.path.isabs(path) and mimetypes.guess_type(path)[0] in OEB_IMAGES and os.path.exists(os.path.join(base_dir, path)):
                images.append(path)

        # Markdown inline
        for m in re.finditer(r'(?mu)\!\[([^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*)\]\s*\((?P<path>[^\)]*)\)', txt):  # noqa
            path = m.group('path')
            if path and not os.path.isabs(path) and mimetypes.guess_type(path)[0] in OEB_IMAGES and os.path.exists(os.path.join(base_dir, path)):
                images.append(path)

        # Markdown reference
        refs = {}
        for m in re.finditer(r'(?mu)^(\ ?\ ?\ ?)\[(?P<id>[^\]]*)\]:\s*(?P<path>[^\s]*)$', txt):
            if m.group('id') and m.group('path'):
                refs[m.group('id')] = m.group('path')
        for m in re.finditer(r'(?mu)\!\[([^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*)\]\s*\[(?P<id>[^\]]*)\]', txt):  # noqa
            path = refs.get(m.group('id'), None)
            if path and not os.path.isabs(path) and mimetypes.guess_type(path)[0] in OEB_IMAGES and os.path.exists(os.path.join(base_dir, path)):
                images.append(path)

        # Remove duplicates
        return list(set(images))

    def run(self, path_to_ebook):
        from ebook_converter.ebooks.metadata.opf2 import metadata_to_opf

        with open(path_to_ebook, 'rb') as ebf:
            txt = ebf.read().decode('utf-8', 'replace')
        base_dir = os.path.dirname(path_to_ebook)
        images = self._get_image_references(txt, base_dir)

        if images:
            # Create TXTZ and put file plus images inside of it.
            import zipfile
            of = self.temporary_file('_plugin_txt2txtz.txtz')
            txtz = zipfile.ZipFile(of.name, 'w')
            # Add selected TXT file to archive.
            txtz.write(path_to_ebook, os.path.basename(path_to_ebook), zipfile.ZIP_DEFLATED)
            # metadata.opf
            if os.path.exists(os.path.join(base_dir, 'metadata.opf')):
                txtz.write(os.path.join(base_dir, 'metadata.opf'), 'metadata.opf', zipfile.ZIP_DEFLATED)
            else:
                from ebook_converter.ebooks.metadata.txt import get_metadata
                with open(path_to_ebook, 'rb') as ebf:
                    mi = get_metadata(ebf)
                opf = metadata_to_opf(mi)
                txtz.writestr('metadata.opf', opf, zipfile.ZIP_DEFLATED)
            # images
            for image in images:
                txtz.write(os.path.join(base_dir, image), image)
            txtz.close()

            return of.name
        else:
            # No images so just import the TXT file.
            return path_to_ebook


plugins += [HTML2ZIP, PML2PMLZ, TXT2TXTZ, ArchiveExtract, KPFExtract]
# }}}

# Metadata reader plugins {{{


class ComicMetadataReader(MetadataReaderPlugin):

    name = 'Read comic metadata'
    file_types = {'cbr', 'cbz'}
    description = 'Extract cover from comic files'

    def customization_help(self, gui=False):
        return 'Read series number from volume or issue number. Default is volume, set this to issue to use issue number instead.'

    def get_metadata(self, stream, ftype):
        if hasattr(stream, 'seek') and hasattr(stream, 'tell'):
            pos = stream.tell()
            id_ = stream.read(3)
            stream.seek(pos)
            if id_ == b'Rar':
                ftype = 'cbr'
            elif id_.startswith(b'PK'):
                ftype = 'cbz'
        if ftype == 'cbr':
            from ebook_converter.utils.unrar import extract_cover_image
        else:
            from ebook_converter.libunzip import extract_cover_image
        from ebook_converter.ebooks.metadata import MetaInformation
        ret = extract_cover_image(stream)
        mi = MetaInformation(None, None)
        stream.seek(0)
        if ftype in {'cbr', 'cbz'}:
            series_index = self.site_customization
            if series_index not in {'volume', 'issue'}:
                series_index = 'volume'
            try:
                mi.smart_update(get_comic_metadata(stream, ftype, series_index=series_index))
            except:
                pass
        if ret is not None:
            path, data = ret
            ext = os.path.splitext(path)[1][1:]
            mi.cover_data = (ext.lower(), data)
        return mi


class CHMMetadataReader(MetadataReaderPlugin):

    name        = 'Read CHM metadata'
    file_types  = {'chm'}
    description = 'Read metadata from CHM files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.chm.metadata import get_metadata
        return get_metadata(stream)


class EPUBMetadataReader(MetadataReaderPlugin):

    name        = 'Read EPUB metadata'
    file_types  = {'epub'}
    description = 'Read metadata from EPUB files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.epub import get_metadata, get_quick_metadata
        if self.quick:
            return get_quick_metadata(stream)
        return get_metadata(stream)


class FB2MetadataReader(MetadataReaderPlugin):

    name        = 'Read FB2 metadata'
    file_types  = {'fb2', 'fbz'}
    description = 'Read metadata from FB2 files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.fb2 import get_metadata
        return get_metadata(stream)


class HTMLMetadataReader(MetadataReaderPlugin):

    name        = 'Read HTML metadata'
    file_types  = {'html'}
    description = 'Read metadata from HTML files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.html import get_metadata
        return get_metadata(stream)


class HTMLZMetadataReader(MetadataReaderPlugin):

    name        = 'Read HTMLZ metadata'
    file_types  = {'htmlz'}
    description = 'Read metadata from HTMLZ files'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.extz import get_metadata
        return get_metadata(stream)


class IMPMetadataReader(MetadataReaderPlugin):

    name        = 'Read IMP metadata'
    file_types  = {'imp'}
    description = 'Read metadata from IMP files'
    author      = 'Ashish Kulkarni'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.imp import get_metadata
        return get_metadata(stream)


class LITMetadataReader(MetadataReaderPlugin):

    name        = 'Read LIT metadata'
    file_types  = {'lit'}
    description = 'Read metadata from LIT files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.lit import get_metadata
        return get_metadata(stream)


class LRFMetadataReader(MetadataReaderPlugin):

    name        = 'Read LRF metadata'
    file_types  = {'lrf'}
    description = 'Read metadata from LRF files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.lrf.meta import get_metadata
        return get_metadata(stream)


class LRXMetadataReader(MetadataReaderPlugin):

    name        = 'Read LRX metadata'
    file_types  = {'lrx'}
    description = 'Read metadata from LRX files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.lrx import get_metadata
        return get_metadata(stream)


class MOBIMetadataReader(MetadataReaderPlugin):

    name        = 'Read MOBI metadata'
    file_types  = {'mobi', 'prc', 'azw', 'azw3', 'azw4', 'pobi'}
    description = 'Read metadata from MOBI files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.mobi import get_metadata
        return get_metadata(stream)


class ODTMetadataReader(MetadataReaderPlugin):

    name        = 'Read ODT metadata'
    file_types  = {'odt'}
    description = 'Read metadata from ODT files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.odt import get_metadata
        return get_metadata(stream)


class DocXMetadataReader(MetadataReaderPlugin):

    name        = 'Read DOCX metadata'
    file_types  = {'docx'}
    description = 'Read metadata from DOCX files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.docx import get_metadata
        return get_metadata(stream)


class OPFMetadataReader(MetadataReaderPlugin):

    name        = 'Read OPF metadata'
    file_types  = {'opf'}
    description = 'Read metadata from OPF files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.opf import get_metadata
        return get_metadata(stream)[0]


class PDBMetadataReader(MetadataReaderPlugin):

    name        = 'Read PDB metadata'
    file_types  = {'pdb', 'updb'}
    description = 'Read metadata from PDB files'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.pdb import get_metadata
        return get_metadata(stream)


class PDFMetadataReader(MetadataReaderPlugin):

    name        = 'Read PDF metadata'
    file_types  = {'pdf'}
    description = 'Read metadata from PDF files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.pdf import get_metadata, get_quick_metadata
        if self.quick:
            return get_quick_metadata(stream)
        return get_metadata(stream)


class PMLMetadataReader(MetadataReaderPlugin):

    name        = 'Read PML metadata'
    file_types  = {'pml', 'pmlz'}
    description = 'Read metadata from PML files'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.pml import get_metadata
        return get_metadata(stream)


class RARMetadataReader(MetadataReaderPlugin):

    name = 'Read RAR metadata'
    file_types = {'rar'}
    description = 'Read metadata from e-books in RAR archives'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.rar import get_metadata
        return get_metadata(stream)


class RBMetadataReader(MetadataReaderPlugin):

    name        = 'Read RB metadata'
    file_types  = {'rb'}
    description = 'Read metadata from RB files'
    author      = 'Ashish Kulkarni'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.rb import get_metadata
        return get_metadata(stream)


class RTFMetadataReader(MetadataReaderPlugin):

    name        = 'Read RTF metadata'
    file_types  = {'rtf'}
    description = 'Read metadata from RTF files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.rtf import get_metadata
        return get_metadata(stream)


class SNBMetadataReader(MetadataReaderPlugin):

    name        = 'Read SNB metadata'
    file_types  = {'snb'}
    description = 'Read metadata from SNB files'
    author      = 'Li Fanxi'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.snb import get_metadata
        return get_metadata(stream)


class TOPAZMetadataReader(MetadataReaderPlugin):

    name        = 'Read Topaz metadata'
    file_types  = {'tpz', 'azw1'}
    description = 'Read metadata from MOBI files'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.topaz import get_metadata
        return get_metadata(stream)


class TXTMetadataReader(MetadataReaderPlugin):

    name        = 'Read TXT metadata'
    file_types  = {'txt'}
    description = 'Read metadata from TXT files'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.txt import get_metadata
        return get_metadata(stream)


class TXTZMetadataReader(MetadataReaderPlugin):

    name        = 'Read TXTZ metadata'
    file_types  = {'txtz'}
    description = 'Read metadata from TXTZ files'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.extz import get_metadata
        return get_metadata(stream)


class ZipMetadataReader(MetadataReaderPlugin):

    name = 'Read ZIP metadata'
    file_types = {'zip', 'oebzip'}
    description = 'Read metadata from e-books in ZIP archives'

    def get_metadata(self, stream, ftype):
        from ebook_converter.ebooks.metadata.zip import get_metadata
        return get_metadata(stream)


plugins += [x for x in list(locals().values()) if isinstance(x, type) and
                                        x.__name__.endswith('MetadataReader')]

# }}}

# Metadata writer plugins {{{


class EPUBMetadataWriter(MetadataWriterPlugin):

    name = 'Set EPUB metadata'
    file_types = {'epub'}
    description = 'Set metadata in EPUB files'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.epub import set_metadata
        q = self.site_customization or ''
        set_metadata(stream, mi, apply_null=self.apply_null, force_identifiers=self.force_identifiers, add_missing_cover='disable-add-missing-cover' != q)

    def customization_help(self, gui=False):
        h = 'disable-add-missing-cover'
        if gui:
            h = '<i>' + h + '</i>'
        return ('Enter {0} below to have the EPUB metadata writer plugin not '
                'add cover images to EPUB files that have no existing cover '
                'image.'.format(h))


class FB2MetadataWriter(MetadataWriterPlugin):

    name = 'Set FB2 metadata'
    file_types = {'fb2', 'fbz'}
    description = 'Set metadata in FB2 files'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.fb2 import set_metadata
        set_metadata(stream, mi, apply_null=self.apply_null)


class HTMLZMetadataWriter(MetadataWriterPlugin):

    name        = 'Set HTMLZ metadata'
    file_types  = {'htmlz'}
    description = 'Set metadata from HTMLZ files'
    author      = 'John Schember'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.extz import set_metadata
        set_metadata(stream, mi)


class LRFMetadataWriter(MetadataWriterPlugin):

    name = 'Set LRF metadata'
    file_types = {'lrf'}
    description = 'Set metadata in LRF files'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.lrf.meta import set_metadata
        set_metadata(stream, mi)


class MOBIMetadataWriter(MetadataWriterPlugin):

    name        = 'Set MOBI metadata'
    file_types  = {'mobi', 'prc', 'azw', 'azw3', 'azw4'}
    description = 'Set metadata in MOBI files'
    author      = 'Marshall T. Vandegrift'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.mobi import set_metadata
        set_metadata(stream, mi)


class PDBMetadataWriter(MetadataWriterPlugin):

    name        = 'Set PDB metadata'
    file_types  = {'pdb'}
    description = 'Set metadata from PDB files'
    author      = 'John Schember'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.pdb import set_metadata
        set_metadata(stream, mi)


class PDFMetadataWriter(MetadataWriterPlugin):

    name        = 'Set PDF metadata'
    file_types  = {'pdf'}
    description = 'Set metadata in PDF files'
    author      = 'Kovid Goyal'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.pdf import set_metadata
        set_metadata(stream, mi)


class RTFMetadataWriter(MetadataWriterPlugin):

    name = 'Set RTF metadata'
    file_types = {'rtf'}
    description = 'Set metadata in RTF files'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.rtf import set_metadata
        set_metadata(stream, mi)


class TOPAZMetadataWriter(MetadataWriterPlugin):

    name        = 'Set TOPAZ metadata'
    file_types  = {'tpz', 'azw1'}
    description = 'Set metadata in TOPAZ files'
    author      = 'Greg Riker'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.topaz import set_metadata
        set_metadata(stream, mi)


class TXTZMetadataWriter(MetadataWriterPlugin):

    name        = 'Set TXTZ metadata'
    file_types  = {'txtz'}
    description = 'Set metadata from TXTZ files'
    author      = 'John Schember'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.extz import set_metadata
        set_metadata(stream, mi)


class ODTMetadataWriter(MetadataWriterPlugin):

    name        = 'Set ODT metadata'
    file_types  = {'odt'}
    description = 'Set metadata from ODT files'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.odt import set_metadata
        return set_metadata(stream, mi)


class DocXMetadataWriter(MetadataWriterPlugin):

    name        = 'Set DOCX metadata'
    file_types  = {'docx'}
    description = 'Set metadata from DOCX files'

    def set_metadata(self, stream, mi, type):
        from ebook_converter.ebooks.metadata.docx import set_metadata
        return set_metadata(stream, mi)


plugins += [x for x in list(locals().values()) if isinstance(x, type) and
                                        x.__name__.endswith('MetadataWriter')]

# }}}

# Conversion plugins {{{
from ebook_converter.ebooks.conversion.plugins.comic_input import ComicInput
from ebook_converter.ebooks.conversion.plugins.djvu_input import DJVUInput
from ebook_converter.ebooks.conversion.plugins.epub_input import EPUBInput
from ebook_converter.ebooks.conversion.plugins.fb2_input import FB2Input
from ebook_converter.ebooks.conversion.plugins.html_input import HTMLInput
from ebook_converter.ebooks.conversion.plugins.htmlz_input import HTMLZInput
from ebook_converter.ebooks.conversion.plugins.lit_input import LITInput
from ebook_converter.ebooks.conversion.plugins.mobi_input import MOBIInput
from ebook_converter.ebooks.conversion.plugins.odt_input import ODTInput
from ebook_converter.ebooks.conversion.plugins.pdb_input import PDBInput
from ebook_converter.ebooks.conversion.plugins.azw4_input import AZW4Input
from ebook_converter.ebooks.conversion.plugins.pdf_input import PDFInput
from ebook_converter.ebooks.conversion.plugins.pml_input import PMLInput
from ebook_converter.ebooks.conversion.plugins.rb_input import RBInput
from ebook_converter.ebooks.conversion.plugins.recipe_input import RecipeInput
from ebook_converter.ebooks.conversion.plugins.rtf_input import RTFInput
from ebook_converter.ebooks.conversion.plugins.tcr_input import TCRInput
from ebook_converter.ebooks.conversion.plugins.txt_input import TXTInput
from ebook_converter.ebooks.conversion.plugins.lrf_input import LRFInput
from ebook_converter.ebooks.conversion.plugins.chm_input import CHMInput
from ebook_converter.ebooks.conversion.plugins.snb_input import SNBInput
from ebook_converter.ebooks.conversion.plugins.docx_input import DOCXInput

from ebook_converter.ebooks.conversion.plugins.epub_output import EPUBOutput
from ebook_converter.ebooks.conversion.plugins.fb2_output import FB2Output
from ebook_converter.ebooks.conversion.plugins.lit_output import LITOutput
from ebook_converter.ebooks.conversion.plugins.lrf_output import LRFOutput
from ebook_converter.ebooks.conversion.plugins.mobi_output import (MOBIOutput,
        AZW3Output)
from ebook_converter.ebooks.conversion.plugins.oeb_output import OEBOutput
from ebook_converter.ebooks.conversion.plugins.pdb_output import PDBOutput
from ebook_converter.ebooks.conversion.plugins.pdf_output import PDFOutput
from ebook_converter.ebooks.conversion.plugins.pml_output import PMLOutput
from ebook_converter.ebooks.conversion.plugins.rb_output import RBOutput
from ebook_converter.ebooks.conversion.plugins.rtf_output import RTFOutput
from ebook_converter.ebooks.conversion.plugins.tcr_output import TCROutput
from ebook_converter.ebooks.conversion.plugins.txt_output import TXTOutput, TXTZOutput
from ebook_converter.ebooks.conversion.plugins.html_output import HTMLOutput
from ebook_converter.ebooks.conversion.plugins.htmlz_output import HTMLZOutput
from ebook_converter.ebooks.conversion.plugins.snb_output import SNBOutput
from ebook_converter.ebooks.conversion.plugins.docx_output import DOCXOutput

plugins += [
    ComicInput,
    DJVUInput,
    EPUBInput,
    FB2Input,
    HTMLInput,
    HTMLZInput,
    LITInput,
    MOBIInput,
    ODTInput,
    PDBInput,
    AZW4Input,
    PDFInput,
    PMLInput,
    RBInput,
    RecipeInput,
    RTFInput,
    TCRInput,
    TXTInput,
    LRFInput,
    CHMInput,
    SNBInput,
    DOCXInput,
]
plugins += [
    EPUBOutput,
    DOCXOutput,
    FB2Output,
    LITOutput,
    LRFOutput,
    MOBIOutput, AZW3Output,
    OEBOutput,
    PDBOutput,
    PDFOutput,
    PMLOutput,
    RBOutput,
    RTFOutput,
    TCROutput,
    TXTOutput,
    TXTZOutput,
    HTMLOutput,
    HTMLZOutput,
    SNBOutput,
]
# }}}

# Catalog plugins {{{
from ebook_converter.library.catalogs.csv_xml import CSV_XML
from ebook_converter.library.catalogs.bibtex import BIBTEX
from ebook_converter.library.catalogs.epub_mobi import EPUB_MOBI
plugins += [CSV_XML, BIBTEX, EPUB_MOBI]
# }}}

# Profiles {{{
from ebook_converter.customize.profiles import input_profiles, output_profiles
plugins += input_profiles + output_profiles
# }}}

# Device driver plugins {{{
#from ebook_converter.devices.hanlin.driver import HANLINV3, HANLINV5, BOOX, SPECTRA
#from ebook_converter.devices.blackberry.driver import BLACKBERRY, PLAYBOOK
#from ebook_converter.devices.cybook.driver import CYBOOK, ORIZON, MUSE, DIVA
#from ebook_converter.devices.eb600.driver import (EB600, COOL_ER, SHINEBOOK, TOLINO,
#                POCKETBOOK360, GER2, ITALICA, ECLICTO, DBOOK, INVESBOOK,
#                BOOQ, ELONEX, POCKETBOOK301, MENTOR, POCKETBOOK602,
#                POCKETBOOK701, POCKETBOOK740, POCKETBOOK360P, PI2, POCKETBOOK622,
#                POCKETBOOKHD)
#from ebook_converter.devices.iliad.driver import ILIAD
#from ebook_converter.devices.irexdr.driver import IREXDR1000, IREXDR800
#from ebook_converter.devices.jetbook.driver import (JETBOOK, MIBUK, JETBOOK_MINI,
#        JETBOOK_COLOR)
#from ebook_converter.devices.kindle.driver import (KINDLE, KINDLE2, KINDLE_DX,
#        KINDLE_FIRE)
#from ebook_converter.devices.nook.driver import NOOK, NOOK_COLOR
#from ebook_converter.devices.prs505.driver import PRS505
#from ebook_converter.devices.prst1.driver import PRST1
#from ebook_converter.devices.user_defined.driver import USER_DEFINED
#from ebook_converter.devices.android.driver import ANDROID, S60, WEBOS
#from ebook_converter.devices.nokia.driver import N770, N810, E71X, E52
#from ebook_converter.devices.eslick.driver import ESLICK, EBK52
#from ebook_converter.devices.nuut2.driver import NUUT2
#from ebook_converter.devices.iriver.driver import IRIVER_STORY
#from ebook_converter.devices.binatone.driver import README
#from ebook_converter.devices.hanvon.driver import (N516, EB511, ALEX, AZBOOKA, THEBOOK,
#        LIBREAIR, ODYSSEY, KIBANO)
#from ebook_converter.devices.edge.driver import EDGE
#from ebook_converter.devices.teclast.driver import (TECLAST_K3, NEWSMY, IPAPYRUS,
#        SOVOS, PICO, SUNSTECH_EB700, ARCHOS7O, STASH, WEXLER)
#from ebook_converter.devices.sne.driver import SNE
#from ebook_converter.devices.misc import (
#    PALMPRE, AVANT, SWEEX, PDNOVEL, GEMEI, VELOCITYMICRO, PDNOVEL_KOBO,
#    LUMIREAD, ALURATEK_COLOR, TREKSTOR, EEEREADER, NEXTBOOK, ADAM, MOOVYBOOK,
#    COBY, EX124G, WAYTEQ, WOXTER, POCKETBOOK626, SONYDPTS1, CERVANTES)
#from ebook_converter.devices.folder_device.driver import FOLDER_DEVICE_FOR_CONFIG
#from ebook_converter.devices.kobo.driver import KOBO, KOBOTOUCH
#from ebook_converter.devices.boeye.driver import BOEYE_BEX, BOEYE_BDX
#from ebook_converter.devices.smart_device_app.driver import SMART_DEVICE_APP
#from ebook_converter.devices.mtp.driver import MTP_DEVICE

# Order here matters. The first matched device is the one used.
#plugins += [
#    HANLINV3,
#    HANLINV5,
#    BLACKBERRY, PLAYBOOK,
#    CYBOOK, ORIZON, MUSE, DIVA,
#    ILIAD,
#    IREXDR1000,
#    IREXDR800,
#    JETBOOK, JETBOOK_MINI, MIBUK, JETBOOK_COLOR,
#    SHINEBOOK,
#    POCKETBOOK360, POCKETBOOK301, POCKETBOOK602, POCKETBOOK701, POCKETBOOK360P,
#    POCKETBOOK622, PI2, POCKETBOOKHD, POCKETBOOK740,
#    KINDLE, KINDLE2, KINDLE_DX, KINDLE_FIRE,
#    NOOK, NOOK_COLOR,
#    PRS505, PRST1,
#    ANDROID, S60, WEBOS,
#    N770,
#    E71X,
#    E52,
#    N810,
#    COOL_ER,
#    ESLICK,
#    EBK52,
#    NUUT2,
#    IRIVER_STORY,
#    GER2,
#    ITALICA,
#    ECLICTO,
#    DBOOK,
#    INVESBOOK,
#    BOOX,
#    BOOQ,
#    EB600, TOLINO,
#    README,
#    N516, KIBANO,
#    THEBOOK, LIBREAIR,
#    EB511,
#    ELONEX,
#    TECLAST_K3,
#    NEWSMY,
#    PICO, SUNSTECH_EB700, ARCHOS7O, SOVOS, STASH, WEXLER,
#    IPAPYRUS,
#    EDGE,
#    SNE,
#    ALEX, ODYSSEY,
#    PALMPRE,
#    KOBO, KOBOTOUCH,
#    AZBOOKA,
#    FOLDER_DEVICE_FOR_CONFIG,
#    AVANT, CERVANTES,
#    MENTOR,
#    SWEEX,
#    PDNOVEL,
#    SPECTRA,
#    GEMEI,
#    VELOCITYMICRO,
#    PDNOVEL_KOBO,
#    LUMIREAD,
#    ALURATEK_COLOR,
#    TREKSTOR,
#    EEEREADER,
#    NEXTBOOK,
#    ADAM,
#    MOOVYBOOK, COBY, EX124G, WAYTEQ, WOXTER, POCKETBOOK626, SONYDPTS1,
#    BOEYE_BEX,
#    BOEYE_BDX,
#    MTP_DEVICE,
#    SMART_DEVICE_APP,
#    USER_DEFINED,
#]


# }}}

# Interface Actions {{{


class ActionAdd(InterfaceActionBase):
    name = 'Add Books'
    actual_plugin = 'ebook_converter.gui2.actions.add:AddAction'
    description = 'Add books to calibre or the connected device'


class ActionFetchAnnotations(InterfaceActionBase):
    name = 'Fetch Annotations'
    actual_plugin = 'ebook_converter.gui2.actions.annotate:FetchAnnotationsAction'
    description = 'Fetch annotations from a connected Kindle (experimental)'


class ActionGenerateCatalog(InterfaceActionBase):
    name = 'Generate Catalog'
    actual_plugin = 'ebook_converter.gui2.actions.catalog:GenerateCatalogAction'
    description = 'Generate a catalog of the books in your calibre library'


class ActionConvert(InterfaceActionBase):
    name = 'Convert Books'
    actual_plugin = 'ebook_converter.gui2.actions.convert:ConvertAction'
    description = 'Convert books to various e-book formats'


class ActionPolish(InterfaceActionBase):
    name = 'Polish Books'
    actual_plugin = 'ebook_converter.gui2.actions.polish:PolishAction'
    description = 'Fine tune your e-books'


class ActionEditToC(InterfaceActionBase):
    name = 'Edit ToC'
    actual_plugin = 'ebook_converter.gui2.actions.toc_edit:ToCEditAction'
    description = 'Edit the Table of Contents in your books'


class ActionDelete(InterfaceActionBase):
    name = 'Remove Books'
    actual_plugin = 'ebook_converter.gui2.actions.delete:DeleteAction'
    description = 'Delete books from your calibre library or connected device'


class ActionEmbed(InterfaceActionBase):
    name = 'Embed Metadata'
    actual_plugin = 'ebook_converter.gui2.actions.embed:EmbedAction'
    description = ('Embed updated metadata into the actual book files in '
                   'your calibre library')


class ActionEditMetadata(InterfaceActionBase):
    name = 'Edit Metadata'
    actual_plugin = 'ebook_converter.gui2.actions.edit_metadata:EditMetadataAction'
    description = 'Edit the metadata of books in your calibre library'


class ActionView(InterfaceActionBase):
    name = 'View'
    actual_plugin = 'ebook_converter.gui2.actions.view:ViewAction'
    description = 'Read books in your calibre library'


class ActionFetchNews(InterfaceActionBase):
    name = 'Fetch News'
    actual_plugin = 'ebook_converter.gui2.actions.fetch_news:FetchNewsAction'
    description = 'Download news from the internet in e-book form'


class ActionQuickview(InterfaceActionBase):
    name = 'Quickview'
    actual_plugin = 'ebook_converter.gui2.actions.show_quickview:ShowQuickviewAction'
    description = 'Show a list of related books quickly'


class ActionTagMapper(InterfaceActionBase):
    name = 'Tag Mapper'
    actual_plugin = 'ebook_converter.gui2.actions.tag_mapper:TagMapAction'
    description = 'Filter/transform the tags for books in the library'


class ActionAuthorMapper(InterfaceActionBase):
    name = 'Author Mapper'
    actual_plugin = 'ebook_converter.gui2.actions.author_mapper:AuthorMapAction'
    description = 'Transform the authors for books in the library'


class ActionTemplateTester(InterfaceActionBase):
    name = 'Template Tester'
    actual_plugin = 'ebook_converter.gui2.actions.show_template_tester:ShowTemplateTesterAction'
    description = 'Show an editor for testing templates'


class ActionSaveToDisk(InterfaceActionBase):
    name = 'Save To Disk'
    actual_plugin = 'ebook_converter.gui2.actions.save_to_disk:SaveToDiskAction'
    description = 'Export books from your calibre library to the hard disk'


class ActionShowBookDetails(InterfaceActionBase):
    name = 'Show Book Details'
    actual_plugin = 'ebook_converter.gui2.actions.show_book_details:ShowBookDetailsAction'
    description = 'Show Book details in a separate popup'


class ActionRestart(InterfaceActionBase):
    name = 'Restart'
    actual_plugin = 'ebook_converter.gui2.actions.restart:RestartAction'
    description = 'Restart calibre'


class ActionOpenFolder(InterfaceActionBase):
    name = 'Open Folder'
    actual_plugin = 'ebook_converter.gui2.actions.open:OpenFolderAction'
    description = ('Open the folder that contains the book files in your'
            ' calibre library')


class ActionSendToDevice(InterfaceActionBase):
    name = 'Send To Device'
    actual_plugin = 'ebook_converter.gui2.actions.device:SendToDeviceAction'
    description = 'Send books to the connected device'


class ActionConnectShare(InterfaceActionBase):
    name = 'Connect Share'
    actual_plugin = 'ebook_converter.gui2.actions.device:ConnectShareAction'
    description = ('Send books via email or the web. Also connect to'
            ' folders on your computer as if they are devices')


class ActionHelp(InterfaceActionBase):
    name = 'Help'
    actual_plugin = 'ebook_converter.gui2.actions.help:HelpAction'
    description = 'Browse the calibre User Manual'


class ActionPreferences(InterfaceActionBase):
    name = 'Preferences'
    actual_plugin = 'ebook_converter.gui2.actions.preferences:PreferencesAction'
    description = 'Customize calibre'


class ActionSimilarBooks(InterfaceActionBase):
    name = 'Similar Books'
    actual_plugin = 'ebook_converter.gui2.actions.similar_books:SimilarBooksAction'
    description = 'Easily find books similar to the currently selected one'


class ActionChooseLibrary(InterfaceActionBase):
    name = 'Choose Library'
    actual_plugin = 'ebook_converter.gui2.actions.choose_library:ChooseLibraryAction'
    description = ('Switch between different calibre libraries and perform '
                   'maintenance on them')


class ActionAddToLibrary(InterfaceActionBase):
    name = 'Add To Library'
    actual_plugin = 'ebook_converter.gui2.actions.add_to_library:AddToLibraryAction'
    description = 'Copy books from the device to your calibre library'


class ActionEditCollections(InterfaceActionBase):
    name = 'Edit Collections'
    actual_plugin = 'ebook_converter.gui2.actions.edit_collections:EditCollectionsAction'
    description = ('Edit the collections in which books are placed on your '
                   'device')


class ActionMatchBooks(InterfaceActionBase):
    name = 'Match Books'
    actual_plugin = 'ebook_converter.gui2.actions.match_books:MatchBookAction'
    description = 'Match book on the devices to books in the library'


class ActionCopyToLibrary(InterfaceActionBase):
    name = 'Copy To Library'
    actual_plugin = 'ebook_converter.gui2.actions.copy_to_library:CopyToLibraryAction'
    description = 'Copy a book from one calibre library to another'


class ActionTweakEpub(InterfaceActionBase):
    name = 'Tweak ePub'
    actual_plugin = 'ebook_converter.gui2.actions.tweak_epub:TweakEpubAction'
    description = 'Edit e-books in the EPUB or AZW3 formats'


class ActionUnpackBook(InterfaceActionBase):
    name = 'Unpack Book'
    actual_plugin = 'ebook_converter.gui2.actions.unpack_book:UnpackBookAction'
    description = ('Make small changes to EPUB or HTMLZ files in your '
                   'calibre library')


class ActionNextMatch(InterfaceActionBase):
    name = 'Next Match'
    actual_plugin = 'ebook_converter.gui2.actions.next_match:NextMatchAction'
    description = ('Find the next or previous match when searching in '
                   'your calibre library in highlight mode')


class ActionPickRandom(InterfaceActionBase):
    name = 'Pick Random Book'
    actual_plugin = 'ebook_converter.gui2.actions.random:PickRandomAction'
    description = 'Choose a random book from your calibre library'


class ActionSortBy(InterfaceActionBase):
    name = 'Sort By'
    actual_plugin = 'ebook_converter.gui2.actions.sort:SortByAction'
    description = 'Sort the list of books'


class ActionMarkBooks(InterfaceActionBase):
    name = 'Mark Books'
    actual_plugin = 'ebook_converter.gui2.actions.mark_books:MarkBooksAction'
    description = 'Temporarily mark books'


class ActionVirtualLibrary(InterfaceActionBase):
    name = 'Virtual Library'
    actual_plugin = 'ebook_converter.gui2.actions.virtual_library:VirtualLibraryAction'
    description = 'Change the current Virtual library'


class ActionStore(InterfaceActionBase):
    name = 'Store'
    author = 'John Schember'
    actual_plugin = 'ebook_converter.gui2.actions.store:StoreAction'
    description = 'Search for books from different book sellers'

    def customization_help(self, gui=False):
        return 'Customize the behavior of the store search.'

    def config_widget(self):
        from ebook_converter.gui2.store.config.store import config_widget as get_cw
        return get_cw()

    def save_settings(self, config_widget):
        from ebook_converter.gui2.store.config.store import save_settings as save
        save(config_widget)


class ActionPluginUpdater(InterfaceActionBase):
    name = 'Plugin Updater'
    author = 'Grant Drake'
    description = ('Get new ebook_converter plugins or update your existing '
                   'ones')
    actual_plugin = 'calibre.gui2.actions.plugin_updates:PluginUpdaterAction'


plugins += [ActionAdd, ActionFetchAnnotations, ActionGenerateCatalog,
        ActionConvert, ActionDelete, ActionEditMetadata, ActionView,
        ActionFetchNews, ActionSaveToDisk, ActionQuickview, ActionPolish,
        ActionShowBookDetails,ActionRestart, ActionOpenFolder, ActionConnectShare,
        ActionSendToDevice, ActionHelp, ActionPreferences, ActionSimilarBooks,
        ActionAddToLibrary, ActionEditCollections, ActionMatchBooks, ActionChooseLibrary,
        ActionCopyToLibrary, ActionTweakEpub, ActionUnpackBook, ActionNextMatch, ActionStore,
        ActionPluginUpdater, ActionPickRandom, ActionEditToC, ActionSortBy,
        ActionMarkBooks, ActionEmbed, ActionTemplateTester, ActionTagMapper, ActionAuthorMapper,
        ActionVirtualLibrary]

# }}}


if __name__ == '__main__':
    # Test load speed
    import subprocess, textwrap
    try:
        subprocess.check_call(['python', '-c', textwrap.dedent(
        '''
        import init_calibre  # noqa

        def doit():
            import ebook_converter.customize.builtins as b  # noqa

        def show_stats():
            from pstats import Stats
            s = Stats('/tmp/calibre_stats')
            s.sort_stats('cumulative')
            s.print_stats(30)

        import cProfile
        cProfile.run('doit()', '/tmp/calibre_stats')
        show_stats()

        '''
        )])
    except subprocess.CalledProcessError:
        raise SystemExit(1)
    try:
        subprocess.check_call(['python', '-c', textwrap.dedent(
        '''
        import time, sys, init_calibre
        st = time.time()
        import ebook_converter.customize.builtins
        t = time.time() - st
        ret = 0

        for x in ('lxml', 'ebook_converter.ebooks.BeautifulSoup', 'uuid',
            'ebook_converter.utils.terminal', 'ebook_converter.utils.img', 'PIL', 'Image',
            'sqlite3', 'mechanize', 'httplib', 'xml', 'inspect', 'urllib',
            'ebook_converter.utils.date', 'ebook_converter.utils.config', 'platform',
            'ebook_converter.utils.zipfile', 'ebook_converter.utils.formatter',
        ):
            if x in sys.modules:
                ret = 1
                print (x, 'has been loaded by a plugin')
        if ret:
            print ('\\nA good way to track down what is loading something is to run'
            ' python -c "import init_calibre; import ebook_converter.customize.builtins"')
            print()
        print ('Time taken to import all plugins: %.2f'%t)
        sys.exit(ret)

        ''')])
    except subprocess.CalledProcessError:
        raise SystemExit(1)
