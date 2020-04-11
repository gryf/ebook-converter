import setuptools

module = setuptools.Extension('ebook_converter.ebooks.compression.cPalmdoc',
                              sources=['ebook_converter/ebooks/compression/'
                                       'palmdoc.c'],
                              language='c')

setuptools.setup(ext_modules=[module])
# setuptools.setup()
