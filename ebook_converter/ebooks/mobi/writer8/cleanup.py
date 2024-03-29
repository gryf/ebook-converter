from ebook_converter.ebooks.oeb.base import XPath


class CSSCleanup(object):

    def __init__(self, log, opts):
        self.log, self.opts = log, opts

    def __call__(self, item, stylizer):
        if not hasattr(item.data, 'xpath'):
            return

        # The Kindle touch displays all black pages if the height is set on
        # body
        for body in XPath('//h:body')(item.data):
            style = stylizer.style(body)
            style.drop('height')


def remove_duplicate_anchors(oeb):
    # The Kindle apparently has incorrect behavior for duplicate anchors, see
    # https://bugs.launchpad.net/calibre/+bug/1454199
    for item in oeb.spine:
        if not hasattr(item.data, 'xpath'):
            continue
        seen = set()
        for tag in item.data.xpath('//*[@id or @name]'):
            for attr in ('id', 'name'):
                anchor = tag.get(attr)
                if anchor is not None:
                    if anchor in seen:
                        oeb.log.debug('Removing duplicate anchor: %s', anchor)
                        tag.attrib.pop(attr)
                    else:
                        seen.add(anchor)
