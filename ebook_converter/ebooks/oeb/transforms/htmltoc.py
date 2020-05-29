"""
HTML-TOC-adding transform.
"""
from ebook_converter import constants as const
from ebook_converter.ebooks.oeb import base


DEFAULT_TITLE = 'Table of Contents'
STYLE_CSS = {'nested': '.calibre_toc_header {\n  text-align: center;\n}\n'
             '.calibre_toc_block {\n  margin-left: 1.2em;\n  text-indent: '
             '-1.2em;\n}\n.calibre_toc_block .calibre_toc_block {\n  '
             'margin-left: 2.4em;\n}\n.calibre_toc_block .calibre_toc_block '
             '.calibre_toc_block {\n  margin-left: 3.6em;\n}\n',

             'centered': '.calibre_toc_header {\n  text-align: center;\n}\n'
             '.calibre_toc_block {\n  text-align: center;\n}\nbody > '
             '.calibre_toc_block {\n  margin-top: 1.2em;\n}\n'}


class HTMLTOCAdder(object):

    def __init__(self, title=None, style='nested', position='end'):
        self.title = title
        self.style = style
        self.position = position

    @classmethod
    def config(cls, cfg):
        group = cfg.add_group('htmltoc', 'HTML TOC generation options.')
        group('toc_title', ['--toc-title'], default=None,
              help='Title for any generated in-line table of contents.')
        return cfg

    @classmethod
    def generate(cls, opts):
        return cls(title=opts.toc_title)

    def __call__(self, oeb, context):
        has_toc = getattr(getattr(oeb, 'toc', False), 'nodes', False)

        if 'toc' in oeb.guide:
            # Ensure toc pointed to in <guide> is in spine
            from ebook_converter.ebooks.oeb.base import urlnormalize
            href = urlnormalize(oeb.guide['toc'].href)
            if href in oeb.manifest.hrefs:
                item = oeb.manifest.hrefs[href]
                if (hasattr(item.data, 'xpath') and
                        base.XPath('//h:a[@href]')(item.data)):
                    if oeb.spine.index(item) < 0:
                        if self.position == 'end':
                            oeb.spine.add(item, linear=False)
                        else:
                            oeb.spine.insert(0, item, linear=True)
                    return
                elif has_toc:
                    oeb.guide.remove('toc')
            else:
                oeb.guide.remove('toc')
        if not has_toc:
            return
        oeb.logger.info('Generating in-line TOC...')
        title = self.title or oeb.translate(DEFAULT_TITLE)
        style = self.style
        if style not in STYLE_CSS:
            oeb.logger.error('Unknown TOC style %r' % style)
            style = 'nested'
        id, css_href = oeb.manifest.generate('tocstyle', 'tocstyle.css')
        oeb.manifest.add(id, css_href, base.CSS_MIME, data=STYLE_CSS[style])
        language = str(oeb.metadata.language[0])
        contents = base.element(None, base.tag('xhtml', 'html'),
                                nsmap={None: const.XHTML_NS},
                                attrib={base.tag('xml', 'lang'): language})
        head = base.element(contents, base.tag('xhtml', 'head'))
        htitle = base.element(head, base.tag('xhtml', 'title'))
        htitle.text = title
        base.element(head, base.tag('xhtml', 'link'), rel='stylesheet',
                     type=base.CSS_MIME, href=css_href)
        body = base.element(contents, base.tag('xhtml', 'body'),
                            attrib={'class': 'calibre_toc'})
        h1 = base.element(body, base.tag('xhtml', 'h2'),
                          attrib={'class': 'calibre_toc_header'})
        h1.text = title
        self.add_toc_level(body, oeb.toc)
        id, href = oeb.manifest.generate('contents', 'contents.xhtml')
        item = oeb.manifest.add(id, href, base.XHTML_MIME, data=contents)
        if self.position == 'end':
            oeb.spine.add(item, linear=False)
        else:
            oeb.spine.insert(0, item, linear=True)
        oeb.guide.add('toc', 'Table of Contents', href)

    def add_toc_level(self, elem, toc):
        for node in toc:
            block = base.element(elem, base.tag('xhtml', 'div'),
                                 attrib={'class': 'calibre_toc_block'})
            line = base.element(block, base.tag('xhtml', 'a'),
                                attrib={'href': node.href,
                                        'class': 'calibre_toc_line'})
            line.text = node.title
            self.add_toc_level(block, node)
