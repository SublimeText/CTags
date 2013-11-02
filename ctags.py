#!/usr/bin/env python

"""A ctags wrapper, parser and sorter"""

import codecs
import re
import os
import subprocess
import bisect
import mmap

"""
Contants
"""

TAGS_RE = re.compile(
    '(?P<symbol>[^\t]+)\t'
    '(?P<filename>[^\t]+)\t'
    '(?P<ex_command>.*?);"\t'
    '(?P<type>[^\t\r\n]+)'
    '(?:\t(?P<fields>.*))?'
)

# column indexes
SYMBOL = 0
FILENAME = 1

MATCHES_STARTWITH = 'starts_with'

PATH_ORDER = [
    'function', 'class', 'struct',
]

PATH_IGNORE_FIELDS = ('file', 'access', 'signature',
                      'language', 'line', 'inherits')

TAG_PATH_SPLITTERS = ('/', '.', '::', ':')


"""
Functions
"""

"""Helper functions"""


def cmp(a, b):
    """Compare two strings, and return a numerical value of comparison"""
    return (str(a) > str(b)) - (str(a) < str(b))


def splits(string, *splitters):
    """Split a string on a number of splitters"""
    if splitters:
        split = string.split(splitters[0])
        for s in split:
            for c in splits(s, *splitters[1:]):
                yield c
    else:
        if string:
            yield string

"""Tag processing functions"""


def parse_tag_lines(lines, order_by='symbol', tag_class=None, filters=[]):
    """Parse and sort a list of tags.

    Parse and sort a list of tags one by using a combination of regexen and
    Python functions. The end result is a dictionary containing all 'tags' or
    entries found in the list of tags, sorted and filtered in a manner
    specified by the user.

    :Parameters:
        - `lines`: List of tag lines from a tagfile
        - `order_by`: Element by which the result should be sorted
        - `tag_class`: A Class to wrap around the resulting dictionary
        - `filters`: Filters to apply to resulting dictionary

    :Returns:
        A tag object or dictionary containing a sorted, filtered version of
        the original input tag lines
    """
    tags_lookup = {}

    for line in lines:
        skip = False
        search_obj = TAGS_RE.search(line)

        if not search_obj:
            continue

        tag = search_obj.groupdict()  # convert regex search result to dict

        tag = post_process_tag(search_obj)

        if tag_class is not None:  # if 'casting' to a class
            tag = tag_class(tag)

        # apply filters, filtering out any matching entries
        for f in filters:
            for k, v in list(f.items()):
                if re.match(v, tag[k]):
                    skip = True

        if skip:  # if a filter was matched, ignore line (filter out)
            continue

        tags_lookup.setdefault(tag[order_by], []).append(tag)

    return tags_lookup


def post_process_tag(tag):
    """Process 'EX Command'-related elements of a tag.

    Process all 'EX Command'-related elements. The 'Ex Command' element has
    previously been split into the 'fields', 'type' and 'ex_command' elements.
    Break these down further as seen below::

        =========== = ============= =========================================
        original    → new           meaning/example
        =========== = ============= =========================================
        symbol      → symbol        symbol name (i.e. class, variable)
        filename    → filename      file containing symbol
        .           → tag_path      tuple of (filename, [class], symbol)
        ex_command  → ex_command    line number or regex used to find symbol
        type        → type          type of symbol (i.e. class, method)
        fields      → fields        string of fields
        .           → [field_keys]  list of parsed field keys
        .           → [field_one]   parsed field element one
        .           → [...]         additional parsed field element
        =========== = ============= =========================================

    Example::

        =========== = ============= =========================================
        original    → new           example
        =========== = ============= =========================================
        symbol      → symbol        'getSum'
        filename    → filename      'DemoClass.java'
        .           → tag_path      ('DemoClass.java', 'DemoClass', 'getSum')
        ex_command  → ex_command    '\tprivate int getSum(int a, int b) {'
        type        → type          'm'
        fields      → fields        'class:DemoClass\tfile:'
        .           → field_keys    ['class', 'file']
        .           → class         'DemoClass'
        .           → file          ''
        =========== = ============= =========================================

    :Parameters:
        - `tag`: A dict containing the unprocessed tag

    :Returns:
        A dict containing the processed tag
    """
    fields = tag.get('fields')

    if fields:
        fields_dict = process_fields(fields)
        tag.update(fields_dict)
        tag['field_keys'] = sorted(fields_dict.keys())

    tag['ex_command'] = process_ex_cmd(tag['ex_command'])

    create_tag_path(tag)

    return tag


def unescape_ex(ex):
    return re.sub(r"\\(\$|/|\^|\\)", r'\1', ex)


def process_ex_cmd(ex):
    return ex if ex.isdigit() else unescape_ex(ex[2:-2])


def process_fields(fields):
    return dict(f.split(':', 1) for f in fields.split('\t'))


def create_tag_path(tag):
    symbol = tag.get('symbol')
    field_keys = tag.get('field_keys', [])[:]

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

"""Tag building/sorting functions"""


def build_ctags(cmd, tag_file, env=None):
    p = subprocess.Popen(cmd, cwd=os.path.dirname(tag_file), shell=True,
                         env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    ret = p.wait()

    if ret:
        raise EnvironmentError((cmd, ret, p.stdout.read()))

    resort_ctags(tag_file)

    return tag_file


def resort_ctags(tag_file):
    keys = {}

    with codecs.open(tag_file, encoding='utf-8') as fh:
        for line in fh:
            keys.setdefault(line.split('\t')[FILENAME], []).append(line)

    with codecs.open(tag_file+'_sorted_by_file', 'w', encoding='utf-8') as fw:
        for k in sorted(keys):
            for line in keys[k]:
                split = line.split('\t')
                split[FILENAME] = split[FILENAME].lstrip('.\\')
                fw.write('\t'.join(split))


"""Models"""


class Tag(dict):
    """Model an individual tag entry"""
    def __init__(self, *args, **kw):
        """Initialise Tag object"""
        dict.__init__(self, *args, **kw)
        self.__dict__ = self


class TagFile(object):
    """Model a tag file.

    This doesn't actually hold a entire tag file, due in part to the sheer
    size of some tag files (> 100 MB files are possible). Instead, it acts
    as a 'wrapper' of sorts around a file, providing functionality like
    searching for a retrieving tags, finding tags based on given criteria
    (prefix, suffix, exact), getting the directory of a tag and so forth
    """
    def __init__(self, p, column, match_as=None):
        """Initialise TagFile object"""
        self.p = p
        self.column = column
        if isinstance(match_as, str):
            match_as = getattr(self, match_as)

        self.match_as = match_as or self.exact_matches

    def __getitem__(self, index):
        """Provide sequence-type interface to tag file.

        Allow tag file to be read like a list, i.e. ``for item in self:`` or
        ``self[key]``
        """
        self.fh.seek(index)
        self.fh.readline()
        try:
            return self.fh.readline().split(b'\t')[self.column]
        # Ask forgiveness not permission
        except IndexError:
            return ''

    def __len__(self):
        """Get size of tag file in bytes"""
        return os.stat(self.p).st_size

    @property
    def dir(self):
        """Get directory of tag file"""
        return os.path.dirname(self.p)

    def get(self, *tags):
        """Get a tag from the tag file"""
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
        """Get a tag with the given from the tag file"""
        with open(self.p, 'r+') as fh:
            self.fh = mmap.mmap(fh.fileno(), 0)

            for l in fh:
                if l.split('\t')[self.column].endswith(suffix):
                    yield l
                else:
                    continue

            self.fh.close()

    def exact_matches(self, iterator, tag):
        for l in iterator:
            comp = cmp(l.split('\t')[self.column], tag.decode())

            if comp == -1:
                continue
            elif comp:
                break

            yield l

    def starts_with(self, iterator, tag):
        for l in iterator:
            field = l.split('\t')[self.column]
            comp = cmp(field, tag.decode())

            if comp == -1:
                continue

            if field.startswith(tag):
                yield l
            else:
                break

    def tag_class(self):
        return type('Tag', (Tag,), dict(root_dir=self.dir))

    def get_tags_dict(self, *tags, **kw):
        """Return the tags from a tag file as a dict"""
        filters = kw.get('filters', [])
        return parse_tag_lines(self.get(*tags),
                               tag_class=self.tag_class(), filters=filters)

    def get_tags_dict_by_suffix(self, suffix, **kw):
        """Return the tags with the given suffix of a tag file as a dict"""
        filters = kw.get('filters', [])
        return parse_tag_lines(self.get_by_suffix(suffix),
                               tag_class=self.tag_class(), filters=filters)
