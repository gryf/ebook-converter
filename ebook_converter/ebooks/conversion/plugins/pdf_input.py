import os

from ebook_converter.customize.conversion import InputFormatPlugin, OptionRecommendation
from ebook_converter import polyglot


class PDFInput(InputFormatPlugin):

    name        = 'PDF Input'
    author      = 'Kovid Goyal and John Schember'
    description = 'Convert PDF files to HTML'
    file_types  = {'pdf'}
    commit_name = 'pdf_input'

    options = {
        OptionRecommendation(name='no_images', recommended_value=False,
            help='Do not extract images from the document'),
        OptionRecommendation(name='unwrap_factor', recommended_value=0.45,
            help='Scale used to determine the length at which a line should '
            'be unwrapped. Valid values are a decimal between 0 and 1. The '
            'default is 0.45, just below the median line length.'),
        OptionRecommendation(name='new_pdf_engine', recommended_value=False,
            help='Use the new PDF conversion engine. Currently not operational.')
    }

    def convert_new(self, stream, accelerators):
        from ebook_converter.ebooks.pdf.pdftohtml import pdftohtml
        from ebook_converter.utils.cleantext import clean_ascii_chars
        from ebook_converter.ebooks.pdf.reflow import PDFDocument

        pdftohtml(os.getcwd(), stream.name, self.opts.no_images, as_xml=True)
        with open('index.xml', 'rb') as f:
            xml = clean_ascii_chars(f.read())
        PDFDocument(xml, self.opts, self.log)
        return os.path.join(os.getcwd(), 'metadata.opf')

    def convert(self, stream, options, file_ext, log, accelerators):
        from ebook_converter.ebooks.metadata.opf2 import OPFCreator
        from ebook_converter.ebooks.pdf.pdftohtml import pdftohtml

        log.debug('Converting file to html...')
        # The main html file will be named index.html
        self.opts, self.log = options, log
        if options.new_pdf_engine:
            return self.convert_new(stream, accelerators)
        pdftohtml(os.getcwd(), stream.name, options.no_images)

        from ebook_converter.ebooks.metadata.meta import get_metadata
        log.debug('Retrieving document metadata...')
        mi = get_metadata(stream, 'pdf')
        opf = OPFCreator(os.getcwd(), mi)

        manifest = [('index.html', None)]

        images = os.listdir(os.getcwd())
        images.remove('index.html')
        for i in images:
            manifest.append((i, None))
        log.debug('Generating manifest...')
        opf.create_manifest(manifest)

        opf.create_spine(['index.html'])
        log.debug('Rendering manifest...')
        with open('metadata.opf', 'wb') as opffile:
            opf.render(opffile)
        if os.path.exists('toc.ncx'):
            ncxid = opf.manifest.id_for_path('toc.ncx')
            if ncxid:
                with open('metadata.opf', 'r+b') as f:
                    raw = f.read().replace(b'<spine', b'<spine toc="%s"' %
                                           polyglot.as_bytes(ncxid))
                    f.seek(0)
                    f.write(raw)

        return os.path.join(os.getcwd(), 'metadata.opf')
