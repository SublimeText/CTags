################################################################################
# coding: utf8
################################################################################

# Std Libs
from __future__ import with_statement

import re
import unittest
import os
import subprocess
import bisect
import mmap

from os.path import dirname

################################################################################

TAGS_RE = re.compile (

    '(?P<symbol>[^\t]+)\t'
    '(?P<filename>[^\t]+)\t'
    '(?P<ex_command>.*?);"\t'
    '(?P<type>[^\t\r\n]+)'
    '(?:\t(?P<fields>.*))?'
)

# Column indexes
SYMBOL = 0
FILENAME = 1

MATCHES_STARTWITH = 'starts_with'

PATH_ORDER = [
    'function', 'class', 'struct',
]

PATH_IGNORE_FIELDS = ( 'file', 'access', 'signature',
                       'language', 'line', 'inherits' )

TAG_PATH_SPLITTERS = ('/', '.', '::', ':')

################################################################################

def splits(string, *splitters):
    if splitters:
        split = string.split(splitters[0])
        for s in split:
            for c in splits(s, *splitters[1:]):
                yield c
    else:
        if string: yield string

################################################################################

def parse_tag_lines(lines, order_by='symbol', tag_class=None, filters=[]):
    tags_lookup = {}

    for l in lines:
        search_obj = TAGS_RE.search(l.decode('utf8'))
        if not search_obj:
            continue

        tag = post_process_tag(search_obj)
        if tag_class is not None: tag = tag_class(tag)

        skip = False
        for f in filters:
            for k, v in f.items():
                if re.match(v, tag[k]):
                    skip = True

        if skip: continue

        tags_lookup.setdefault(tag[order_by], []).append(tag)

    return tags_lookup

def unescape_ex(ex):
    return re.sub(r"\\(\$|/|\^|\\)", r'\1', ex)

def process_ex_cmd(ex):
    return ex if ex.isdigit() else unescape_ex(ex[2:-2])

def post_process_tag(search_obj):
    tag = search_obj.groupdict()

    fields = tag.get('fields')
    if fields:
        fields_dict = process_fields(fields)
        tag.update(fields_dict)
        tag['field_keys'] = sorted(fields_dict.keys())

    tag['ex_command'] =   process_ex_cmd(tag['ex_command'])

    create_tag_path(tag)

    return tag

def process_fields(fields):
    return dict(f.split(':', 1) for f in fields.split('\t'))

class Tag(dict):
    def __init__(self, *args, **kw):
        dict.__init__(self, *args, **kw)
        self.__dict__ = self

################################################################################

def parse_tag_file(tag_file):
    with open(tag_file) as tf:
        tags = parse_tag_lines(tf)

    return tags

################################################################################

def create_tag_path(tag):
    symbol     =  tag.get('symbol')
    field_keys =  tag.get('field_keys', [])[:]

    fields = []
    for i, field in enumerate(PATH_ORDER):
        if field in field_keys:
            fields.append(field)
            field_keys.pop(field_keys.index(field))

    fields.extend(field_keys)

    tag_path = ''
    for field in fields:
        if field not in PATH_IGNORE_FIELDS:
            tag_path += (tag.get(field) + '.')

    tag_path += symbol

    splitup = ([tag.get('filename')] +
               list(splits(tag_path, *TAG_PATH_SPLITTERS)))

    tag['tag_path'] = tuple(splitup)

################################################################################

def get_tag_class(tag):
    cls  = tag.get('function', '').split('.')[:1]
    return cls and cls[0] or tag.get('class') or tag.get('struct')

################################################################################

def resort_ctags(tag_file):
    keys = {}

    with open(tag_file) as fh:
        for l in fh:
            keys.setdefault(l.split('\t')[FILENAME], []).append(l)

    with open(tag_file + '_sorted_by_file', 'w') as fw:
        for k in sorted(keys):
            for line in keys[k]:
                split = line.split('\t')
                split[FILENAME] = split[FILENAME].lstrip('.\\')
                fw.write('\t'.join(split))

def build_ctags(cmd, tag_file, env=None):
    p = subprocess.Popen(cmd, cwd = dirname(tag_file), shell=1, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ret = p.wait()

    if ret: raise EnvironmentError((cmd, ret, p.stdout.read()))
    # Faster than ctags.exe again:
    resort_ctags(tag_file)

    return tag_file

def test_build_ctags__ctags_not_on_path():
    try:
        build_ctags(['ctags.exe -R'], r'C:\Users\nick\AppData\Roaming\Sublime Text 2\Packages\CTags\tags', env={})
    except Exception, e:
        print 'OK'
        print e
    else:
        raise "Should have died"
    # EnvironmentError: (['ctags.exe -R'], 1, '\'"ctags.exe -R"\' is not recognized as an internal or external command,\r\noperable program or batch file.\r\n')

def test_build_ctags__dodgy_command():
    try:
        build_ctags(['ctags', '--arsts'], r'C:\Users\nick\AppData\Roaming\Sublime Text 2\Packages\CTags\tags')
    except Exception, e:
        print 'OK'
        print e
    else:
        raise "Should have died"

################################################################################

class TagFile(object):
    def __init__(self, p, column, match_as=None):
        self.p = p
        self.column = column

        if isinstance(match_as, basestring):
            match_as = getattr(self, match_as)

        self.match_as = match_as or self.exact_matches

    def __getitem__(self, index):
        self.fh.seek(index)
        self.fh.readline()

        try:  return self.fh.readline().split('\t')[self.column]
        # Ask forgiveness not permission
        except IndexError:
            return ''

    def __len__(self):
        return os.stat(self.p).st_size

    def get(self, *tags):
        with open(self.p, 'r+') as fh:
            if tags:
                self.fh = mmap.mmap(fh.fileno(), 0)

                for tag in (t.encode() for t in tags):
                    b4 = bisect.bisect_left(self, tag)
                    fh.seek(b4)

                    for l in self.match_as(fh, tag):
                        yield l

                self.fh.close()
            else:
                for l in fh.readlines():
                    yield l

    def get_by_suffix(self, suffix):
        with open(self.p, 'r+') as fh:
            self.fh = mmap.mmap(fh.fileno(), 0)

            for l in fh:
                if l.split('\t')[self.column].endswith(suffix): yield l
                else: continue

            self.fh.close()


    def exact_matches(self, iterator, tag):
        for l in iterator:
            comp = cmp(l.split('\t')[self.column], tag)

            if    comp == -1:    continue
            elif  comp:          break

            yield l

    def starts_with(self, iterator, tag):
        for l in iterator:
            field = l.split('\t')[self.column]
            comp = cmp(field, tag)

            if comp == -1: continue

            if field.startswith(tag): yield l
            else: break

    @property
    def dir(self):
        return dirname(self.p)

    def tag_class(self):
        return type('Tag', (Tag,), dict(root_dir = self.dir))

    def get_tags_dict_by_suffix(self, suffix, **kw):
        filters = kw.get('filters', [])
        return parse_tag_lines( self.get_by_suffix(suffix),
                                tag_class=self.tag_class(), filters=filters)

    def get_tags_dict(self, *tags, **kw):
        filters = kw.get('filters', [])
        return parse_tag_lines( self.get(*tags),
                                tag_class=self.tag_class(), filters=filters)


################################################################################


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

################################################################################
# TAG FILE FORMAT

# When not running in etags mode, each entry in the tag file consists of a
# separate line, each looking like this in the most general case:

# tag_name<TAB>file_name<TAB>ex_cmd;"<TAB>extension_fields

# The fields and separators of these lines are specified as follows:

# 1.

#     tag name

# 2.

#     single tab character

# 3.

#     name of the file in which the object associated with the tag is located

# 4.

#     single tab character

# 5.

#     EX command used to locate the tag within the file; generally a search
#     pattern (either /pattern/ or ?pattern?) or line number (see −−excmd). Tag
#     file format 2 (see −−format) extends this EX command under certain
#     circumstances to include a set of extension fields (described below)
#     embedded in an EX comment immediately appended to the EX command, which
#     leaves it backward-compatible with original vi(1) implementations.

# A few special tags are written into the tag file for internal purposes. These
# tags are composed in such a way that they always sort to the top of the file.
# Therefore, the first two characters of these tags are used a magic number to
# detect a tag file for purposes of determining whether a valid tag file is
# being overwritten rather than a source file. Note that the name of each source
# file will be recorded in the tag file exactly as it appears on the command
# line.

# Therefore, if the path you specified on the command line was relative to the
# current directory, then it will be recorded in that same manner in the tag
# file. See, however, the −−tag−relative option for how this behavior can be
# modified.

# Extension fields are tab-separated key-value pairs appended to the end of the
# EX command as a comment, as described above. These key value pairs appear in
# the general form "key:value". Their presence in the lines of the tag file are
# controlled by the −−fields option. The possible keys and the meaning of their
# values are as follows:

# access

#     Indicates the visibility of this class member, where value is specific to
#     the language.

# file

#     Indicates that the tag has file-limited visibility. This key has no
#     corresponding value.

# kind

#     Indicates the type, or kind, of tag. Its value is either one of the
#     corresponding one-letter flags described under the various −−<LANG>−kinds
#     options above, or a full name. It is permitted (and is, in fact, the
#     default) for the key portion of this field to be omitted. The optional
#     behaviors are controlled with the −−fields option.

# implementation

# When present, this indicates a limited implementation (abstract vs. concrete)
# of a routine or class, where value is specific to the language ("virtual" or
# "pure virtual" for C++; "abstract" for Java).

# inherits

#     When present, value. is a comma-separated list of classes from which this
#     class is derived (i.e. inherits from).

# signature

#     When present, value is a language-dependent representation of the
#     signature of a routine. A routine signature in its complete form specifies
#     the return type of a routine and its formal argument list. This extension
#     field is presently supported only for C-based languages and does not
#     include the return type.

# In addition, information on the scope of the tag definition may be available,
# with the key portion equal to some language-dependent construct name and its
# value the name declared for that construct in the program. This scope entry
# indicates the scope in which the tag was found. For example, a tag generated
# for a C structure member would have a scope looking like "struct:myStruct".myStruct".

