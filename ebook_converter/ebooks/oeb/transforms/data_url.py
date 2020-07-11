import mimetypes
import re
import urllib.parse

from ebook_converter.ebooks.oeb.base import XPath
from ebook_converter.polyglot.binary import from_base64_bytes
from ebook_converter.polyglot.builtins import as_bytes


class DataURL(object):

    def __call__(self, oeb, opts):
        from ebook_converter.utils.imghdr import what
        self.log = oeb.log
        attr_path = XPath('//h:img[@src]')
        for item in oeb.spine:
            root = item.data
            if not hasattr(root, 'xpath'):
                continue
            for img in attr_path(root):
                raw = img.get('src', '')
                if not raw.startswith('data:'):
                    continue
                header, data = raw.partition(',')[0::2]
                if not header.startswith('data:image/') or not data:
                    continue
                if ';base64' in header:
                    data = re.sub(r'\s+', '', data)
                    try:
                        data = from_base64_bytes(data)
                    except Exception:
                        self.log.error('Found invalid base64 encoded data '
                                       'URI, ignoring it')
                        continue
                else:
                    data = urllib.parse.unquote(data)
                data = as_bytes(data)
                fmt = what(None, data)
                if not fmt:
                    self.log.warn('Image encoded as data URL has unknown '
                                  'format, ignoring')
                    continue
                img.set('src',
                        item.relhref(self.convert_image_data_uri(data, fmt,
                                                                 oeb)))

    def convert_image_data_uri(self, data, fmt, oeb):
        self.log('Found image encoded as data URI converting it to normal '
                 'image')
        item_id, item_href = oeb.manifest.generate('data-url-image',
                                                   'data-url-image.' + fmt)
        oeb.manifest.add(item_id, item_href,
                         mimetypes.guess_type(item_href)[0], data=data)
        return item_href
