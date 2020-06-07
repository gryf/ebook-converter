from lxml import etree

from ebook_converter import constants as const
from ebook_converter.ebooks.oeb import base
from ebook_converter.utils.localization import canonicalize_lang


def get_book_language(container):
    for lang in container.opf_xpath('//dc:language'):
        raw = lang.text
        if raw:
            code = canonicalize_lang(raw.split(',')[0].strip())
            if code:
                return code


def set_guide_item(container, item_type, title, name, frag=None):
    ref_tag = base.tag('opf', 'reference')
    href = None
    if name:
        href = container.name_to_href(name, container.opf_name)
        if frag:
            href += '#' + frag

    guides = container.opf_xpath('//opf:guide')
    if not guides and href:
        g = container.opf.makeelement(base.tag('opf', 'guide'),
                                      nsmap={'opf': const.OPF2_NS})
        container.insert_into_xml(container.opf, g)
        guides = [g]

    for guide in guides:
        matches = []
        for child in guide.iterchildren(etree.Element):
            if (child.tag == ref_tag and
                    child.get('type', '').lower() == item_type.lower()):
                matches.append(child)
        if not matches and href:
            r = guide.makeelement(ref_tag, type=item_type,
                                  nsmap={'opf': const.OPF2_NS})
            container.insert_into_xml(guide, r)
            matches.append(r)
        for m in matches:
            if href:
                m.set('title', title)
                m.set('href', href)
                m.set('type', item_type)
            else:
                container.remove_from_xml(m)
    container.dirty(container.opf_name)
