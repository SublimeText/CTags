#!/usr/bin/env python

"""Unit tests for ctagsplugin.py"""

import os
import sys
import tempfile
import unittest
import codecs
import shutil

if sys.version_info >= (3, 0):
    from . import ctagsplugin
    from . import ctags
else:
    import ctagsplugin
    import ctags


class CTagsPluginTest(unittest.TestCase):

    """
    Helper functions
    """

    def make_tmp_directory(self, pwd=None):
        """Make a temporary directory to place files in

        :returns: Path to the temporary directory
        """
        tmp_dir = tempfile.mkdtemp(dir=pwd)
        return tmp_dir

    def build_python_file(self, pwd=None):
        """Build a simple Python "program" that ctags can use

        :returns: Path to a constructed, valid Java source file
        """
        path = ''

        # the file created here is locked while open, hence we can't delete
        # similarly, ctags appears to require an extension hence the suffix
        with tempfile.NamedTemporaryFile(
                delete=False, suffix='.py', dir=pwd) as temp:
            try:
                path = temp.name  # store name for later use
                temp.writelines([  # write a temp Python (duh!) "Hello, world"
                    'def my_definition():\n',
                    '\toutput = "Hello, world!"\n',
                    '\tprint(output)\n'])
            finally:
                temp.close()

        return path

    def build_java_file(self, pwd=None):
        """Build a slightly detailed Java "program" that ctags can use

        Build a slightly more detailed program that 'build_python_file' does,
        in order to test more advanced functionality of ctags.py, or ctags.exe

        :returns: Path to a constructed, valid Java source file
        """
        path = ''

        # the file created here is locked while open, hence we can't delete
        # similarly, ctags appears to require an extension hence the suffix
        with tempfile.NamedTemporaryFile(
                delete=False, suffix='.java', dir=pwd) as temp:
            try:
                path = temp.name  # store name for later use
                temp.writelines([  # write a temp Java "Hello, world"
                    'public class DemoClass {\n',
                    '\tpublic static void main(String args[]) {\n',
                    '\t\tSystem.out.println("Hello, World");\n',
                    '\n',
                    '\t\tDemoClass demo = new DemoClass();\n',
                    '\t\tSystem.out.printf("Sum %d\n", demo.getSum(5,6));\n',
                    '\t}\n',
                    '\n',
                    '\tprivate int getSum(int a, int b) {\n',
                    '\t\treturn (a + b);\n',
                    '\t}\n',
                    '}\n'])
            finally:
                temp.close()

        return path

    def remove_tmp_directory(self, path):
        """Remove a temporary directory made by ``make_tmp_directory``

        :param path: Path to directory

        :returns: True if directory deleted, else False
        """
        shutil.rmtree(path)

    def remove_tmp_files(self, paths):
        """Remove temporary files made by ``make_x_file``

        :param paths: Path to file

        :returns: True if file deleted, else False
        """
        for path in paths:
            os.remove(path)

    """
    Test functions
    """

    def test_find_tags_relative_to__find_tags_in_current_directory(self):
        TAG_FILE = 'example_tags'

        current_path = self.build_python_file()
        tag_file = ctags.build_ctags(path=current_path, tag_file=TAG_FILE)

        # should find tag file in current directory
        self.assertEquals(
            ctagsplugin.find_tags_relative_to(current_path, TAG_FILE),
            tag_file)

        # cleanup
        self.remove_tmp_files([current_path, tag_file])

    def test_find_tags_relative_to__find_tags_in_parent_directory(self):
        TAG_FILE = 'example_tags'

        parent_path = self.build_python_file()
        parent_tag_file = ctags.build_ctags(path=parent_path,
                                            tag_file=TAG_FILE)
        child_dir = self.make_tmp_directory()
        child_path = self.build_python_file(pwd=child_dir)

        # should find tag file in parent directory
        self.assertEquals(
            ctagsplugin.find_tags_relative_to(child_path, TAG_FILE),
            parent_tag_file)

        # cleanup
        self.remove_tmp_files([parent_path, parent_tag_file])
        self.remove_tmp_directory(child_dir)

    def test_find_top_folder__current_folder_open(self):
        # create temporary folders and files
        temp_dir = self.make_tmp_directory()
        temp_path = self.build_python_file(pwd=temp_dir)

        path = ctagsplugin.find_top_folder([temp_dir], temp_path)

        # directory of file should be top
        self.assertEquals(path, temp_dir)

        # cleanup
        self.remove_tmp_directory(temp_dir)

    def test_find_top_folder__single_ancestor_folder_open(self):
        # create temporary folders and files
        parent_dir = self.make_tmp_directory()
        child_dir = self.make_tmp_directory(pwd=parent_dir)
        temp_path = self.build_python_file(pwd=child_dir)

        path = ctagsplugin.find_top_folder([parent_dir], temp_path)

        # should return parent as the deepest common folder
        self.assertEquals(path, parent_dir)

        # cleanup
        self.remove_tmp_directory(parent_dir)

    def test_find_top_folder__single_sibling_folder_open(self):
        # create temporary folders and files
        parent_dir = self.make_tmp_directory()
        child_a_dir = self.make_tmp_directory(pwd=parent_dir)
        child_b_dir = self.make_tmp_directory(pwd=parent_dir)
        temp_path = self.build_python_file(pwd=child_b_dir)

        path = ctagsplugin.find_top_folder([child_a_dir], temp_path)

        # should return parent of the two child directories the deepest common
        # folder
        self.assertEquals(path, parent_dir)

        # cleanup
        self.remove_tmp_directory(parent_dir)

    def test_find_top_folder__single_child_folder_open(self):
        # create temporary folders and files
        parent_dir = self.make_tmp_directory()
        child_dir = self.make_tmp_directory(pwd=parent_dir)
        grandchild_dir = self.make_tmp_directory(pwd=child_dir)
        temp_path = self.build_python_file(pwd=child_dir)

        path = ctagsplugin.find_top_folder([grandchild_dir], temp_path)

        # should return child directory as the deepest common folder
        self.assertEquals(path, child_dir)

        # cleanup
        self.remove_tmp_directory(parent_dir)


if __name__ == '__main__':
    unittest.main()
