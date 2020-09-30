import collections
import functools
import operator
import pkg_resources
import re
import urllib.parse

from lxml import etree
from lxml.builder import ElementMaker

from ebook_converter import constants as const
from ebook_converter import constants_old
from ebook_converter.ebooks.oeb import base
from ebook_converter.ebooks.oeb.polish.errors import MalformedMarkup
from ebook_converter.ebooks.oeb.polish.utils import guess_type, extract
from ebook_converter.ebooks.oeb.polish.opf import set_guide_item, get_book_language
from ebook_converter.ebooks.oeb.polish.pretty import pretty_html_tree
from ebook_converter.utils.localization import get_lang, canonicalize_lang, lang_as_iso639_1


ns = etree.FunctionNamespace('calibre_xpath_extensions')
ns.prefix = 'calibre'
ns['lower-case'] = lambda c, x: x.lower() if hasattr(x, 'lower') else x


class TOC(object):

    toc_title = None

    def __init__(self, title=None, dest=None, frag=None):
        self.title, self.dest, self.frag = title, dest, frag
        self.dest_exists = self.dest_error = None
        if self.title:
            self.title = self.title.strip()
        self.parent = None
        self.children = []
        self.page_list = []

    def add(self, title, dest, frag=None):
        c = TOC(title, dest, frag)
        self.children.append(c)
        c.parent = self
        return c

    def remove(self, child):
        self.children.remove(child)
        child.parent = None

    def remove_from_parent(self):
        if self.parent is None:
            return
        idx = self.parent.children.index(self)
        for child in reversed(self.children):
            child.parent = self.parent
            self.parent.children.insert(idx, child)
        self.parent.children.remove(self)
        self.parent = None

    def __iter__(self):
        for c in self.children:
            yield c

    def __len__(self):
        return len(self.children)

    def iterdescendants(self, level=None):
        gc_level = None if level is None else level + 1
        for child in self:
            if level is None:
                yield child
            else:
                yield level, child
            for gc in child.iterdescendants(level=gc_level):
                yield gc

    def remove_duplicates(self, only_text=True):
        seen = set()
        remove = []
        for child in self:
            key = child.title if only_text else (child.title, child.dest,
                                                 (child.frag or None))
            if key in seen:
                remove.append(child)
            else:
                seen.add(key)
                child.remove_duplicates()
        for child in remove:
            self.remove(child)

    @property
    def depth(self):
        """The maximum depth of the navigation tree rooted at this node."""
        try:
            return max(node.depth for node in self) + 1
        except ValueError:
            return 1

    @property
    def last_child(self):
        return self.children[-1] if self.children else None

    def get_lines(self, lvl=0):
        frag = ('#'+self.frag) if self.frag else ''
        ans = [('\t'*lvl) + 'TOC: %s --> %s%s' % (self.title, self.dest, frag)]
        for child in self:
            ans.extend(child.get_lines(lvl+1))
        return ans

    def __str__(self):
        return '\n'.join(self.get_lines())

    def to_dict(self, node_counter=None):
        ans = {'title': self.title, 'dest': self.dest, 'frag': self.frag,
               'children': [c.to_dict(node_counter) for c in self.children]}
        if self.dest_exists is not None:
            ans['dest_exists'] = self.dest_exists
        if self.dest_error is not None:
            ans['dest_error'] = self.dest_error
        if node_counter is not None:
            ans['id'] = next(node_counter)
        return ans

    @property
    def as_dict(self):
        return self.to_dict()


def child_xpath(tag, name):
    return tag.xpath('./*[calibre:lower-case(local-name()) = "%s"]' % name)


def add_from_navpoint(container, navpoint, parent, ncx_name):
    dest = frag = text = None
    nl = child_xpath(navpoint, 'navlabel')
    if nl:
        nl = nl[0]
        text = ''
        for txt in child_xpath(nl, 'text'):
            text += etree.tostring(txt, method='text',
                                   encoding='unicode', with_tail=False)
    content = child_xpath(navpoint, 'content')
    if content:
        content = content[0]
        href = content.get('src', None)
        if href:
            dest = container.href_to_name(href, base=ncx_name)
            frag = urllib.parse.urlparse(href).fragment or None
    return parent.add(text or None, dest or None, frag or None)


def process_ncx_node(container, node, toc_parent, ncx_name):
    for navpoint in node.xpath('./*[calibre:lower-case(local-name()) '
                               '= "navpoint"]'):
        child = add_from_navpoint(container, navpoint, toc_parent, ncx_name)
        if child is not None:
            process_ncx_node(container, navpoint, child, ncx_name)


def parse_ncx(container, ncx_name):
    root = container.parsed(ncx_name)
    toc_root = TOC()
    navmaps = root.xpath('//*[calibre:lower-case(local-name()) = "navmap"]')
    if navmaps:
        process_ncx_node(container, navmaps[0], toc_root, ncx_name)
    toc_root.lang = toc_root.uid = None
    for attr, val in root.attrib.items():
        if attr.endswith('lang'):
            toc_root.lang = str(val)
            break
    for uid in root.xpath('//*[calibre:lower-case(local-name()) = "meta" and '
                          '@name="dtb:uid"]/@content'):
        if uid:
            toc_root.uid = str(uid)
            break
    for pl in root.xpath('//*[calibre:lower-case(local-name()) = "pagelist"]'):
        for pt in pl.xpath('descendant::*[calibre:lower-case(local-name()) = '
                           '"pagetarget"]'):
            pagenum = pt.get('value')
            if pagenum:
                href = pt.xpath('descendant::*[calibre:lower-case(local-name()'
                                ') = "content"]/@src')
                if href:
                    dest = container.href_to_name(href[0], base=ncx_name)
                    frag = urllib.parse.urlparse(href[0]).fragment or None
                    toc_root.page_list.append({'dest': dest,
                                               'pagenum': pagenum,
                                               'frag': frag})
    return toc_root


def add_from_li(container, li, parent, nav_name):
    dest = frag = text = None
    for x in li.iterchildren(base.tag('xhtml', 'a'),
                             base.tag('xhtml', 'span')):
        text = (etree.tostring(x, method='text', encoding='unicode',
                               with_tail=False).strip() or
                ' '.join(x.xpath('descendant-or-self::*/@title')).strip())
        href = x.get('href')
        if href:
            dest = (nav_name if href.startswith('#') else
                    container.href_to_name(href, base=nav_name))
            frag = urllib.parse.urlparse(href).fragment or None
        break
    return parent.add(text or None, dest or None, frag or None)


def first_child(parent, tagname):
    try:
        return next(parent.iterchildren(tagname))
    except StopIteration:
        return None


def process_nav_node(container, node, toc_parent, nav_name):
    for li in node.iterchildren(base.tag('xhtml', 'li')):
        child = add_from_li(container, li, toc_parent, nav_name)
        ol = first_child(li, base.tag('xhtml', 'ol'))
        if child is not None and ol is not None:
            process_nav_node(container, ol, child, nav_name)


def parse_nav(container, nav_name):
    root = container.parsed(nav_name)
    toc_root = TOC()
    toc_root.lang = toc_root.uid = None
    xhtml = functools.partial(base.tag, 'xhtml')
    for nav in root.iterdescendants(base.tag('xhtml', 'nav')):
        if nav.get(base.tag('epub', 'type')) == 'toc':
            ol = first_child(nav, base.tag('xhtml', 'ol'))
            if ol is not None:
                process_nav_node(container, ol, toc_root, nav_name)
                for h in nav.iterchildren(*map(xhtml,
                                               'h1 h2 h3 h4 h5 h6'.split())):
                    text = etree.tostring(h, method='text', encoding='unicode',
                                          with_tail=False) or h.get('title')
                    if text:
                        toc_root.toc_title = text
                        break
                break
    return toc_root


def verify_toc_destinations(container, toc):
    anchor_map = {}
    anchor_xpath = base.XPath('//*/@id|//h:a/@name')
    for item in toc.iterdescendants():
        name = item.dest
        if not name:
            item.dest_exists = False
            item.dest_error = 'No file named %s exists' % name
            continue
        try:
            root = container.parsed(name)
        except KeyError:
            item.dest_exists = False
            item.dest_error = 'No file named %s exists' % name
            continue
        if not hasattr(root, 'xpath'):
            item.dest_exists = False
            item.dest_error = 'No HTML file named %s exists' % name
            continue
        if not item.frag:
            item.dest_exists = True
            continue
        if name not in anchor_map:
            anchor_map[name] = frozenset(anchor_xpath(root))
        item.dest_exists = item.frag in anchor_map[name]
        if not item.dest_exists:
            item.dest_error = ('The anchor %(a)s does not exist in file '
                               '%(f)s' % dict(a=item.frag, f=name))


def find_existing_ncx_toc(container):
    toc = container.opf_xpath('//opf:spine/@toc')
    if toc:
        toc = container.manifest_id_map.get(toc[0], None)
    if not toc:
        ncx = guess_type('a.ncx')
        toc = container.manifest_type_map.get(ncx, [None])[0]
    return toc or None


def find_existing_nav_toc(container):
    for name in container.manifest_items_with_property('nav'):
        return name


def get_x_toc(container, find_toc, parse_toc, verify_destinations=True):
    def empty_toc():
        ans = TOC()
        ans.lang = ans.uid = None
        return ans
    toc = find_toc(container)
    ans = (empty_toc() if toc is None or not container.has_name(toc) else
           parse_toc(container, toc))
    ans.toc_file_name = toc if toc and container.has_name(toc) else None
    if verify_destinations:
        verify_toc_destinations(container, ans)
    return ans


def get_toc(container, verify_destinations=True):
    ver = container.opf_version_parsed
    if ver.major < 3:
        return get_x_toc(container, find_existing_ncx_toc, parse_ncx,
                         verify_destinations=verify_destinations)
    else:
        ans = get_x_toc(container, find_existing_nav_toc, parse_nav,
                        verify_destinations=verify_destinations)
        if len(ans) == 0:
            ans = get_x_toc(container, find_existing_ncx_toc, parse_ncx,
                            verify_destinations=verify_destinations)
        return ans


def get_guide_landmarks(container):
    for ref in container.opf_xpath('./opf:guide/opf:reference'):
        href, title, rtype = ref.get('href'), ref.get('title'), ref.get('type')
        href, frag = href.partition('#')[::2]
        name = container.href_to_name(href, container.opf_name)
        if container.has_name(name):
            yield {'dest': name,
                   'frag': frag,
                   'title': title or '',
                   'type': rtype or ''}


def get_nav_landmarks(container):
    nav = find_existing_nav_toc(container)
    if nav and container.has_name(nav):
        root = container.parsed(nav)
        et = base('epub', 'type')
        for elem in root.iterdescendants(base.tag('xhtml', 'nav')):
            if elem.get(et) == 'landmarks':
                for li in elem.iterdescendants(base.tag('xhtml', 'li')):
                    for a in li.iterdescendants(base.tag('xhtml', 'a')):
                        href, rtype = a.get('href'), a.get(et)
                        if href:
                            title = etree.tostring(a, method='text',
                                                   encoding='unicode',
                                                   with_tail=False).strip()
                            href, frag = href.partition('#')[::2]
                            name = container.href_to_name(href, nav)
                            if container.has_name(name):
                                yield {'dest': name,
                                       'frag': frag,
                                       'title': title or '',
                                       'type': rtype or ''}
                            break


def get_landmarks(container):
    ver = container.opf_version_parsed
    if ver.major < 3:
        return list(get_guide_landmarks(container))
    ans = list(get_nav_landmarks(container))
    if len(ans) == 0:
        ans = list(get_guide_landmarks(container))
    return ans


def ensure_id(elem, all_ids):
    elem_id = elem.get('id')
    if elem_id:
        return False, elem_id
    if elem.tag == base.tag('xhtml', 'a'):
        anchor = elem.get('name', None)
        if anchor:
            elem.set('id', anchor)
            return False, anchor
    c = 0
    while True:
        c += 1
        q = 'toc_{}'.format(c)
        if q not in all_ids:
            elem.set('id', q)
            all_ids.add(q)
            break
    return True, elem.get('id')


def elem_to_toc_text(elem):
    text = base.xml2text(elem).strip()
    if not text:
        text = elem.get('title', '')
    if not text:
        text = elem.get('alt', '')
    text = re.sub(r'\s+', ' ', text.strip())
    text = text[:1000].strip()
    if not text:
        text = '(Untitled)'
    return text


def item_at_top(elem):
    try:
        body = base.XPath('//h:body')(elem.getroottree().getroot())[0]
    except (TypeError, IndexError, KeyError, AttributeError):
        return False
    tree = body.getroottree()
    path = tree.getpath(elem)
    for el in body.iterdescendants(etree.Element):
        epath = tree.getpath(el)
        if epath == path:
            break
        try:
            if el.tag.endswith('}img') or (el.text and el.text.strip()):
                return False
        except Exception:
            return False
        if not path.startswith(epath):
            # Only check tail of non-parent elements
            if el.tail and el.tail.strip():
                return False
    return True


def from_xpaths(container, xpaths):
    '''
    Generate a Table of Contents from a list of XPath expressions. Each
    expression in the list corresponds to a level of the generate ToC. For
    example: :code:`['//h:h1', '//h:h2', '//h:h3']` will generate a three level
    Table of Contents from the ``<h1>``, ``<h2>`` and ``<h3>`` tags.
    '''
    tocroot = TOC()
    xpaths = [base.XPath(xp) for xp in xpaths]

    # Find those levels that have no elements in all spine items
    maps = collections.OrderedDict()
    empty_levels = {i+1 for i, xp in enumerate(xpaths)}
    for spinepath in container.spine_items:
        name = container.abspath_to_name(spinepath)
        root = container.parsed(name)
        level_item_map = maps[name] = {i + 1: frozenset(xp(root))
                                       for i, xp in enumerate(xpaths)}
        for lvl, elems in level_item_map.items():
            if elems:
                empty_levels.discard(lvl)
    # Remove empty levels from all level_maps
    if empty_levels:
        for name, lmap in tuple(maps.items()):
            lmap = {lvl: items for lvl, items in lmap.items()
                    if lvl not in empty_levels}
            lmap = sorted(lmap.items(), key=operator.itemgetter(0))
            lmap = {i + 1: items for i, (l, items) in enumerate(lmap)}
            maps[name] = lmap

    node_level_map = {tocroot: 0}

    def parent_for_level(child_level):
        limit = child_level - 1

        def process_node(node):
            child = node.last_child
            if child is None:
                return node
            lvl = node_level_map[child]
            return (node if lvl > limit else
                    child if lvl == limit else process_node(child))

        return process_node(tocroot)

    for name, level_item_map in maps.items():
        root = container.parsed(name)
        item_level_map = {e: i for i, elems in level_item_map.items()
                          for e in elems}
        item_dirtied = False
        all_ids = set(root.xpath('//*/@id'))

        for item in root.iterdescendants(etree.Element):
            lvl = item_level_map.get(item, None)
            if lvl is None:
                continue
            text = elem_to_toc_text(item)
            parent = parent_for_level(lvl)
            if item_at_top(item):
                dirtied, elem_id = False, None
            else:
                dirtied, elem_id = ensure_id(item, all_ids)
            item_dirtied = dirtied or item_dirtied
            toc = parent.add(text, name, elem_id)
            node_level_map[toc] = lvl
            toc.dest_exists = True

        if item_dirtied:
            container.commit_item(name, keep_parsed=True)

    return tocroot


def from_links(container):
    '''
    Generate a Table of Contents from links in the book.
    '''
    toc = TOC()
    link_path = base.XPath('//h:a[@href]')
    seen_titles, seen_dests = set(), set()
    for name, is_linear in container.spine_names:
        root = container.parsed(name)
        for a in link_path(root):
            href = a.get('href')
            if not href or not href.strip():
                continue
            frag = None
            if href.startswith('#'):
                dest = name
                frag = href[1:]
            else:
                href, _, frag = href.partition('#')
                dest = container.href_to_name(href, base=name)
            frag = frag or None
            if (dest, frag) in seen_dests:
                continue
            seen_dests.add((dest, frag))
            text = elem_to_toc_text(a)
            if text in seen_titles:
                continue
            seen_titles.add(text)
            toc.add(text, dest, frag=frag)
    verify_toc_destinations(container, toc)
    for child in toc:
        if not child.dest_exists:
            toc.remove(child)
    return toc


def find_text(node):
    LIMIT = 200
    pat = re.compile(r'\s+')
    for child in node:
        if isinstance(child, etree._Element):
            text = base.xml2text(child).strip()
            text = pat.sub(' ', text)
            if len(text) < 1:
                continue
            if len(text) > LIMIT:
                # Look for less text in a child of this node, recursively
                ntext = find_text(child)
                return ntext or (text[:LIMIT] + '...')
            else:
                return text


def from_files(container):
    '''
    Generate a Table of Contents from files in the book.
    '''
    toc = TOC()
    for i, spinepath in enumerate(container.spine_items):
        name = container.abspath_to_name(spinepath)
        root = container.parsed(name)
        body = base.XPath('//h:body')(root)
        if not body:
            continue
        text = find_text(body[0])
        if not text:
            text = name.rpartition('/')[-1]
            if i == 0 and text.rpartition('.')[0].lower() in {'titlepage',
                                                              'cover'}:
                text = 'Cover'
        toc.add(text, name)
    return toc


def node_from_loc(root, locs, totals=None):
    node = root.xpath('//*[local-name()="body"]')[0]
    for i, loc in enumerate(locs):
        children = tuple(node.iterchildren(etree.Element))
        if totals is not None and totals[i] != len(children):
            raise MalformedMarkup()
        node = children[loc]
    return node


def add_id(container, name, loc, totals=None):
    root = container.parsed(name)
    try:
        node = node_from_loc(root, loc, totals=totals)
    except MalformedMarkup:
        # The webkit HTML parser and the container parser have yielded
        # different node counts, this can happen if the file is valid XML
        # but contains constructs like nested <p> tags. So force parse it
        # with the HTML 5 parser and try again.
        raw = container.raw_data(name)
        root = container.parse_xhtml(raw, fname=name, force_html5_parse=True)
        try:
            node = node_from_loc(root, loc, totals=totals)
        except MalformedMarkup:
            raise MalformedMarkup('The file %s has malformed markup. Try '
                                  'running the Fix HTML tool before '
                                  'editing.' % name)
        container.replace(name, root)

    if not node.get('id'):
        ensure_id(node, set(root.xpath('//*/@id')))
    container.commit_item(name, keep_parsed=True)
    return node.get('id')


def create_ncx(toc, to_href, btitle, lang, uid):
    lang = lang.replace('_', '-')
    ncx = etree.Element(base.tag('ncx', 'ncx'),
                        attrib={'version': '2005-1',
                                base.tag('xml', 'lang'): lang},
                        nsmap={None: const.NCX_NS})
    head = etree.SubElement(ncx, base.tag('ncx', 'head'))
    etree.SubElement(head, base.tag('ncx', 'meta'),
                     name='dtb:uid', content=str(uid))
    etree.SubElement(head, base.tag('ncx', 'meta'),
                     name='dtb:depth', content=str(toc.depth))
    generator = ''.join(['calibre (', constants_old.__version__, ')'])
    etree.SubElement(head, base.tag('ncx', 'meta'),
                     name='dtb:generator', content=generator)
    etree.SubElement(head, base.tag('ncx', 'meta'), name='dtb:totalPageCount',
                     content='0')
    etree.SubElement(head, base.tag('ncx', 'meta'), name='dtb:maxPageNumber',
                     content='0')
    title = etree.SubElement(ncx, base.tag('ncx', 'docTitle'))
    text = etree.SubElement(title, base.tag('ncx', 'text'))
    text.text = btitle
    navmap = etree.SubElement(ncx, base.tag('ncx', 'navMap'))
    spat = re.compile(r'\s+')

    play_order = collections.Counter()

    def process_node(xml_parent, toc_parent):
        for child in toc_parent:
            play_order['c'] += 1
            point = etree.SubElement(xml_parent, base.tag('ncx', 'navPoint'),
                                     id='num_%d' % play_order['c'],
                                     playOrder=str(play_order['c']))
            label = etree.SubElement(point, base.tag('ncx', 'navLabel'))
            title = child.title
            if title:
                title = spat.sub(' ', title)
            etree.SubElement(label, base.tag('ncx', 'text')).text = title
            if child.dest:
                href = to_href(child.dest)
                if child.frag:
                    href += '#'+child.frag
                etree.SubElement(point, base.tag('ncx', 'content'), src=href)
            process_node(point, child)

    process_node(navmap, toc)
    return ncx


def commit_ncx_toc(container, toc, lang=None, uid=None):
    tocname = find_existing_ncx_toc(container)
    if tocname is None:
        item = container.generate_item('toc.ncx', id_prefix='toc')
        tocname = container.href_to_name(item.get('href'),
                                         base=container.opf_name)
        ncx_id = item.get('id')
        [s.set('toc', ncx_id) for s in container.opf_xpath('//opf:spine')]
    if not lang:
        lang = get_lang()
        for _l in container.opf_xpath('//dc:language'):
            _l = canonicalize_lang(base.xml2text(_l).strip())
            if _l:
                lang = _l
                lang = lang_as_iso639_1(_l) or _l
                break
    lang = lang_as_iso639_1(lang) or lang
    if not uid:
        uid = base.uuid_id()
        eid = container.opf.get('unique-identifier', None)
        if eid:
            m = container.opf_xpath('//*[@id="%s"]' % eid)
            if m:
                uid = base.xml2text(m[0])

    title = 'Table of Contents'
    m = container.opf_xpath('//dc:title')
    if m:
        x = base.xml2text(m[0]).strip()
        title = x or title

    to_href = functools.partial(container.name_to_href, base=tocname)
    root = create_ncx(toc, to_href, title, lang, uid)
    container.replace(tocname, root)
    container.pretty_print.add(tocname)


def ensure_single_nav_of_type(root, ntype='toc'):
    et = base('epub', 'type')
    navs = [n for n in root.iterdescendants(base.tag('xhtml', 'nav'))
            if n.get(et) == ntype]
    for x in navs[1:]:
        extract(x)
    if navs:
        nav = navs[0]
        tail = nav.tail
        attrib = dict(nav.attrib)
        nav.clear()
        nav.attrib.update(attrib)
        nav.tail = tail
    else:
        nav = root.makeelement(base.tag('xhtml', 'nav'))
        first_child(root, base.tag('xhtml', 'body')).append(nav)
    nav.set(et, ntype)
    return nav


def commit_nav_toc(container, toc, lang=None, landmarks=None,
                   previous_nav=None):
    from ebook_converter.ebooks.oeb.polish.pretty import pretty_xml_tree
    tocname = find_existing_nav_toc(container)
    if previous_nav is not None:
        nav_name = container.href_to_name(previous_nav[0])
        if nav_name and container.exists(nav_name):
            tocname = nav_name
            container.apply_unique_properties(tocname, 'nav')
    if tocname is None:
        item = container.generate_item('nav.xhtml', id_prefix='nav')
        item.set('properties', 'nav')
        tocname = container.href_to_name(item.get('href'),
                                         base=container.opf_name)
        if previous_nav is not None:
            root = previous_nav[1]
        else:
            with open(pkg_resources.
                      resource_filename('ebook_converter',
                                        'data/new_nav.html')) as fobj:
                root = container.parse_xhtml(fobj.read())
        container.replace(tocname, root)
    else:
        root = container.parsed(tocname)
    if lang:
        lang = lang_as_iso639_1(lang) or lang
        root.set('lang', lang)
        root.set(base.tag('xml', 'lang'), lang)
    nav = ensure_single_nav_of_type(root, 'toc')
    if toc.toc_title:
        nav.append(nav.makeelement(base.tag('xhtml', 'h1')))
        nav[-1].text = toc.toc_title

    rnode = nav.makeelement(base.tag('xhtml', 'ol'))
    nav.append(rnode)
    to_href = functools.partial(container.name_to_href, base=tocname)
    spat = re.compile(r'\s+')

    def process_node(xml_parent, toc_parent):
        for child in toc_parent:
            li = xml_parent.makeelement(base.tag('xhtml', 'li'))
            xml_parent.append(li)
            title = child.title or ''
            title = spat.sub(' ', title).strip()
            a = li.makeelement(base.tag('xhtml', 'a'
                                        if child.dest else 'span'))
            a.text = title
            li.append(a)
            if child.dest:
                href = to_href(child.dest)
                if child.frag:
                    href += '#'+child.frag
                a.set('href', href)
            if len(child):
                ol = li.makeelement(base.tag('xhtml', 'ol'))
                li.append(ol)
                process_node(ol, child)
    process_node(rnode, toc)
    pretty_xml_tree(nav)

    def collapse_li(parent):
        for li in parent.iterdescendants(base.tag('xhtml', 'li')):
            if len(li) == 1:
                li.text = None
                li[0].tail = None
    collapse_li(nav)
    nav.tail = '\n'

    def create_li(ol, entry):
        li = ol.makeelement(base.tag('xhtml', 'li'))
        ol.append(li)
        a = li.makeelement(base.tag('xhtml', 'a'))
        li.append(a)
        href = container.name_to_href(entry['dest'], tocname)
        if entry['frag']:
            href += '#' + entry['frag']
        a.set('href', href)
        return a

    if landmarks is not None:
        nav = ensure_single_nav_of_type(root, 'landmarks')
        nav.set('hidden', '')
        ol = nav.makeelement(base.tag('xhtml', 'ol'))
        nav.append(ol)
        for entry in landmarks:
            if (entry['type'] and container.has_name(entry['dest']) and
                    container.mime_map[entry['dest']] in base.OEB_DOCS):
                a = create_li(ol, entry)
                a.set(base.tag('epub', 'type'), entry['type'])
                a.text = entry['title'] or None
        pretty_xml_tree(nav)
        collapse_li(nav)

    if toc.page_list:
        nav = ensure_single_nav_of_type(root, 'page-list')
        nav.set('hidden', '')
        ol = nav.makeelement(base.tag('xhtml', 'ol'))
        nav.append(ol)
        for entry in toc.page_list:
            if (container.has_name(entry['dest']) and
                    container.mime_map[entry['dest']] in base.OEB_DOCS):
                a = create_li(ol, entry)
                a.text = str(entry['pagenum'])
        pretty_xml_tree(nav)
        collapse_li(nav)
    container.replace(tocname, root)


def commit_toc(container, toc, lang=None, uid=None):
    commit_ncx_toc(container, toc, lang=lang, uid=uid)
    if container.opf_version_parsed.major > 2:
        commit_nav_toc(container, toc, lang=lang)


def remove_names_from_toc(container, names):
    changed = []
    names = frozenset(names)
    for find_toc, parse_toc, commit_toc in ((find_existing_ncx_toc,
                                             parse_ncx, commit_ncx_toc),
                                            (find_existing_nav_toc,
                                             parse_nav, commit_nav_toc)):
        toc = get_x_toc(container, find_toc, parse_toc,
                        verify_destinations=False)
        if len(toc) > 0:
            remove = []
            for node in toc.iterdescendants():
                if node.dest in names:
                    remove.append(node)
            if remove:
                for node in reversed(remove):
                    node.remove_from_parent()
                commit_toc(container, toc)
                changed.append(find_toc(container))
    return changed


def find_inline_toc(container):
    for name, linear in container.spine_names:
        if container.parsed(name).xpath('//*[local-name()="body" and @id='
                                        '"calibre_generated_inline_toc"]'):
            return name


def toc_to_html(toc, container, toc_name, title, lang=None):

    def process_node(html_parent, toc, level=1, indent='  ', style_level=2):
        li = html_parent.makeelement(base.tag('xhtml', 'li'))
        li.tail = '\n' + (indent * level)
        html_parent.append(li)
        name, frag = toc.dest, toc.frag
        href = '#'
        if name:
            href = container.name_to_href(name, toc_name)
            if frag:
                href += '#' + frag
        a = li.makeelement(base.tag('xhtml', 'a'), href=href)
        a.text = toc.title
        li.append(a)
        if len(toc) > 0:
            parent = li.makeelement(base.tag('xhtml', 'ul'))
            parent.set('class', 'level%d' % (style_level))
            li.append(parent)
            a.tail = '\n\n' + (indent*(level+2))
            parent.text = '\n'+(indent*(level+3))
            parent.tail = '\n\n' + (indent*(level+1))
            for child in toc:
                process_node(parent, child, level+3,
                             style_level=style_level + 1)
            parent[-1].tail = '\n' + (indent*(level+2))

    E = ElementMaker(namespace=const.XHTML_NS, nsmap={None: const.XHTML_NS})
    # TODO(gryf): revisit lack of css.
    css_f = pkg_resources.resource_filename('ebook_converter',
                                            'data/inline_toc_styles.css')
    html = E.html(E.head(E.title(title),
                         E.style(css_f, type='text/css')),
                  E.body(E.h2(title), E.ul(),
                         id="calibre_generated_inline_toc"))

    ul = html[1][1]
    ul.set('class', 'level1')
    for child in toc:
        process_node(ul, child)
    if lang:
        html.set('lang', lang)
    pretty_html_tree(container, html)
    return html


def create_inline_toc(container, title=None):
    """
    Create an inline (HTML) Table of Contents from an existing NCX Table of
    Contents.

    :param title: The title for this table of contents.
    """
    lang = get_book_language(container)
    default_title = 'Table of Contents'
    title = title or default_title
    toc = get_toc(container)
    if len(toc) == 0:
        return None
    toc_name = find_inline_toc(container)

    name = toc_name
    html = toc_to_html(toc, container, name, title, lang)
    raw = base.serialize(html, 'text/html')
    if name is None:
        name, c = 'toc.xhtml', 0
        while container.has_name(name):
            c += 1
            name = 'toc%d.xhtml' % c
        container.add_file(name, raw, spine_index=0)
    else:
        with container.open(name, 'wb') as f:
            f.write(raw)
    set_guide_item(container, 'toc', title, name,
                   frag='calibre_generated_inline_toc')
    return name
