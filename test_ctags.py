#!/usr/bin/env python

"""Unit tests for ctags.py"""

from ctags import TagFile, SYMBOL, MATCHES_STARTWITH, FILENAME, build_ctags

import unittest
import codecs

import ctags


class CTagsTest(unittest.TestCase):
    # def test_all_search_strings_work(self):
    #     os.chdir(os.path.dirname(__file__))
    #     tags = parse_tag_file('tags')

    #     failures = []

    #     for symbol, tag_list in tags.iteritems():
    #         for tag in (Tag(t) for t in tag_list):
    #             if not tag.ex_command.isdigit():
    #                 with open(tag.filename, 'r+') as fh:
    #                     mapped = mmap.mmap(fh.fileno(), 0)
    #                     if not mapped.find(tag.ex_command):
    #                         failures += [tag.ex_command]

    #     for f in failures:
    #         print f

    #     self.assertEqual(len(failures), 0, 'update tag files and try again')
    '''
    def test_startswith(self):
        f = TagFile('tags', SYMBOL, MATCHES_STARTWITH)
        assert len(list(f.get('co'))) == 3

    def test_tags_files(self):
        tests = [
            (r'tags', SYMBOL),
            (r'sorted_by_file_test_tags', FILENAME),
        ]

        fails = []

        for tags_file, column_index in tests:
            tag_file = TagFile(tags_file, column_index)

            with codecs.open(tags_file, 'r') as fh:
                latest = ''
                lines = []

                for l in fh:
                    symbol = l.split('\t')[column_index]
                    if symbol != latest:
                        if latest:
                            tags = list(tag_file.get(latest))
                            if not lines == tags:
                                fails.append((tags_file, lines, tags))
                            lines = []
                        latest = symbol
                    lines += [l]

        self.assertEquals(fails, [])

    def test_build_ctags__ctags_not_on_path():
        try:
            build_ctags(['ctags.exe -R'], r'C:\Users\nick\AppData\Roaming\Sublime Text 2\Packages\CTags\tags', env={})
        except Exception as e:
            print ('OK')
            print (e)
        else:
            raise "Should have died"

    def test_build_ctags__dodgy_command():
        try:
            build_ctags(['ctags', '--arsts'], r'C:\Users\nick\AppData\Roaming\Sublime Text 2\Packages\CTags\tags')
        except Exception as e:
            print ('OK')
            print (e)
        else:
            raise "Should have died"
    '''

    def test_post_process_tag__line_numbers(self):
        """Test ``post_process_tag`` with a line number ``excmd`` variable

        Test function with an sample tag from a Python file. This in turn tests
        the supporting functions.
        """
        tag = {
            'symbol': 'acme_function',
            'filename': '.\\a_folder\\a_script.py',
            'ex_command': '99',
            'type': 'f',
            'fields': None}

        expected_output = {
            'symbol': 'acme_function',
            'filename': '.\\a_folder\\a_script.py',
            'tag_path': ('.\\a_folder\\a_script.py', 'acme_function'),
            'ex_command': '99',
            'type': 'f',
            'fields': None}

        result = ctags.post_process_tag(tag)

        self.assertEquals(result, expected_output)

    def test_post_process_tag__regex_no_fields(self):
        """Test ``post_process_tag`` with a regex ``excmd`` variable

        Test function with an sample tag from a Python file. This in turn tests
        the supporting functions.
        """
        tag = {
            'symbol': 'acme_function',
            'filename': '.\\a_folder\\a_script.py',
            'ex_command': '/^def acme_function(tag):$/',
            'type': 'f',
            'fields': None}

        expected_output = {
            'symbol': 'acme_function',
            'filename': '.\\a_folder\\a_script.py',
            'tag_path': ('.\\a_folder\\a_script.py', 'acme_function'),
            'ex_command': 'def acme_function(tag):',
            'type': 'f',
            'fields': None}

        result = ctags.post_process_tag(tag)

        self.assertEquals(result, expected_output)

    def test_post_process_tag__fields(self):
        """Test ``post_process_tag`` with a number of ``field`` variables

        Test function with an sample tag from a Java file. This in turn tests
        the supporting functions.
        """
        tag = {
            'symbol': 'getSum',
            'filename': '.\\a_folder\\DemoClass.java',
            'ex_command': '/^\tprivate int getSum(int a, int b) {$/',
            'type': 'm',
            'fields': 'class:DemoClass\tfile:'}

        expected_output = {
            'symbol': 'getSum',
            'filename': '.\\a_folder\\DemoClass.java',
            'tag_path': ('.\\a_folder\\DemoClass.java', 'DemoClass', 'getSum'),
            'ex_command': '\tprivate int getSum(int a, int b) {',
            'type': 'm',
            'fields': 'class:DemoClass\tfile:',
            'field_keys': ['class', 'file'],
            'class': 'DemoClass',
            'file': ''}

        result = ctags.post_process_tag(tag)

        self.assertEquals(result, expected_output)


if __name__ == '__main__':
    unittest.main()
