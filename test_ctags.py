class CTagsTest(unittest.TestCase):
    # def test_all_search_strings_work(self):
    #     # os.chdir(os.path.dirname(__file__))
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

    def test_startswith(self):
        f = TagFile('tags', SYMBOL, MATCHES_STARTWITH)

        # print '\nFCUKT', len(list(f.get('co')))
        # print '\n'.join(list(f.get('co')))
        assert len(list(f.get('co'))) == 3

    def test_tags_files(self):
        tests = [ ( r"tags", SYMBOL ),
                  ( r"sorted_by_file_test_tags", FILENAME ),
                  # ( r"C:\python25\lib\tags_sorted_by_file", FILENAME )
                  ]

        fails = []

        for tags_file, column_index in tests:
            tag_file = TagFile(tags_file, column_index)

            with open(tags_file, 'r') as fh:
                latest =  ''
                lines  = []

                for l in fh:
                    symbol = l.split('\t')[column_index]

                    if symbol != latest:

                        if latest:
                            tags = list(tag_file.get(latest))
                            if not lines == tags:
                                fails.append( (tags_file, lines, tags) )

                            lines = []

                        latest = symbol

                    lines += [l]

        self.assertEquals(fails, [])

if __name__ == '__main__':
    unittest.main()
