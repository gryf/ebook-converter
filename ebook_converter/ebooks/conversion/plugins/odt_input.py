"""
Convert an ODT file into a Open Ebook
"""
from ebook_converter.customize.conversion import InputFormatPlugin


__license__ = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'


class ODTInput(InputFormatPlugin):

    name        = 'ODT Input'
    author      = 'Kovid Goyal'
    description = 'Convert ODT (OpenOffice) files to HTML'
    file_types  = {'odt'}
    commit_name = 'odt_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from ebook_converter.ebooks.odt.input import Extract
        return Extract()(stream, '.', log)
