#!/usr/bin/env python

"""Unit tests for ctagsplugin.py"""

import os
import tempfile
import unittest
import shutil

try:
    import sublime

    if int(sublime.version()) > 3000:
        from . import ctagsplugin
        from . import ctags
    else:
        import ctagsplugin
        import ctags
except:
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
        """Build a simple Python "program" that ctags can use.

        :Returns:
        Path to a constructed, valid Java source file
        """
        path = ''

        # the file created here is locked while open, hence we can't delete
        # similarly, ctags appears to require an extension hence the suffix
        with tempfile.NamedTemporaryFile(
                delete=False, suffix='.py', dir=pwd) as temp:
            try:
                path = temp.name  # store name for later use
                temp.writelines([
                    b'def my_definition():\n',
                    b'\toutput = "Hello, world!"\n',
                    b'\tprint(output)\n'])
            finally:
                temp.close()

        return path

    def build_java_file(self, pwd=None):
        """Build a slightly detailed Java "program" that ctags can use.

        Build a slightly more detailed program that 'build_python_file' does,
        in order to test more advanced functionality of ctags.py, or ctags.exe

        :Returns:
        Path to a constructed, valid Java source file
        """
        path = ''

        # the file created here is locked while open, hence we can't delete
        # similarly, ctags appears to require an extension hence the suffix
        with tempfile.NamedTemporaryFile(
                delete=False, suffix='.java', dir=pwd) as temp:
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

    """find_tags_relative_to"""

    def test_find_tags_relative_to__find_tags_in_current_directory(self):
        TAG_FILE = 'example_tags'

        current_path = self.build_python_file()
        tag_file = ctags.build_ctags(path=current_path, tag_file=TAG_FILE)

        # should find tag file in current directory
        self.assertEqual(
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
        self.assertEqual(
            ctagsplugin.find_tags_relative_to(child_path, TAG_FILE),
            parent_tag_file)

        # cleanup
        self.remove_tmp_files([parent_path, parent_tag_file])
        self.remove_tmp_directory(child_dir)

    """get_common_ancestor_folder"""

    def test_get_common_ancestor_folder__current_folder_open(self):
        parent_dir = '/c/users'

        temp = parent_dir + '/example.py'

        path = ctagsplugin.get_common_ancestor_folder(temp, [parent_dir])

        # should return parent of the two child directories the deepest common
        # folder
        self.assertEqual(path, parent_dir)

    def test_get_common_ancestor_folder__single_ancestor_folder_open(self):
        parent_dir = '/c/users'
        child_dir = parent_dir + '/child'

        temp = child_dir + '/example.py'

        path = ctagsplugin.get_common_ancestor_folder(temp, [parent_dir])

        # should return parent of the two child directories the deepest common
        # folder
        self.assertEqual(path, parent_dir)

    def test_get_common_ancestor_folder__single_sibling_folder_open(self):
        parent_dir = '/c/users'
        child_a_dir = parent_dir + '/child_a'
        child_b_dir = parent_dir + '/child_b'

        temp = child_b_dir + '/example.py'

        path = ctagsplugin.get_common_ancestor_folder(temp, [child_a_dir])

        # should return parent of the two child directories the deepest common
        # folder
        self.assertEqual(path, parent_dir)

    def test_get_common_ancestor_folder__single_child_folder_open(self):
        parent_dir = '/c/users'
        child_dir = parent_dir + '/child'
        grandchild_dir = child_dir + '/grandchild'

        temp = child_dir + '/example.py'

        # create temporary folders and files
        path = ctagsplugin.get_common_ancestor_folder(temp, [grandchild_dir])

        # should return child directory as the deepest common folder
        self.assertEqual(path, child_dir)

    """get_rel_path_to_source"""

    def test_get_rel_path_to_source__source_file_in_sibling_directory(self):
        temp = '/c/users/temporary_file'
        tag_file = '/c/users/tags'

        result = ctagsplugin.get_rel_path_to_source(
            temp, tag_file, multiple=False)

        relative_path = 'temporary_file'

        self.assertEqual([relative_path], result)

    def test_get_rel_path_to_source__source_file_in_child_directory(self):
        temp = '/c/users/folder/temporary_file'
        tag_file = '/c/users/tags'

        result = ctagsplugin.get_rel_path_to_source(
            temp, tag_file, multiple=False)

        # handle [windows, unix] paths
        relative_paths = ['folder\\temporary_file', 'folder/temporary_file']

        #self.assertEquals([relative_path], result)
        self.assertIn(result[0], relative_paths)


if __name__ == '__main__':
    unittest.main()
