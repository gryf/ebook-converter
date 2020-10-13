import os
import shutil

from lxml import etree

from ebook_converter.utils.zipfile import ZipFile
from ebook_converter.utils.xml_parse import safe_xml_fromstring


def pretty_all_xml_in_dir(path):
    for root, _, fnames in os.walk(path):
        for f in fnames:
            f = os.path.join(root, f)
            if f.endswith('.xml') or f.endswith('.rels'):
                with open(f, 'r+b') as stream:
                    raw = stream.read()
                    if raw:
                        root = safe_xml_fromstring(raw)
                        stream.seek(0)
                        stream.truncate()
                        stream.write(etree.tostring(root, pretty_print=True,
                                                    encoding='utf-8',
                                                    xml_declaration=True))


def do_dump(path, dest):
    if os.path.exists(dest):
        shutil.rmtree(dest)
    with ZipFile(path) as zf:
        zf.extractall(dest)
    pretty_all_xml_in_dir(dest)


def dump(path):
    dest = os.path.splitext(os.path.basename(path))[0]
    dest += '-dumped'
    do_dump(path, dest)

    print(path, 'dumped to', dest)
