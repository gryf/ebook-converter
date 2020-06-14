"""
Convert .fb2 files to .lrf
"""
import mimetypes
import os
import pkg_resources
import re

from lxml import etree

from ebook_converter import constants as const
from ebook_converter.customize.conversion import InputFormatPlugin
from ebook_converter.customize.conversion import OptionRecommendation


FB2NS = 'http://www.gribuser.ru/xml/fictionbook/2.0'
FB21NS = 'http://www.gribuser.ru/xml/fictionbook/2.1'


class FB2Input(InputFormatPlugin):

    name = 'FB2 Input'
    author = 'Anatoly Shipitsin'
    description = 'Convert FB2 and FBZ files to HTML'
    file_types = {'fb2', 'fbz'}
    commit_name = 'fb2_input'

    recommendations = {('level1_toc', '//h:h1', OptionRecommendation.MED),
                       ('level2_toc', '//h:h2', OptionRecommendation.MED),
                       ('level3_toc', '//h:h3', OptionRecommendation.MED)}

    options = {OptionRecommendation(name='no_inline_fb2_toc',
                                    recommended_value=False,
                                    level=OptionRecommendation.LOW,
                                    help='Do not insert a Table of Contents '
                                    'at the beginning of the book.')}

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from ebook_converter.ebooks.metadata.fb2 import ensure_namespace
        from ebook_converter.ebooks.metadata.fb2 import get_fb2_data
        from ebook_converter.ebooks.metadata.opf2 import OPFCreator
        from ebook_converter.ebooks.metadata.meta import get_metadata
        from ebook_converter.ebooks.chardet import xml_to_unicode
        self.log = log
        log.debug('Parsing XML...')
        raw = get_fb2_data(stream)[0]
        raw = raw.replace(b'\0', b'')
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                             assume_utf8=True, resolve_entities=True)[0]
        try:
            doc = etree.fromstring(raw)
        except etree.XMLSyntaxError:
            doc = etree.fromstring(raw.replace('& ', '&amp;'))
        if doc is None:
            raise ValueError('The FB2 file is not valid XML')
        doc = ensure_namespace(doc)
        try:
            fb_ns = doc.nsmap[doc.prefix]
        except Exception:
            fb_ns = FB2NS

        NAMESPACES = {'f': fb_ns, 'l': const.XLINK_NS}
        stylesheets = doc.xpath('//*[local-name() = "stylesheet" and '
                                '@type="text/css"]')
        css = ''
        for s in stylesheets:
            css += etree.tostring(s, encoding='unicode', method='text',
                                  with_tail=False) + '\n\n'
        if css:
            import css_parser
            import logging
            parser = css_parser.CSSParser(fetcher=None,
                                          log=logging.getLogger('calibre.css'))

            XHTML_CSS_NAMESPACE = '@namespace "%s";\n' % const.XHTML_NS
            text = XHTML_CSS_NAMESPACE + css
            log.debug('Parsing stylesheet...')
            stylesheet = parser.parseString(text)
            stylesheet.namespaces['h'] = const.XHTML_NS
            css = stylesheet.cssText
            if isinstance(css, bytes):
                css = css.decode('utf-8', 'replace')
            css = css.replace('h|style', 'h|span')
            css = re.sub(r'name\s*=\s*', 'class=', css)
        self.extract_embedded_content(doc)
        log.debug('Converting XML to HTML...')
        with open(pkg_resources.resource_filename('ebook_converter',
                                                  'data/fb2.xsl')) as f:
            ss = f.read()
        ss = ss.replace("__FB_NS__", fb_ns)
        if options.no_inline_fb2_toc:
            log('Disabling generation of inline FB2 TOC')
            ss = re.compile(r'<!-- BUILD TOC -->.*<!-- END BUILD TOC -->',
                            re.DOTALL).sub('', ss)

        styledoc = etree.fromstring(ss)

        transform = etree.XSLT(styledoc)
        result = transform(doc)

        # Handle links of type note and cite
        notes = {a.get('href')[1:]: a
                 for a in result.xpath('//a[@link_note and @href]')
                 if a.get('href').startswith('#')}
        cites = {a.get('link_cite'): a
                 for a in result.xpath('//a[@link_cite]')
                 if not a.get('href', '')}
        all_ids = {x for x in result.xpath('//*/@id')}
        for cite, a in cites.items():
            note = notes.get(cite, None)
            if note:
                c = 1
                while 'cite%d' % c in all_ids:
                    c += 1
                if not note.get('id', None):
                    note.set('id', 'cite%d' % c)
                    all_ids.add(note.get('id'))
                a.set('href', '#%s' % note.get('id'))
        for x in result.xpath('//*[@link_note or @link_cite]'):
            x.attrib.pop('link_note', None)
            x.attrib.pop('link_cite', None)

        for img in result.xpath('//img[@src]'):
            src = img.get('src')
            img.set('src', self.binary_map.get(src, src))
        index = transform.tostring(result)
        with open('index.xhtml', 'wb') as f:
            f.write(index.encode('utf-8'))
        with open('inline-styles.css', 'wb') as f:
            f.write(css.encode('utf-8'))
        stream.seek(0)
        mi = get_metadata(stream, 'fb2')
        if not mi.title:
            mi.title = 'Unknown'
        if not mi.authors:
            mi.authors = ['Unknown']
        cpath = None
        if mi.cover_data and mi.cover_data[1]:
            with open('fb2_cover_calibre_mi.jpg', 'wb') as f:
                f.write(mi.cover_data[1])
            cpath = os.path.abspath('fb2_cover_calibre_mi.jpg')
        else:
            for img in doc.xpath('//f:coverpage/f:image',
                                 namespaces=NAMESPACES):
                href = img.get('{%s}href' % const.XLINK_NS,
                               img.get('href', None))
                if href is not None:
                    if href.startswith('#'):
                        href = href[1:]
                    cpath = os.path.abspath(href)
                    break

        opf = OPFCreator(os.getcwd(), mi)
        entries = [(f2, mimetypes.guess_type(f2)[0])
                   for f2 in os.listdir(u'.')]
        opf.create_manifest(entries)
        opf.create_spine(['index.xhtml'])
        if cpath:
            opf.guide.set_cover(cpath)
        with open('metadata.opf', 'wb') as f:
            opf.render(f)
        return os.path.join(os.getcwd(), 'metadata.opf')

    def extract_embedded_content(self, doc):
        from ebook_converter.ebooks.fb2 import base64_decode
        self.binary_map = {}
        for elem in doc.xpath('./*'):
            if elem.text and 'binary' in elem.tag and 'id' in elem.attrib:
                ct = elem.get('content-type', '')
                fname = elem.attrib['id']
                ext = ct.rpartition('/')[-1].lower()
                if ext in ('png', 'jpeg', 'jpg'):
                    if fname.lower().rpartition('.')[-1] not in {'jpg', 'jpeg',
                                                                 'png'}:
                        fname += '.' + ext
                    self.binary_map[elem.get('id')] = fname
                raw = elem.text.strip()
                try:
                    data = base64_decode(raw)
                except TypeError:
                    self.log.exception('Binary data with id=%s is corrupted, '
                                       'ignoring' % elem.get('id'))
                else:
                    with open(fname, 'wb') as f:
                        f.write(data)
