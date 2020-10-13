# from ebook_converter.util import img
from ebook_converter.constants_old import __appname__, __version__
from ebook_converter.gui2 import ensure_app, config, load_builtin_fonts, pixmap_to_data
from ebook_converter.utils.cleantext import clean_ascii_chars, clean_xml_chars
from ebook_converter.utils.config import JSONConfig

#def calibre_cover2(title, author_string='', series_string='', prefs=None, as_qimage=False, logo_path=None):
#    init_environment()
#    title, subtitle, footer = '<b>' + escape_formatting(title), '<i>' + escape_formatting(series_string), '<b>' + escape_formatting(author_string)
#    prefs = prefs or cprefs
#    prefs = {k:prefs.get(k) for k in cprefs.defaults}
#    scale = 800. / prefs['cover_height']
#    scale_cover(prefs, scale)
#    prefs = Prefs(**prefs)
#    img = QImage(prefs.cover_width, prefs.cover_height, QImage.Format_ARGB32)
#    img.fill(Qt.white)
#    # colors = to_theme('ffffff ffffff 000000 000000')
#    color_theme = theme_to_colors(fallback_colors)
#
#    class CalibeLogoStyle(Style):
#        NAME = GUI_NAME = 'calibre'
#
#        def __call__(self, painter, rect, color_theme, title_block, subtitle_block, footer_block):
#            top = title_block.position.y + 10
#            extra_spacing = subtitle_block.line_spacing // 2 if subtitle_block.line_spacing else title_block.line_spacing // 3
#            height = title_block.height + subtitle_block.height + extra_spacing + title_block.leading
#            top += height + 25
#            bottom = footer_block.position.y - 50
#            logo = QImage(logo_path or I('library.png'))
#            pwidth, pheight = rect.width(), bottom - top
#            scaled, width, height = img.fit_image(logo.width(), logo.height(), pwidth, pheight)
#            x, y = (pwidth - width) // 2, (pheight - height) // 2
#            rect = QRect(x, top + y, width, height)
#            painter.setRenderHint(QPainter.SmoothPixmapTransform)
#            painter.drawImage(rect, logo)
#            return self.ccolor1, self.ccolor1, self.ccolor1
#    style = CalibeLogoStyle(color_theme, prefs)
#    title_block, subtitle_block, footer_block = layout_text(
#        prefs, img, title, subtitle, footer, img.height() // 3, style)
#    p = QPainter(img)
#    rect = QRect(0, 0, img.width(), img.height())
#    colors = style(p, rect, color_theme, title_block, subtitle_block, footer_block)
#    for block, color in zip((title_block, subtitle_block, footer_block), colors):
#        p.setPen(color)
#        block.draw(p)
#    p.end()
#    img.setText('Generated cover', '%s %s' % (__appname__, __version__))
#    if as_qimage:
#        return img
#    return pixmap_to_data(img)


def message_image(text, width=500, height=400, font_size=20):
    # init_environment()
    # img = QImage(width, height, QImage.Format_ARGB32)
    # img.fill(Qt.white)
    # p = QPainter(img)
    # f = QFont()
    # f.setPixelSize(font_size)
    # p.setFont(f)
    # r = img.rect().adjusted(10, 10, -10, -10)
    # p.drawText(r, Qt.AlignJustify | Qt.AlignVCenter | Qt.TextWordWrap, text)
    # p.end()
    # return pixmap_to_data(img)
    # TODO(gryf): geenrate image using pillow.
    return None


def scale_cover(prefs, scale):
    for x in ('cover_width', 'cover_height', 'title_font_size', 'subtitle_font_size', 'footer_font_size'):
        prefs[x] = int(scale * prefs[x])


def generate_masthead(title, output_path=None, width=600, height=60, as_qimage=False, font_family=None):
    init_environment()
    font_family = font_family or cprefs['title_font_family'] or 'Liberation Serif'
    img = QImage(width, height, QImage.Format_ARGB32)
    img.fill(Qt.white)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    f = QFont(font_family)
    f.setStyleStrategy(QFont.PreferAntialias)
    f.setPixelSize((height * 3) // 4), f.setBold(True)
    p.setFont(f)
    p.drawText(img.rect(), Qt.AlignLeft | Qt.AlignVCenter, sanitize(title))
    p.end()
    if as_qimage:
        return img
    data = pixmap_to_data(img)
    if output_path is None:
        return data
    with open(output_path, 'wb') as f:
        f.write(data)
