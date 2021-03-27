import urllib.parse

from ebook_converter.ebooks.oeb import base
from ebook_converter.ebooks.oeb.base import XPath, xml2text, urlnormalize


JACKET_XPATH = '//h:meta[@name="calibre-content" and @content="jacket"]'


class RemoveFirstImage:

    def remove_images(self, item, limit=1):
        path = XPath('//h:img[@src]')
        removed = 0
        for img in path(item.data):
            if removed >= limit:
                break
            href = item.abshref(img.get('src'))
            image = self.oeb.manifest.hrefs.get(href)
            if image is None:
                href = urlnormalize(href)
                image = self.oeb.manifest.hrefs.get(href)
            if image is not None:
                self.oeb.manifest.remove(image)
                self.oeb.guide.remove_by_href(href)
                img.getparent().remove(img)
                removed += 1
        return removed

    def remove_first_image(self):
        deleted_item = None
        for item in self.oeb.spine:
            if XPath(JACKET_XPATH)(item.data):
                continue
            removed = self.remove_images(item)
            if removed > 0:
                self.log('Removed first image')
                body = XPath('//h:body')(item.data)
                if body:
                    raw = xml2text(body[0]).strip()
                    imgs = XPath('//h:img|//svg:svg')(item.data)
                    if not raw and not imgs:
                        self.log('Removing %s as it has no content' %
                                 item.href)
                        self.oeb.manifest.remove(item)
                        deleted_item = item
                break
        else:
            self.log.warn('Could not find first image to remove')
        if deleted_item is not None:
            for item in list(self.oeb.toc):
                href = urllib.parse.urldefrag(item.href)[0]
                if href == deleted_item.href:
                    self.oeb.toc.remove(item)
            self.oeb.guide.remove_by_href(deleted_item.href)

    def __call__(self, oeb, opts, metadata):
        """
        Add metadata in jacket.xhtml if specified in opts
        If not specified, remove previous jacket instance
        """
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        if opts.remove_first_image:
            self.remove_first_image()


def linearize_jacket(oeb):
    for x in oeb.spine[:4]:
        if XPath(JACKET_XPATH)(x.data):
            for e in XPath('//h:table|//h:tr|//h:th')(x.data):
                e.tag = base.tag('xhtml', 'div')
            for e in XPath('//h:td')(x.data):
                e.tag = base.tag('xhtml', 'span')
            break
