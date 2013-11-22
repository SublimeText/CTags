#!/usr/bin/env python

"""Unit tests for ctags.py"""

import os
import tempfile
import unittest
import codecs

try:
    import sublime

    if int(sublime.version()) > 3000:
        from . import ctags
    else:
        import ctags
except:
    import ctags


class CTagsTest(unittest.TestCase):
    """
    Helper functions
    """

    def build_python_file(self):
        """Build a simple Python "program" that ctags can use.

        :Returns:
        Path to a constructed, valid Java source file
        """
        path = ''

        # the file created here is locked while open, hence we can't delete
        # similarly, ctags appears to require an extension hence the suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix='.py') as temp:
            try:
                path = temp.name  # store name for later use
                temp.writelines([
                    b'def my_definition():\n',
                    b'\toutput = "Hello, world!"\n',
                    b'\tprint(output)\n'])
            finally:
                temp.close()

        return path

    def build_java_file(self):
        """Build a slightly detailed Java "program" that ctags can use.

        Build a slightly more detailed program that 'build_python_file' does,
        in order to test more advanced functionality of ctags.py, or ctags.exe

        :Returns:
        Path to a constructed, valid Java source file
        """
        path = ''

        # the file created here is locked while open, hence we can't delete
        # similarly, ctags appears to require an extension hence the suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix='.java') as temp:
            try:
                path = temp.name  # store name for later use
                temp.writelines([
                    b'public class DemoClass {\n',
                    b'\tpublic static void main(String args[]) {\n',
                    b'\t\tSystem.out.println("Hello, World");\n',
                    b'\n',
                    b'\t\tDemoClass demo = new DemoClass();\n',
                    b'\t\tSystem.out.printf("Sum %d\n", demo.getSum(5,6));\n',
                    b'\t}\n',
                    b'\n',
                    b'\tprivate int getSum(int a, int b) {\n',
                    b'\t\treturn (a + b);\n',
                    b'\t}\n',
                    b'}\n'])
            finally:
                temp.close()

        return path

    """
    Test functions
    """

    def setUp(self):
        """Set up test environment.

        Ensures the ``ctags_not_on_path`` test is run first, and all other
        tests are skipped if this fails. If ctags is not installed, no test
        will pass
        """
        self.test_build_ctags__ctags_on_path()

    """build ctags"""

    def test_build_ctags__ctags_on_path(self):
        """Checks that ``ctags`` is in ``PATH``"""
        # build_ctags requires a real path, so we create a temporary file as a
        # cross-platform way to get the temp directory
        with tempfile.NamedTemporaryFile() as temp:
            try:
                ctags.build_ctags(path=temp.name)
            except EnvironmentError:
                self.fail('build_ctags() raised EnvironmentError. ctags not'
                          ' on path')

    def test_build_ctags__custom_command(self):
        """Checks for support of simple custom command to execute ctags"""
        # build_ctags requires a real path, so we create a temporary file as a
        # cross-platform way to get the temp directory
        with tempfile.NamedTemporaryFile() as temp:
            try:
                ctags.build_ctags(path=temp.name, cmd='ctags')
            except EnvironmentError:
                self.fail('build_ctags() raised EnvironmentError. ctags not'
                          ' on path')

    def test_build_ctags__invalid_custom_command(self):
        """Checks for failure for invalid custom command to execute ctags"""
        # build_ctags requires a real path, so we create a temporary file as a
        # cross-platform way to get the temp directory
        with tempfile.NamedTemporaryFile() as temp:
            with self.assertRaises(EnvironmentError):
                ctags.build_ctags(path=temp.name, cmd='ccttaaggss')

    def test_build_ctags__single_file(self):
        """Test execution of ctags using a single temporary file"""
        path = self.build_python_file()

        tag_file = ctags.build_ctags(path=path)

        with codecs.open(tag_file, encoding='utf-8') as output:
            try:
                content = output.readlines()
                filename = os.path.basename(path)
                self.assertEqual(
                    content[-1],
                    'my_definition\t{0}\t/^def my_definition()'
                    ':$/;"\tf\r\n'.format(filename))
            finally:
                output.close()
                os.remove(path)  # clean up
                os.remove(tag_file)

    def test_build_ctags__custom_tag_file(self):
        """Test execution of ctags using a custom tag file"""
        path = self.build_python_file()

        tag_file = ctags.build_ctags(path=path, tag_file='my_tag_file')

        with codecs.open(tag_file, encoding='utf-8') as output:
            try:
                content = output.readlines()
                filename = os.path.basename(path)
                self.assertEqual(
                    content[-1],
                    'my_definition\t{0}\t/^def my_definition()'
                    ':$/;"\tf\r\n'.format(filename))
            finally:
                output.close()
                os.remove(path)  # clean up
                os.remove(tag_file)

    """post_process_tag"""

    def test_post_process_tag__line_numbers(self):
        """Test ``post_process_tag`` with a line number ``excmd`` variable.

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

        self.assertEqual(result, expected_output)

    def test_post_process_tag__regex_no_fields(self):
        """Test ``post_process_tag`` with a regex ``excmd`` variable.

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

        self.assertEqual(result, expected_output)

    def test_post_process_tag__fields(self):
        """Test ``post_process_tag`` with a number of ``field`` variables.

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

        self.assertEqual(result, expected_output)


if __name__ == '__main__':
    unittest.main()
