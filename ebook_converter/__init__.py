import mimetypes
from importlib.resources import files


mime_path = files('ebook_converter').joinpath('data/mime.types')
mimetypes.init([str(mime_path)])