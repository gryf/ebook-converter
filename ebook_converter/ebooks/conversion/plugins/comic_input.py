"""
Based on ideas from comiclrf created by FangornUK.
"""
import shutil, textwrap, codecs, os

from ebook_converter import constants as const
from ebook_converter.customize.conversion import InputFormatPlugin, OptionRecommendation
from ebook_converter.ptempfile import PersistentTemporaryDirectory
from ebook_converter.utils import directory


class ComicInput(InputFormatPlugin):

    name        = 'Comic Input'
    author      = 'Kovid Goyal'
    description = 'Optimize comic files (.cbz, .cbr, .cbc) for viewing on portable devices'
    file_types  = {'cbz', 'cbr', 'cbc'}
    is_image_collection = True
    commit_name = 'comic_input'
    core_usage = -1

    options = {
        OptionRecommendation(name='colors', recommended_value=0,
            help='Reduce the number of colors used in the image. This works '
                 'only if you choose the PNG output format. It is useful to '
                 'reduce file sizes. Set to zero to turn off. Maximum value '
                 'is 256. It is off by default.'),
        OptionRecommendation(name='dont_normalize', recommended_value=False,
            help='Disable normalize (improve contrast) color range '
                 'for pictures. Default: False'),
        OptionRecommendation(name='keep_aspect_ratio', recommended_value=False,
            help='Maintain picture aspect ratio. Default is to fill the '
                 'screen.'),
        OptionRecommendation(name='dont_sharpen', recommended_value=False,
            help='Disable sharpening.'),
        OptionRecommendation(name='disable_trim', recommended_value=False,
            help='Disable trimming of comic pages. For some comics, trimming '
                 'might remove content as well as borders.'),
        OptionRecommendation(name='landscape', recommended_value=False,
            help="Don't split landscape images into two portrait images"),
        OptionRecommendation(name='wide', recommended_value=False,
            help="Keep aspect ratio and scale image using screen height as "
                 "image width for viewing in landscape mode."),
        OptionRecommendation(name='right2left', recommended_value=False,
              help='Used for right-to-left publications like manga. '
                   'Causes landscape pages to be split into portrait pages '
                   'from right to left.'),
        OptionRecommendation(name='despeckle', recommended_value=False,
              help='Enable Despeckle. Reduces speckle noise. May greatly '
                   'increase processing time.'),
        OptionRecommendation(name='no_sort', recommended_value=False,
              help="Don't sort the files found in the comic "
                   "alphabetically by name. Instead use the order they were "
                   "added to the comic."),
        OptionRecommendation(name='output_format', choices=['png', 'jpg'],
                recommended_value='png',
                help='The format that images in the created e-book are '
                     'converted to. You can experiment to see which format '
                     'gives you optimal size and look on your device.'),
        OptionRecommendation(name='no_process', recommended_value=False,
              help="Apply no processing to the image"),
        OptionRecommendation(name='dont_grayscale', recommended_value=False,
            help='Do not convert the image to grayscale (black and white)'),
        OptionRecommendation(name='comic_image_size', recommended_value=None,
            help='Specify the image size as widthxheight pixels. Normally,'
                 ' an image size is automatically calculated from the output '
                 'profile, this option overrides it.'),
        OptionRecommendation(name='dont_add_comic_pages_to_toc', recommended_value=False,
            help='When converting a CBC do not add links to each page to'
                 ' the TOC. Note this only applies if the TOC has more than '
                 'one section'),
        }

    recommendations = {
        ('margin_left', 0, OptionRecommendation.HIGH),
        ('margin_top',  0, OptionRecommendation.HIGH),
        ('margin_right', 0, OptionRecommendation.HIGH),
        ('margin_bottom', 0, OptionRecommendation.HIGH),
        ('insert_blank_line', False, OptionRecommendation.HIGH),
        ('remove_paragraph_spacing',  False, OptionRecommendation.HIGH),
        ('change_justification', 'left', OptionRecommendation.HIGH),
        ('dont_split_on_pagebreaks', True, OptionRecommendation.HIGH),
        ('chapter', None, OptionRecommendation.HIGH),
        ('page_breaks_brefore', None, OptionRecommendation.HIGH),
        ('use_auto_toc', False, OptionRecommendation.HIGH),
        ('page_breaks_before', None, OptionRecommendation.HIGH),
        ('disable_font_rescaling', True, OptionRecommendation.HIGH),
        ('linearize_tables', False, OptionRecommendation.HIGH),
        }

    def get_comics_from_collection(self, stream):
        from ebook_converter.libunzip import extract as zipextract
        tdir = PersistentTemporaryDirectory('_comic_collection')
        zipextract(stream, tdir)
        comics = []
        with directory.CurrentDir(tdir):
            if not os.path.exists('comics.txt'):
                raise ValueError((
                    '%s is not a valid comic collection'
                    ' no comics.txt was found in the file')
                        %stream.name)
            with open('comics.txt', 'rb') as f:
                raw = f.read()
            if raw.startswith(codecs.BOM_UTF16_BE):
                raw = raw.decode('utf-16-be')[1:]
            elif raw.startswith(codecs.BOM_UTF16_LE):
                raw = raw.decode('utf-16-le')[1:]
            elif raw.startswith(codecs.BOM_UTF8):
                raw = raw.decode('utf-8')[1:]
            else:
                raw = raw.decode('utf-8')
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                fname, title = line.partition(':')[0], line.partition(':')[-1]
                fname = fname.replace('#', '_')
                fname = os.path.join(tdir, *fname.split('/'))
                if not title:
                    title = os.path.basename(fname).rpartition('.')[0]
                if os.access(fname, os.R_OK):
                    comics.append([title, fname])
        if not comics:
            raise ValueError('%s has no comics'%stream.name)
        return comics

    def get_pages(self, comic, tdir2):
        from ebook_converter.ebooks.comic.input import (extract_comic,  process_pages,
                find_pages)
        tdir  = extract_comic(comic)
        new_pages = find_pages(tdir, sort_on_mtime=self.opts.no_sort,
                verbose=self.opts.verbose)
        thumbnail = None
        if not new_pages:
            raise ValueError('Could not find any pages in the comic: %s'
                    %comic)
        if self.opts.no_process:
            n2 = []
            for i, page in enumerate(new_pages):
                n2.append(os.path.join(tdir2, '{} - {}' .format(i, os.path.basename(page))))
                shutil.copyfile(page, n2[-1])
            new_pages = n2
        else:
            new_pages, failures = process_pages(new_pages, self.opts,
                    self.report_progress, tdir2)
            if failures:
                self.log.warning('Could not process the following pages '
                '(run with --verbose to see why):')
                for f in failures:
                    self.log.warning('\t%s', f)
            if not new_pages:
                raise ValueError('Could not find any valid pages in comic: %s'
                        % comic)
            thumbnail = os.path.join(tdir2,
                    'thumbnail.'+self.opts.output_format.lower())
            if not os.access(thumbnail, os.R_OK):
                thumbnail = None
        return new_pages

    def get_images(self):
        return self._images

    def convert(self, stream, opts, file_ext, log, accelerators):
        from ebook_converter.ebooks.metadata import MetaInformation
        from ebook_converter.ebooks.metadata.opf2 import OPFCreator
        from ebook_converter.ebooks.metadata.toc import TOC

        self.opts, self.log= opts, log
        if file_ext == 'cbc':
            comics_ = self.get_comics_from_collection(stream)
        else:
            comics_ = [['Comic', os.path.abspath(stream.name)]]
        stream.close()
        comics = []
        for i, x in enumerate(comics_):
            title, fname = x
            cdir = 'comic_%d'%(i+1) if len(comics_) > 1 else '.'
            cdir = os.path.abspath(cdir)
            if not os.path.exists(cdir):
                os.makedirs(cdir)
            pages = self.get_pages(fname, cdir)
            if not pages:
                continue
            if self.for_viewer:
                comics.append((title, pages, [self.create_viewer_wrapper(pages)]))
            else:
                wrappers = self.create_wrappers(pages)
                comics.append((title, pages, wrappers))

        if not comics:
            raise ValueError('No comic pages found in %s'%stream.name)

        mi  = MetaInformation(os.path.basename(stream.name).rpartition('.')[0],
            ['Unknown'])
        opf = OPFCreator(os.getcwd(), mi)
        entries = []

        def href(x):
            if len(comics) == 1:
                return os.path.basename(x)
            return '/'.join(x.split(os.sep)[-2:])

        cover_href = None
        for comic in comics:
            pages, wrappers = comic[1:]
            page_entries = [(x, None) for x in map(href, pages)]
            entries += [(w, None) for w in map(href, wrappers)] + page_entries
            if cover_href is None and page_entries:
                cover_href = page_entries[0][0]
        opf.create_manifest(entries)
        spine = []
        for comic in comics:
            spine.extend(map(href, comic[2]))
        self._images = []
        for comic in comics:
            self._images.extend(comic[1])
        opf.create_spine(spine)
        if self.for_viewer and cover_href:
            opf.guide.set_cover(cover_href)
        toc = TOC()
        if len(comics) == 1:
            wrappers = comics[0][2]
            for i, x in enumerate(wrappers):
                toc.add_item(href(x), None, 'Page %d' % (i+1),
                        play_order=i)
        else:
            po = 0
            for comic in comics:
                po += 1
                wrappers = comic[2]
                stoc = toc.add_item(href(wrappers[0]),
                        None, comic[0], play_order=po)
                if not opts.dont_add_comic_pages_to_toc:
                    for i, x in enumerate(wrappers):
                        stoc.add_item(href(x), None,
                                'Page %d' % (i+1), play_order=po)
                        po += 1
        opf.set_toc(toc)
        with open('metadata.opf', 'wb') as m, open('toc.ncx', 'wb') as n:
            opf.render(m, n, 'toc.ncx')
        return os.path.abspath('metadata.opf')

    def create_wrappers(self, pages):
        wrappers = []
        WRAPPER = textwrap.dedent('''\
        <html xmlns="%s">
            <head>
                <meta charset="utf-8"/>
                <title>Page #%d</title>
                <style type="text/css">
                    @page { margin:0pt; padding: 0pt}
                    body { margin: 0pt; padding: 0pt}
                    div { text-align: center }
                </style>
            </head>
            <body>
                <div>
                    <img src="%s" alt="comic page #%d" />
                </div>
            </body>
        </html>
        ''')
        dir = os.path.dirname(pages[0])
        for i, page in enumerate(pages):
            wrapper = WRAPPER%(const.XHTML_NS, i+1, os.path.basename(page),
                               i+1)
            page = os.path.join(dir, 'page_%d.xhtml'%(i+1))
            with open(page, 'wb') as f:
                f.write(wrapper.encode('utf-8'))
            wrappers.append(page)
        return wrappers

    def create_viewer_wrapper(self, pages):
        def page(src):
            return '<img src="{}"></img>'.format(os.path.basename(src))

        pages = '\n'.join(map(page, pages))
        base = os.path.dirname(pages[0])
        wrapper = '''
        <html xmlns="%s">
            <head>
                <meta charset="utf-8"/>
                <style type="text/css">
                html, body, img { height: 100vh; display: block; margin: 0; padding: 0; border-width: 0; }
                img {
                    width: 100%%; height: 100%%;
                    object-fit: contain;
                    margin-left: auto; margin-right: auto;
                    max-width: 100vw; max-height: 100vh;
                    top: 50vh; transform: translateY(-50%%);
                    position: relative;
                    page-break-after: always;
                }
                </style>
            </head>
            <body>
            %s
            </body>
        </html>
        ''' % (const.XHTML_NS, pages)
        path = os.path.join(base, 'wrapper.xhtml')
        with open(path, 'wb') as f:
            f.write(wrapper.encode('utf-8'))
        return path
