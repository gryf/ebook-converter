import mimetypes
import pkg_resources


mimetypes.init([pkg_resources.
                resource_filename('ebook_converter', 'data/mime.types')])
