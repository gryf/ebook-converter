import mimetypes
import textwrap
import urllib.parse

from lxml import etree

from ebook_converter.utils.imghdr import identify
from ebook_converter.polyglot.urllib import unquote


class CoverManager(object):

    SVG_TEMPLATE = textwrap.dedent('''\
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <meta name="calibre:cover" content="true" />
        <title>Cover</title>
        <style type="text/css" title="override_css">
            @page {padding: 0pt; margin:0pt}
            body { text-align: center; padding:0pt; margin: 0pt; }
        </style>
    </head>
    <body>
        <div>
            <svg version="1.1" xmlns="http://www.w3.org/2000/svg"
                xmlns:xlink="http://www.w3.org/1999/xlink"
                width="100%%" height="100%%" viewBox="__viewbox__"
                preserveAspectRatio="__ar__">
                <image width="__width__" height="__height__" xlink:href="%s"/>
            </svg>
        </div>
    </body>
</html>''')

    NONSVG_TEMPLATE = textwrap.dedent('''\
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <meta name="calibre:cover" content="true" />
        <title>Cover</title>
        <style type="text/css" title="override_css">
            @page {padding: 0pt; margin:0pt}
            body { text-align: center; padding:0pt; margin: 0pt }
            div { padding:0pt; margin: 0pt }
            img { padding:0pt; margin: 0pt }
        </style>
    </head>
    <body>
        <div>
            <img src="%s" alt="cover" __style__ />
        </div>
    </body>
</html>
    ''')

    def __init__(self, no_default_cover=False, no_svg_cover=False,
                 preserve_aspect_ratio=False, fixed_size=None):
        self.no_default_cover = no_default_cover
        self.no_svg_cover = no_svg_cover
        self.preserve_aspect_ratio = preserve_aspect_ratio

        ar = 'xMidYMid meet' if preserve_aspect_ratio else 'none'
        self.svg_template = self.SVG_TEMPLATE.replace('__ar__', ar)

        if fixed_size is None:
            style = 'style="height: 100%%"'
        else:
            width, height = fixed_size
            style = 'style="height: %s; width: %s"' % (height, width)
        self.non_svg_template = self.NONSVG_TEMPLATE.replace('__style__',
                                                             style)

    def __call__(self, oeb, opts, log):
        self.oeb = oeb
        self.log = log
        self.insert_cover()

    def inspect_cover(self, href):
        from ebook_converter.ebooks.oeb.base import urlnormalize
        for x in self.oeb.manifest:
            if x.href == urlnormalize(href):
                try:
                    raw = x.data
                    return identify(raw)[1:]
                except Exception:
                    self.log.exception('Failed to read cover image dimensions')
        return -1, -1

    def insert_cover(self):
        g, m = self.oeb.guide, self.oeb.manifest
        item = None
        href = None
        if 'titlepage' not in g:
            if 'cover' in g:
                href = g['cover'].href
            if href is None:
                return
            width, height = self.inspect_cover(href)
            if width == -1 or height == -1:
                self.log.warning('Failed to read cover dimensions')
                width, height = 600, 800
            # if self.preserve_aspect_ratio:
            #    width, height = 600, 800
            self.svg_template = self.svg_template.replace('__viewbox__',
                                                          '0 0 %d %d' %
                                                          (width, height))
            self.svg_template = self.svg_template.replace('__width__',
                                                          str(width))
            self.svg_template = self.svg_template.replace('__height__',
                                                          str(height))

            if href is not None:
                templ = self.non_svg_template if self.no_svg_cover \
                        else self.svg_template
                tp = templ % unquote(href)
                id, href = m.generate('titlepage', 'titlepage.xhtml')
                item = m.add(id, href, mimetypes.guess_type('t.xhtml')[0],
                             data=etree.fromstring(tp))
        else:
            key = urllib.parse.urldefrag(self.oeb.guide['titlepage'].href)[0]
            item = self.oeb.manifest.hrefs[key]
        if item is not None:
            self.oeb.spine.insert(0, item, True)
            if 'cover' not in self.oeb.guide.refs:
                self.oeb.guide.add('cover', 'Title Page', 'a')
            self.oeb.guide.refs['cover'].href = item.href
            if 'titlepage' in self.oeb.guide.refs:
                self.oeb.guide.refs['titlepage'].href = item.href
            titem = getattr(self.oeb.toc, 'item_that_refers_to_cover', None)
            if titem is not None:
                titem.href = item.href
