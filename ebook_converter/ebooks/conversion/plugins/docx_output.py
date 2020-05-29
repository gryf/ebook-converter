import io

from lxml import etree

from ebook_converter import constants as const
from ebook_converter.customize import conversion
from ebook_converter.ebooks.docx.dump import do_dump
from ebook_converter.ebooks.docx.writer.container import DOCX
from ebook_converter.ebooks.docx.writer.from_html import Convert
from ebook_converter.ebooks.metadata import opf2 as opf_meta
from ebook_converter.ebooks.oeb import base


PAGE_SIZES = ['a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'b0', 'b1',
              'b2', 'b3', 'b4', 'b5', 'b6', 'legal', 'letter']
_OPT = conversion.OptionRecommendation


class DOCXOutput(conversion.OutputFormatPlugin):

    name = 'DOCX Output'
    author = 'Kovid Goyal'
    file_type = 'docx'
    commit_name = 'docx_output'
    ui_data = {'page_sizes': PAGE_SIZES}

    options = {_OPT(name='docx_page_size', recommended_value='letter',
                    level=_OPT.LOW, choices=PAGE_SIZES,
                    help='The size of the page. Default is letter. Choices '
                    'are %s' % PAGE_SIZES),
               _OPT(name='docx_custom_page_size', recommended_value=None,
                    help='Custom size of the document. Use the form '
                    'widthxheight EG. `123x321` to specify the width and '
                    'height (in pts). This overrides any specified '
                    'page-size.'),
               _OPT(name='docx_no_cover', recommended_value=False,
                    help='Do not insert the book cover as an image at the '
                    'start of the document. If you use this option, the book '
                    'cover will be discarded.'),
               _OPT(name='preserve_cover_aspect_ratio',
                    recommended_value=False, help='Preserve the aspect ratio '
                    'of the cover image instead of stretching it out to cover '
                    'the entire page.'),
               _OPT(name='docx_no_toc', recommended_value=False,
                    help='Do not insert the table of contents as a page at '
                    'the start of the document.'),
               _OPT(name='extract_to', help='Extract the contents of the '
                    'generated DOCX file to the specified directory. The '
                    'contents of the directory are first deleted, so be '
                    'careful.'),
               _OPT(name='docx_page_margin_left', recommended_value=72.0,
                    level=_OPT.LOW, help='The size of the left page margin, '
                    'in pts. Default is 72pt. Overrides the common left page '
                    'margin setting.'),
               _OPT(name='docx_page_margin_top', recommended_value=72.0,
                    level=_OPT.LOW, help='The size of the top page margin, '
                    'in pts. Default is 72pt. Overrides the common top page '
                    'margin setting, unless set to zero.'),
               _OPT(name='docx_page_margin_right', recommended_value=72.0,
                    level=_OPT.LOW, help='The size of the right page margin, '
                    'in pts. Default is 72pt. Overrides the common right page '
                    'margin setting, unless set to zero.'),
               _OPT(name='docx_page_margin_bottom', recommended_value=72.0,
                    level=_OPT.LOW, help='The size of the bottom page margin, '
                    'in pts. Default is 72pt. Overrides the common bottom '
                    'page margin setting, unless set to zero.')}

    def convert_metadata(self, oeb):

        package = etree.Element(base.tag('opf', 'package'),
                                attrib={'version': '2.0'},
                                nsmap={None: const.OPF2_NS})
        oeb.metadata.to_opf2(package)
        self.mi = opf_meta.OPF(io.BytesIO(etree.tostring(package,
                                                         encoding='utf-8')),
                               populate_spine=False,
                               try_to_guess_cover=False).to_book_metadata()

    def convert(self, oeb, output_path, input_plugin, opts, log):
        docx = DOCX(opts, log)
        self.convert_metadata(oeb)
        Convert(oeb, docx, self.mi, not opts.docx_no_cover,
                not opts.docx_no_toc)()
        docx.write(output_path, self.mi)
        if opts.extract_to:
            do_dump(output_path, opts.extract_to)
