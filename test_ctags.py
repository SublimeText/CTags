#!/usr/bin/env python

"""
Unit tests for 'ctags.py'.
"""

import os
import sys
import tempfile
import codecs
from subprocess import CalledProcessError

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import ctags

class CTagsTest(unittest.TestCase):
    #
    # Helper functions
    #
    def build_python_file(self):
        """
        Build a simple Python "program" that ctags can use.

        :returns: Path to a constructed, valid Python source file
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

    def build_python_file__extended(self):
        """
        Build a Python "program" demonstrating all common CTag types

        Build a Python program that demonstrates the following CTag types:
            - ``f`` - function definitions
            - ``v`` - variable definitions
            - ``c`` - classes
            - ``m`` - class, struct, and union members
            - ``i`` - import

        This is mainly intended to regression test for issue #209.

        :returns: Path to a constructed, valid Python source file
        """
        path = ''

        # the file created here is locked while open, hence we can't delete
        # similarly, ctags appears to require an extension hence the suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix='.py') as temp:
            try:
                path = temp.name  # store name for later use
                temp.writelines([
                    b'import os\n',
                    b'\n',
                    b'COLOR_RED = "\\c800080FF;"\t#red\n',
                    b'\n',
                    b'def my_function(first_name):\n',
                    b'\tprint("Hello {0}".format(first_name))\n',
                    b'\n',
                    b'class MyClass(object):\n',
                    b'\tlast_name = None\n',
                    b'\taddress = None\t# comment preceded by a tab\n',
                    b'\n',
                    b'\tdef my_method(self, last_name):\n',
                    b'\t\tself.last_name = last_name\n',
                    b'\t\tprint("Hello again, {0}".format(self.last_name))\n'])
            finally:
                temp.close()

        return path

    def build_java_file(self):
        """
        Build a slightly detailed Java "program" that ctags can use.

        Build a slightly more detailed program that 'build_python_file' does,
        in order to test more advanced functionality of ctags.py, or ctags.exe

        :returns: Path to a constructed, valid Java source file
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

    def build_c_file(self):
        """
        Build a simple C "program" that ctags can use.

        This is mainly intended to regression test for issue #213.

        :returns: Path to a constructed, valid C source file
        """
        path = ''

        # the file created here is locked while open, hence we can't delete
        # similarly, ctags appears to require an extension hence the suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix='.c') as temp:
            try:
                path = temp.name  # store name for later use
                temp.writelines([
                    b'#define foo(x,y) x+y\n'
                    b'#define foobar 1\n'
                    b'\n'
                    b'void bar()\n'
                    b'{\n'
                    b'\tfoo(10,2);'
                    b'\n'
                    b'#if foobar\n'
                    b'\tfoo(2,3); \n'
                    b'}\n'])
            finally:
                temp.close()

        return path

    #
    # Test functions
    #

    def setUp(self):
        """
        Set up test environment.

        Ensures the ``ctags_not_on_path`` test is run first, and all other
        tests are skipped if this fails. If ctags is not installed, no test
        will pass.
        """
        self.test_build_ctags__ctags_on_path()

    # build ctags

    def test_build_ctags__ctags_on_path(self):
        """
        Checks that ``ctags`` is in ``PATH``.
        """
        # build_ctags requires a real path, so we create a temporary file as a
        # cross-platform way to get the temp directory
        with tempfile.NamedTemporaryFile() as temp:
            try:
                ctags.build_ctags(path=temp.name)
            except EnvironmentError:
                self.fail('build_ctags() raised EnvironmentError. ctags not'
                          ' on path')

    def test_build_ctags__custom_command(self):
        """
        Checks for support of simple custom command to execute ctags.
        """
        # build_ctags requires a real path, so we create a temporary file as a
        # cross-platform way to get the temp directory
        with tempfile.NamedTemporaryFile() as temp:
            try:
                ctags.build_ctags(path=temp.name, cmd='ctags')
            except EnvironmentError:
                self.fail('build_ctags() raised EnvironmentError. ctags not'
                          ' on path')

    def test_build_ctags__invalid_custom_command(self):
        """
        Checks for failure for invalid custom command to execute ctags.
        """
        # build_ctags requires a real path, so we create a temporary file as a
        # cross-platform way to get the temp directory
        with tempfile.NamedTemporaryFile() as temp:
            with self.assertRaises(CalledProcessError):
                ctags.build_ctags(path=temp.name, cmd='ccttaaggss')

    def test_build_ctags__single_file(self):
        """
        Test execution of ctags using a single temporary file.
        """
        path = self.build_python_file()

        tag_file = ctags.build_ctags(path=path)

        with codecs.open(tag_file, encoding='utf-8') as output:
            try:
                content = output.readlines()
                filename = os.path.basename(path)
                self.assertEqual(
                    content[-1],
                    'my_definition\t{0}\t/^def my_definition()'
                    ':$/;"\tf{1}'.format(filename, os.linesep))
            finally:
                output.close()
                os.remove(path)  # clean up
                os.remove(tag_file)

    def test_build_ctags__custom_tag_file(self):
        """
        Test execution of ctags using a custom tag file.
        """
        path = self.build_python_file()

        tag_file = ctags.build_ctags(path=path, tag_file='my_tag_file')

        with codecs.open(tag_file, encoding='utf-8') as output:
            try:
                content = output.readlines()
                filename = os.path.basename(path)
                self.assertEqual(
                    content[-1],
                    'my_definition\t{0}\t/^def my_definition()'
                    ':$/;"\tf{1}'.format(filename, os.linesep))
            finally:
                output.close()
                os.remove(path)  # clean up
                os.remove(tag_file)

    def test_build_ctags__additional_options(self):
        """
        Test execution of ctags using additional ctags options.
        """
        path = self.build_python_file()

        tag_file = ctags.build_ctags(path=path, tag_file='my_tag_file',
                                     opts="--language-force=java")

        with codecs.open(tag_file, encoding='utf-8') as output:
            try:
                content = output.readlines()
                # there should be nothing in the file but headers (due to the
                # Java 'language-force' option on a Python file)
                self.assertEqual(
                    content[-1][:2],  # all comments start with '!_' - confirm
                    '!_')
            finally:
                output.close()
                os.remove(path)  # clean up
                os.remove(tag_file)

    # post_process_tag

    def test_post_process_tag__line_numbers(self):
        """
        Test ``post_process_tag`` with a line number ``excmd`` variable.

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
        """
        Test ``post_process_tag`` with a regex ``excmd`` variable.

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
        """
        Test ``post_process_tag`` with a number of ``field`` variables.

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

    # Tag class

    def test_parse_tag_lines__python(self):
        """
        Test ``parse_tag_lines`` with a sample Python file.
        """
        path = self.build_python_file__extended()

        tag_file = ctags.build_ctags(path=path, opts=['--python-kinds=-i'])

        with codecs.open(tag_file, encoding='utf-8') as output:
            try:
                content = output.readlines()
                filename = os.path.basename(path)
            except IOError:
                self.fail("Setup of files for test failed")
            finally:
                output.close()
                os.remove(path)  # clean up
                os.remove(tag_file)

        expected_outputs = {
            'MyClass': [{
                'symbol': 'MyClass',
                'filename': filename,
                'ex_command': 'class MyClass(object):',
                'tag_path': (filename, 'MyClass'),
                'type': 'c',
                'fields': None}],
            'address': [{
                'symbol': 'address',
                'filename': filename,
                'ex_command': '\taddress = None\t# comment preceded by a tab',
                'tag_path': (filename, 'MyClass', 'address'),
                'type': 'v',
                'fields': 'class:MyClass',
                'field_keys': ['class'],
                'class': 'MyClass'}],
            'last_name': [{
                'symbol': 'last_name',
                'filename': filename,
                'ex_command': '\tlast_name = None',
                'tag_path': (filename, 'MyClass', 'last_name'),
                'type': 'v',
                'fields': 'class:MyClass',
                'field_keys': ['class'],
                'class': 'MyClass'}],
            'my_function': [{
                'symbol': 'my_function',
                'filename': filename,
                'ex_command': 'def my_function(first_name):',
                'tag_path': (filename, 'my_function'),
                'type': 'f',
                'fields': None}],
            'my_method': [{
                'symbol': 'my_method',
                'filename': filename,
                'ex_command': '\tdef my_method(self, last_name):',
                'tag_path': (filename, 'MyClass', 'my_method'),
                'type': 'm',
                'fields': 'class:MyClass',
                'field_keys': ['class'],
                'class': 'MyClass'}],
            'COLOR_RED': [{
                'symbol': 'COLOR_RED',
                'filename': filename,
                'ex_command': 'COLOR_RED = "\\c800080FF;"\t#red',
                'tag_path': (filename, 'COLOR_RED'),
                'type': 'v',
                'fields': None}],
            }

        result = ctags.parse_tag_lines(content)

        for key in expected_outputs:
            self.assertEqual(result[key], expected_outputs[key])

        for key in result:  # don't forget - we might have missed something!
            self.assertEqual(expected_outputs[key], result[key])

    def test_parse_tag_lines__c(self):
        """
        Test ``parse_tag_lines`` with a sample C file.
        """
        path = self.build_c_file()

        tag_file = ctags.build_ctags(path=path)

        with codecs.open(tag_file, encoding='utf-8') as output:
            try:
                content = output.readlines()
                filename = os.path.basename(path)
            except IOError:
                self.fail("Setup of files for test failed")
            finally:
                output.close()
                os.remove(path)  # clean up
                os.remove(tag_file)

        expected_outputs = {
            'bar': [{
                'symbol': 'bar',
                'filename': filename,
                'ex_command': 'void bar()',
                'tag_path': (filename, 'bar'),
                'type': 'f',
                'fields': None}],
            'foo': [{
                'symbol': 'foo',
                'filename': filename,
                'ex_command': '1',
                'tag_path': (filename, 'foo'),
                'type': 'd',
                'fields': 'file:',
                'field_keys': ['file'],
                'file': ''}],
            'foobar': [{
                'symbol': 'foobar',
                'filename': filename,
                'ex_command': '2',
                'tag_path': (filename, 'foobar'),
                'type': 'd',
                'fields': 'file:',
                'field_keys': ['file'],
                'file': ''}]
            }

        result = ctags.parse_tag_lines(content)

        for key in expected_outputs:
            self.assertEqual(result[key], expected_outputs[key])

        for key in result:  # don't forget - we might have missed something!
            self.assertEqual(expected_outputs[key], result[key])

if __name__ == '__main__':
    unittest.main()
