import os
import tempfile
import unittest

from lxml import etree


# resolving of SYSTEM entities is turned off as entities can cause
# reads of local files, for example:
# <!DOCTYPE foo [ <!ENTITY passwd SYSTEM "file:///etc/passwd" >]>
fs = etree.fromstring


class Resolver(etree.Resolver):

    def resolve(self, url, id, context):
        return self.resolve_string('', context)


def create_parser(recover):
    parser = etree.XMLParser(recover=recover, no_network=True)
    parser.resolvers.add(Resolver())
    return parser


def safe_xml_fromstring(string_or_bytes, recover=True):
    return fs(string_or_bytes, parser=create_parser(recover))


def find_tests():

    class TestXMLParse(unittest.TestCase):

        def setUp(self):
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tf.write(b'external')
                self.temp_file = tf.name

        def tearDown(self):
            os.remove(self.temp_file)

        def test_safe_xml_fromstring(self):
            templ = '<!DOCTYPE foo [ <!ENTITY e {id} "{val}" > ]><r>&e;</r>'
            external = 'file:///' + self.temp_file.replace(os.sep, '/')
            self.assertEqual(etree.fromstring(templ.format(id='SYSTEM',
                                                           val=external)).text,
                             'external')
            for eid, val, expected in (
                ('', 'normal entity', 'normal entity'),
                ('', external, external),

                ('SYSTEM', external, None),
                ('SYSTEM', 'http://example.com', None),

                ('PUBLIC', external, None),
                ('PUBLIC', 'http://example.com', None),
            ):
                got = getattr(etree.fromstring(templ.format(id=eid, val=val)),
                              'text', None)
                self.assertEqual(got, expected)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestXMLParse)


if __name__ == '__main__':
    from ebook_converter.utils.run_tests import run_tests
    run_tests(find_tests)
