import os
import sys
import pkg_resources

from lxml import etree

from ebook_converter.customize.conversion import InputFormatPlugin


class LRFInput(InputFormatPlugin):

    name = 'LRF Input'
    author = 'Kovid Goyal'
    description = 'Convert LRF files to HTML'
    file_types = {'lrf'}
    commit_name = 'lrf_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from ebook_converter.ebooks.lrf.input import MediaType, Styles, \
                TextBlock, Canvas, ImageBlock, RuledLine
        self.log = log
        self.log.info('Generating XML')
        from ebook_converter.ebooks.lrf.lrfparser import LRFDocument
        d = LRFDocument(stream)
        d.parse()
        xml = d.to_xml(write_files=True)
        if options.verbose > 2:
            open(u'lrs.xml', 'wb').write(xml.encode('utf-8'))
        doc = etree.fromstring(xml)

        char_button_map = {}
        for x in doc.xpath('//CharButton[@refobj]'):
            ro = x.get('refobj')
            jump_button = doc.xpath('//*[@objid="%s"]' % ro)
            if jump_button:
                jump_to = jump_button[0].xpath('descendant::JumpTo[@refpage '
                                               'and @refobj]')
                if jump_to:
                    char_button_map[ro] = ('%s.xhtml#%s' %
                                           (jump_to[0].get('refpage'),
                                            jump_to[0].get('refobj')))
        plot_map = {}
        for x in doc.xpath('//Plot[@refobj]'):
            ro = x.get('refobj')
            image = doc.xpath('//Image[@objid="%s" and @refstream]' % ro)
            if image:
                imgstr = doc.xpath('//ImageStream[@objid="%s" and @file]' %
                                   image[0].get('refstream'))
                if imgstr:
                    plot_map[ro] = imgstr[0].get('file')

        self.log.info('Converting XML to HTML...')

        with open(pkg_resources.
                  resource_filename('ebook_converter',
                                    'data/lrf.xsl')) as fobj:
            # TODO(gryf): change this nonsense to etree.parse() instead.
            styledoc = etree.fromstring(fobj.read())
        media_type = MediaType()
        styles = Styles()
        text_block = TextBlock(styles, char_button_map, plot_map, log)
        canvas = Canvas(doc, styles, text_block, log)
        image_block = ImageBlock(canvas)
        ruled_line = RuledLine()
        extensions = {('calibre', 'media-type'): media_type,
                      ('calibre', 'text-block'): text_block,
                      ('calibre', 'ruled-line'): ruled_line,
                      ('calibre', 'styles'): styles,
                      ('calibre', 'canvas'): canvas,
                      ('calibre', 'image-block'): image_block}
        transform = etree.XSLT(styledoc, extensions=extensions)
        try:
            result = transform(doc)
        except RuntimeError:
            sys.setrecursionlimit(5000)
            result = transform(doc)

        with open('content.opf', 'wb') as f:
            f.write(result)
        styles.write()
        return os.path.abspath('content.opf')
