import os

from ebook_converter.customize.conversion import InputFormatPlugin


__license__ = 'GPL v3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


class AZW4Input(InputFormatPlugin):

    name        = 'AZW4 Input'
    author      = 'John Schember'
    description = 'Convert AZW4 to HTML'
    file_types  = {'azw4'}
    commit_name = 'azw4_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from ebook_converter.ebooks.pdb.header import PdbHeaderReader
        from ebook_converter.ebooks.azw4.reader import Reader

        header = PdbHeaderReader(stream)
        reader = Reader(header, stream, log, options)
        opf = reader.extract_content(os.getcwd())

        return opf
