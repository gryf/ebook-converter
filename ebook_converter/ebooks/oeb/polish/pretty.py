import textwrap

from ebook_converter import constants as const
from ebook_converter import force_unicode
from ebook_converter.ebooks.oeb import parse_utils
from ebook_converter.ebooks.oeb import base
from ebook_converter.ebooks.oeb.polish.utils import guess_type
from ebook_converter.utils.icu import sort_key


def isspace(x):
    return not x.strip('\u0009\u000a\u000c\u000d\u0020')


def pretty_xml_tree(elem, level=0, indent='  '):
    ''' XML beautifier, assumes that elements that have children do not have
    textual content.  Also assumes that there is no text immediately after
    closing tags. These are true for opf/ncx and container.xml files. If either
    of the assumptions are violated, there should be no data loss, but pretty
    printing wont produce optimal results.'''
    if (not elem.text and len(elem) > 0) or (elem.text and isspace(elem.text)):
        elem.text = '\n' + (indent * (level+1))
    for i, child in enumerate(elem):
        pretty_xml_tree(child, level=level+1, indent=indent)
        if not child.tail or isspace(child.tail):
            new_level = level + 1
            if i == len(elem) - 1:
                new_level -= 1
            child.tail = '\n' + (indent * new_level)


def pretty_opf(root):
    # Put all dc: tags first starting with title and author. Preserve order for
    # the rest.
    def dckey(x):
        return {'title': 0, 'creator': 1}.get(parse_utils.barename(x.tag), 2)

    for metadata in root.xpath('//opf:metadata',
                               namespaces=const.OPF_NAMESPACES):
        dc_tags = metadata.xpath('./*[namespace-uri()="%s"]' % const.DC11_NS)
        dc_tags.sort(key=dckey)
        for x in reversed(dc_tags):
            metadata.insert(0, x)

    # Group items in the manifest
    spine_ids = root.xpath('//opf:spine/opf:itemref/@idref',
                           namespaces=const.OPF_NAMESPACES)
    spine_ids = {x: i for i, x in enumerate(spine_ids)}

    def manifest_key(x):
        mt = x.get('media-type', '')
        href = x.get('href', '')
        ext = href.rpartition('.')[-1].lower()
        cat = 1000
        if mt in base.OEB_DOCS:
            cat = 0
        elif mt == guess_type('a.ncx'):
            cat = 1
        elif mt in base.OEB_STYLES:
            cat = 2
        elif mt.startswith('image/'):
            cat = 3
        elif ext in {'otf', 'ttf', 'woff'}:
            cat = 4
        elif mt.startswith('audio/'):
            cat = 5
        elif mt.startswith('video/'):
            cat = 6

        if cat == 0:
            i = spine_ids.get(x.get('id', None), 1000000000)
        else:
            i = sort_key(href)
        return (cat, i)

    for manifest in root.xpath('//opf:manifest',
                               namespaces=const.OPF_NAMESPACES):
        try:
            children = sorted(manifest, key=manifest_key)
        except AttributeError:
            # There are comments so dont sort since that would mess up the
            # comments.
            continue

        for x in reversed(children):
            manifest.insert(0, x)


def isblock(x):
    if callable(x.tag) or not x.tag:
        return True
    if x.tag in const.XHTML_BLOCK_TAGS | {base.tag('svg', 'svg')}:
        return True
    return False


def has_only_blocks(x):
    if hasattr(x.tag, 'split') and len(x) == 0:
        # Tag with no children,
        return False
    if x.text and not isspace(x.text):
        return False
    for child in x:
        if not isblock(child) or (child.tail and not isspace(child.tail)):
            return False
    return True


def indent_for_tag(x):
    prev = x.getprevious()
    x = x.getparent().text if prev is None else prev.tail
    if not x:
        return ''
    s = x.rpartition('\n')[-1]
    return s if isspace(s) else ''


def set_indent(elem, attr, indent):
    x = getattr(elem, attr)
    if not x:
        x = indent
    else:
        lines = x.splitlines()
        if isspace(lines[-1]):
            lines[-1] = indent
        else:
            lines.append(indent)
        x = '\n'.join(lines)
    setattr(elem, attr, x)


def pretty_block(parent, level=1, indent='  '):
    ''' Surround block tags with blank lines and recurse into child block tags
    that contain only other block tags '''
    if not parent.text or isspace(parent.text):
        parent.text = ''
    if (hasattr(parent.tag, 'strip') and
            parse_utils.barename(parent.tag) in {'tr', 'td', 'th'}):
        nn = '\n'
    else:
        nn = '\n\n'
    parent.text = parent.text + nn + (indent * level)
    for i, child in enumerate(parent):
        if isblock(child) and has_only_blocks(child):
            pretty_block(child, level=level+1, indent=indent)
        elif child.tag == base.tag('svg', 'svg'):
            pretty_xml_tree(child, level=level, indent=indent)
        new_level = level
        if i == len(parent) - 1:
            new_level -= 1
        if not child.tail or isspace(child.tail):
            child.tail = ''
        child.tail = child.tail + nn + (indent * new_level)


def pretty_script_or_style(container, child):
    if child.text:
        indent = indent_for_tag(child)
        if child.tag.endswith('style'):
            child.text = force_unicode(pretty_css(container, '', child.text),
                                       'utf-8')
        child.text = textwrap.dedent(child.text)
        child.text = '\n' + '\n'.join([(indent + x) if x else ''
                                       for x in child.text.splitlines()])
        set_indent(child, 'text', indent)


def pretty_html_tree(container, root):
    root.text = '\n\n'
    for child in root:
        child.tail = '\n\n'
        if hasattr(child.tag, 'endswith') and child.tag.endswith('}head'):
            pretty_xml_tree(child)
    for body in root.findall('h:body', namespaces=const.XPNSMAP):
        pretty_block(body)
        # Special case the handling of a body that contains a single block tag
        # with all content. In this case we prettify the containing block tag
        # even if it has non block children.
        if (len(body) == 1 and
                not callable(body[0].tag) and
                isblock(body[0]) and
                not has_only_blocks(body[0]) and
                parse_utils.barename(body[0].tag) not in ('pre', 'p', 'h1',
                                                          'h2', 'h3', 'h4',
                                                          'h5', 'h6') and
                len(body[0]) > 0):
            pretty_block(body[0], level=2)

    if container is not None:
        # Handle <script> and <style> tags
        for child in root.xpath('//*[local-name()="script" or local-name()='
                                '"style"]'):
            pretty_script_or_style(container, child)


def fix_html(container, raw):
    """
    Fix any parsing errors in the HTML represented as a string in raw. Fixing
    is done using the HTML5 parsing algorithm.
    """
    root = container.parse_xhtml(raw)
    return base.serialize(root, 'text/html')


def pretty_html(container, name, raw):
    """
    Pretty print the HTML represented as a string in raw
    """
    root = container.parse_xhtml(raw)
    pretty_html_tree(container, root)
    return base.serialize(root, 'text/html')


def pretty_css(container, name, raw):
    """
    Pretty print the CSS represented as a string in raw
    """
    sheet = container.parse_css(raw)
    return base.serialize(sheet, 'text/css')


def pretty_xml(container, name, raw):
    """
    Pretty print the XML represented as a string in raw. If ``name`` is the
    name of the OPF, extra OPF-specific prettying is performed.
    """
    root = container.parse_xml(raw)
    if name == container.opf_name:
        pretty_opf(root)
    pretty_xml_tree(root)
    return base.serialize(root, 'text/xml')


def fix_all_html(container):
    """
    Fix any parsing errors in all HTML files in the container. Fixing is done
    using the HTML5 parsing algorithm.  """
    for name, mt in container.mime_map.items():
        if mt in base.OEB_DOCS:
            container.parsed(name)
            container.dirty(name)


def pretty_all(container):
    """
    Pretty print all HTML/CSS/XML files in the container
    """
    xml_types = {guess_type('a.ncx'), guess_type('a.xml'), guess_type('a.svg')}
    for name, mt in container.mime_map.items():
        prettied = False
        if mt in base.OEB_DOCS:
            pretty_html_tree(container, container.parsed(name))
            prettied = True
        elif mt in base.OEB_STYLES:
            container.parsed(name)
            prettied = True
        elif name == container.opf_name:
            root = container.parsed(name)
            pretty_opf(root)
            pretty_xml_tree(root)
            prettied = True
        elif mt in xml_types:
            pretty_xml_tree(container.parsed(name))
            prettied = True
        if prettied:
            container.dirty(name)
