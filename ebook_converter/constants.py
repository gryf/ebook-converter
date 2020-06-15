VERSION = '0.1.0'
CALIBRE_NS = 'http://calibre.kovidgoyal.net/2009/metadata'
DC09_NS = 'http://purl.org/metadata/dublin_core'
DC10_NS = 'http://purl.org/dc/elements/1.0/'
DC11_NS = 'http://purl.org/dc/elements/1.1/'
DCTERMS_NS = 'http://purl.org/dc/terms/'
EPUB_NS = 'http://www.idpf.org/2007/ops'
MATHML_NS = 'http://www.w3.org/1998/Math/MathML'
MBP_NS = 'http://www.mobipocket.com'
NCX_NS = 'http://www.daisy.org/z3986/2005/ncx/'
OEB_DOC_NS = 'http://openebook.org/namespaces/oeb-document/1.0/'
OPF1_NS = 'http://openebook.org/namespaces/oeb-package/1.0/'
OPF2_NS = 'http://www.idpf.org/2007/opf'
RE_NS = 'http://exslt.org/regular-expressions'
SVG_NS = 'http://www.w3.org/2000/svg'
XHTML_NS = 'http://www.w3.org/1999/xhtml'
XLINK_NS = 'http://www.w3.org/1999/xlink'
XMLNS_NS = 'http://www.w3.org/2000/xmlns/'
XML_NS = 'http://www.w3.org/XML/1998/namespace'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'

DC_NSES = {DC09_NS, DC10_NS, DC11_NS}
OPF_NAMESPACES = {'opf': OPF2_NS, 'dc': DC11_NS}
OPF_NSES = {OPF1_NS, OPF2_NS}

XHTML_BLOCK_TAGS = {'{%s}%s' % (XHTML_NS, x)
                    for x in ('address', 'article', 'aside', 'audio',
                              'blockquote', 'body', 'canvas', 'col',
                              'colgroup', 'dd', 'div', 'dl', 'dt', 'fieldset',
                              'figcaption', 'figure', 'footer', 'form', 'h1',
                              'h2', 'h3', 'h4', 'h5', 'h6', 'header',
                              'hgroup', 'hr', 'li', 'noscript', 'ol',
                              'output', 'p', 'pre', 'script', 'section',
                              'style', 'svg', 'table', 'tbody', 'td', 'tfoot',
                              'th', 'thead', 'tr', 'ul', 'video', 'img')}

OPF1_NSMAP = {'dc': DC11_NS,
              'oebpackage': OPF1_NS}
OPF2_NSMAP = {'calibre': CALIBRE_NS,
              'dc': DC11_NS,
              'dcterms': DCTERMS_NS,
              'opf': OPF2_NS,
              'xsi': XSI_NS}
XPNSMAP = {'calibre': CALIBRE_NS,
           'd09': DC09_NS,
           'd10': DC10_NS,
           'd11': DC11_NS,
           'dt': DCTERMS_NS,
           'epub': EPUB_NS,
           'h': XHTML_NS,
           'mathml': MATHML_NS,
           'mbp': MBP_NS,
           'ncx': NCX_NS,
           'o1': OPF1_NS,
           'o2': OPF2_NS,
           're': RE_NS,
           'svg': SVG_NS,
           'xl': XLINK_NS,
           'xsi': XSI_NS}
