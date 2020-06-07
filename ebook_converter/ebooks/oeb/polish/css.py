import collections
import functools

from css_parser.css import CSSRule, CSSStyleDeclaration

from ebook_converter import force_unicode
from ebook_converter.css_selectors import parse, SelectorSyntaxError
from ebook_converter.ebooks.oeb import base
from ebook_converter.ebooks.oeb.polish import pretty
from ebook_converter.utils.icu import numeric_sort_key
from ebook_converter.css_selectors import Select, SelectorError


def filter_used_rules(rules, log, select):
    for rule in rules:
        used = False
        for selector in rule.selectorList:
            try:
                if select.has_matches(selector.selectorText):
                    used = True
                    break
            except SelectorError:
                # Cannot parse/execute this selector, be safe and assume it
                # matches something
                used = True
                break
        if not used:
            yield rule


def get_imported_sheets(name, container, sheets, recursion_level=10,
                        sheet=None):
    ans = set()
    sheet = sheet or sheets[name]
    for rule in sheet.cssRules.rulesOfType(CSSRule.IMPORT_RULE):
        if rule.href:
            iname = container.href_to_name(rule.href, name)
            if iname in sheets:
                ans.add(iname)
    if recursion_level > 0:
        for imported_sheet in tuple(ans):
            ans |= get_imported_sheets(imported_sheet, container, sheets,
                                       recursion_level=recursion_level-1)
    ans.discard(name)
    return ans


def merge_declarations(first, second):
    for prop in second.getProperties():
        first.setProperty(prop)


def merge_identical_selectors(sheet):
    ' Merge rules that have identical selectors '
    selector_map = collections.defaultdict(list)
    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
        selector_map[rule.selectorText].append(rule)
    remove = []
    for rule_group in selector_map.values():
        if len(rule_group) > 1:
            for i in range(1, len(rule_group)):
                merge_declarations(rule_group[0].style, rule_group[i].style)
                remove.append(rule_group[i])
    for rule in remove:
        sheet.cssRules.remove(rule)
    return len(remove)


def remove_unused_css(container, report=None, remove_unused_classes=False,
                      merge_rules=False):
    """
    Remove all unused CSS rules from the book. An unused CSS rule is one that
    does not match any actual content.

    :param report: An optional callable that takes a single argument. It is
                   called with information about the operations being
                   performed.
    :param remove_unused_classes: If True, class attributes in the HTML that
                                  do not match any CSS rules are also removed.
    :param merge_rules: If True, rules with identical selectors are merged.
    """
    report = report or (lambda x: x)

    def safe_parse(name):
        try:
            return container.parsed(name)
        except TypeError:
            pass

    sheets = {name: safe_parse(name) for name, mt in container.mime_map.items()
              if mt in base.OEB_STYLES and safe_parse(name) is not None}
    num_merged = 0
    if merge_rules:
        for name, sheet in sheets.items():
            num = merge_identical_selectors(sheet)
            if num:
                container.dirty(name)
                num_merged += num
    import_map = {name: get_imported_sheets(name, container, sheets)
                  for name in sheets}
    if remove_unused_classes:
        class_map = {name: {x.lower() for x in
                            classes_in_rule_list(sheet.cssRules)}
                     for name, sheet in sheets.items()}
    style_rules = {name: tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE))
                   for name, sheet in sheets.items()}

    num_of_removed_rules = num_of_removed_classes = 0

    for name, mt in container.mime_map.items():
        if mt not in base.OEB_DOCS:
            continue
        root = container.parsed(name)
        select = Select(root, ignore_inappropriate_pseudo_classes=True)
        used_classes = set()
        for style in root.xpath('//*[local-name()="style"]'):
            if style.get('type', 'text/css') == 'text/css' and style.text:
                sheet = container.parse_css(style.text)
                if merge_rules:
                    num = merge_identical_selectors(sheet)
                    if num:
                        num_merged += num
                        container.dirty(name)
                if remove_unused_classes:
                    used_classes |= {x.lower() for x in
                                     classes_in_rule_list(sheet.cssRules)}
                imports = get_imported_sheets(name, container, sheets,
                                              sheet=sheet)
                for imported_sheet in imports:
                    style_rules[imported_sheet] = tuple(filter_used_rules(
                        style_rules[imported_sheet], container.log, select))
                    if remove_unused_classes:
                        used_classes |= class_map[imported_sheet]
                rules = tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE))
                unused_rules = tuple(filter_used_rules(rules, container.log,
                                                       select))
                if unused_rules:
                    num_of_removed_rules += len(unused_rules)
                    [sheet.cssRules.remove(r) for r in unused_rules]
                    style.text = force_unicode(sheet.cssText, 'utf-8')
                    pretty.pretty_script_or_style(container, style)
                    container.dirty(name)

        for link in root.xpath('//*[local-name()="link" and @href]'):
            sname = container.href_to_name(link.get('href'), name)
            if sname not in sheets:
                continue
            style_rules[sname] = tuple(filter_used_rules(style_rules[sname],
                                                         container.log,
                                                         select))
            if remove_unused_classes:
                used_classes |= class_map[sname]

            for iname in import_map[sname]:
                style_rules[iname] = tuple(
                    filter_used_rules(style_rules[iname], container.log,
                                      select))
                if remove_unused_classes:
                    used_classes |= class_map[iname]

        if remove_unused_classes:
            for elem in root.xpath('//*[@class]'):
                original_classes, classes = elem.get('class', '').split(), []
                for x in original_classes:
                    if x.lower() in used_classes:
                        classes.append(x)
                if len(classes) != len(original_classes):
                    if classes:
                        elem.set('class', ' '.join(classes))
                    else:
                        del elem.attrib['class']
                    num_of_removed_classes += (len(original_classes) -
                                               len(classes))
                    container.dirty(name)

    for name, sheet in sheets.items():
        unused_rules = style_rules[name]
        if unused_rules:
            num_of_removed_rules += len(unused_rules)
            [sheet.cssRules.remove(r) for r in unused_rules]
            container.dirty(name)

    num_changes = num_of_removed_rules + num_merged + num_of_removed_classes
    if num_changes > 0:
        if num_of_removed_rules > 0:
            report('Removed {} unused CSS style '
                   'rules'.format(num_of_removed_rules))
        if num_of_removed_classes > 0:
            report('Removed {} unused classes from the HTML'
                   .format(num_of_removed_classes))
        if num_merged > 0:
            report('Merged {} CSS style rules'.format(num_merged))
    if num_of_removed_rules == 0:
        report('No unused CSS style rules found')
    if remove_unused_classes and num_of_removed_classes == 0:
        report('No unused class attributes found')
    if merge_rules and num_merged == 0:
        report('No style rules that could be merged found')
    return num_changes > 0


def filter_declaration(style, properties=()):
    changed = False
    for prop in properties:
        if style.removeProperty(prop) != '':
            changed = True
    all_props = set(style.keys())
    for prop in style.getProperties():
        n = base.normalize_css.normalizers.get(prop.name, None)
        if n is not None:
            normalized = n(prop.name, prop.propertyValue)
            removed = properties.intersection(set(normalized))
            if removed:
                changed = True
                style.removeProperty(prop.name)
                for prop in set(normalized) - removed - all_props:
                    style.setProperty(prop, normalized[prop])
    return changed


def filter_sheet(sheet, properties=()):
    from css_parser.css import CSSRule
    changed = False
    remove = []
    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
        if filter_declaration(rule.style, properties):
            changed = True
            if rule.style.length == 0:
                remove.append(rule)
    for rule in remove:
        sheet.cssRules.remove(rule)
    return changed


def transform_inline_styles(container, name, transform_sheet, transform_style):
    root = container.parsed(name)
    changed = False
    for style in root.xpath('//*[local-name()="style"]'):
        if style.text and (style.get('type') or
                           'text/css').lower() == 'text/css':
            sheet = container.parse_css(style.text)
            if transform_sheet(sheet):
                changed = True
                style.text = force_unicode(sheet.cssText, 'utf-8')
                pretty.pretty_script_or_style(container, style)
    for elem in root.xpath('//*[@style]'):
        text = elem.get('style', None)
        if text:
            style = container.parse_css(text, is_declaration=True)
            if transform_style(style):
                changed = True
                if style.length == 0:
                    del elem.attrib['style']
                else:
                    elem.set('style',
                             force_unicode(style.getCssText(separator=' '),
                                           'utf-8'))
    return changed


def transform_css(container, transform_sheet=None, transform_style=None,
                  names=()):
    if not names:
        types = base.OEB_STYLES | base.OEB_DOCS
        names = []
        for name, mt in container.mime_map.items():
            if mt in types:
                names.append(name)

    doc_changed = False

    for name in names:
        mt = container.mime_map[name]
        if mt in base.OEB_STYLES:
            sheet = container.parsed(name)
            if transform_sheet(sheet):
                container.dirty(name)
                doc_changed = True
        elif mt in base.OEB_DOCS:
            if transform_inline_styles(container, name, transform_sheet,
                                       transform_style):
                container.dirty(name)
                doc_changed = True

    return doc_changed


def filter_css(container, properties, names=()):
    """
    Remove the specified CSS properties from all CSS rules in the book.

    :param properties: Set of properties to remove. For example:
                       :code:`{'font-family', 'color'}`.
    :param names: The files from which to remove the properties. Defaults to
                  all HTML and CSS files in the book.
    """
    properties = base.normalize_css.normalize_filter_css(properties)
    return transform_css(container,
                         transform_sheet=functools.partial(
                            filter_sheet, properties=properties),
                         transform_style=functools.partial(
                            filter_declaration, properties=properties),
                         names=names)


def _classes_in_selector(selector, classes):
    for attr in ('selector', 'subselector', 'parsed_tree'):
        s = getattr(selector, attr, None)
        if s is not None:
            _classes_in_selector(s, classes)
    cn = getattr(selector, 'class_name', None)
    if cn is not None:
        classes.add(cn)


def classes_in_selector(text):
    classes = set()
    try:
        for selector in parse(text):
            _classes_in_selector(selector, classes)
    except SelectorSyntaxError:
        pass
    return classes


def classes_in_rule_list(css_rules):
    classes = set()
    for rule in css_rules:
        if rule.type == rule.STYLE_RULE:
            classes |= classes_in_selector(rule.selectorText)
        elif hasattr(rule, 'cssRules'):
            classes |= classes_in_rule_list(rule.cssRules)
    return classes


def iter_declarations(sheet_or_rule):
    if hasattr(sheet_or_rule, 'cssRules'):
        for rule in sheet_or_rule.cssRules:
            for x in iter_declarations(rule):
                yield x
    elif hasattr(sheet_or_rule, 'style'):
        yield sheet_or_rule.style
    elif isinstance(sheet_or_rule, CSSStyleDeclaration):
        yield sheet_or_rule


def remove_property_value(prop, predicate):
    ''' Remove the Values that match the predicate from this property. If all
    values of the property would be removed, the property is removed from its
    parent instead. Note that this means the property must have a parent (a
    CSSStyleDeclaration). '''
    removed_vals = list(filter(predicate, prop.propertyValue))
    if len(removed_vals) == len(prop.propertyValue):
        prop.parent.removeProperty(prop.name)
    else:
        x = base.css_text(prop.propertyValue)
        for v in removed_vals:
            x = x.replace(base.css_text(v), '').strip()
        prop.propertyValue.cssText = x
    return bool(removed_vals)


RULE_PRIORITIES = {t: i for i, t in enumerate((CSSRule.COMMENT,
                                               CSSRule.CHARSET_RULE,
                                               CSSRule.IMPORT_RULE,
                                               CSSRule.NAMESPACE_RULE))}


def sort_sheet(container, sheet_or_text):
    """
    Sort the rules in a stylesheet. Note that in the general case this can
    change the effective styles, but for most common sheets, it should be
    safe.
    """
    if isinstance(sheet_or_text, str):
        sheet = container.parse_css(sheet_or_text)
    else:
        sheet = sheet_or_text

    def text_sort_key(x):
        return numeric_sort_key(str(x or ''))

    def selector_sort_key(x):
        return (x.specificity, text_sort_key(x.selectorText))

    def rule_sort_key(rule):
        primary = RULE_PRIORITIES.get(rule.type, len(RULE_PRIORITIES))
        secondary = text_sort_key(getattr(rule, 'atkeyword', '') or '')
        tertiary = None
        if rule.type == CSSRule.STYLE_RULE:
            primary += 1
            selectors = sorted(rule.selectorList, key=selector_sort_key)
            tertiary = selector_sort_key(selectors[0])
            rule.selectorText = ', '.join(s.selectorText for s in selectors)
        elif rule.type == CSSRule.FONT_FACE_RULE:
            try:
                tertiary = text_sort_key(rule.style.getPropertyValue('font-'
                                                                     'family'))
            except Exception:
                pass

        return primary, secondary, tertiary
    sheet.cssRules.sort(key=rule_sort_key)
    return sheet


def add_stylesheet_links(container, name, text):
    root = container.parse_xhtml(text, name)
    head = root.xpath('//*[local-name() = "head"]')
    if not head:
        return
    head = head[0]
    sheets = tuple(container.manifest_items_of_type(lambda mt:
                                                    mt in base.OEB_STYLES))
    if not sheets:
        return
    for sname in sheets:
        link = head.makeelement(base.tag('xhtml', 'link'), type='text/css',
                                rel='stylesheet',
                                href=container.name_to_href(sname, name))
        head.append(link)
    pretty.pretty_xml_tree(head)
    return pretty.serialize(root, 'text/html')
