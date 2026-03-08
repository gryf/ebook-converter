import mimetypes
from importlib.resources import files


mimetypes.init([str(files('ebook_converter').joinpath('data/mime.types'))])
