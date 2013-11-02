#!/usr/bin/env python

"""A ctags wrapper, parser and sorter"""

import codecs
import re
import os
import subprocess
import bisect
import mmap

from os.path import dirname

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
    return (str(a) > str(b)) - (str(a) < str(b))


def splits(string, *splitters):
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
    tags_lookup = {}

    for l in lines:
        search_obj = TAGS_RE.search(l)
        if not search_obj:
            continue

        tag = post_process_tag(search_obj)
        if tag_class is not None:
            tag = tag_class(tag)

        skip = False
        for f in filters:
            for k, v in list(f.items()):
                if re.match(v, tag[k]):
                    skip = True

        if skip:
            continue

        tags_lookup.setdefault(tag[order_by], []).append(tag)

    return tags_lookup


def unescape_ex(ex):
    return re.sub(r"\\(\$|/|\^|\\)", r'\1', ex)


def post_process_tag(search_obj):
    tag = search_obj.groupdict()

    fields = tag.get('fields')
    if fields:
        fields_dict = process_fields(fields)
        tag.update(fields_dict)
        tag['field_keys'] = sorted(fields_dict.keys())

    tag['ex_command'] = process_ex_cmd(tag['ex_command'])

    create_tag_path(tag)

    return tag


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
    p = subprocess.Popen(cmd, cwd=dirname(tag_file), shell=1, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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
    def __init__(self, *args, **kw):
        dict.__init__(self, *args, **kw)
        self.__dict__ = self


class TagFile(object):
    def __init__(self, p, column, match_as=None):
        self.p = p
        self.column = column
        if isinstance(match_as, str):
            match_as = getattr(self, match_as)

        self.match_as = match_as or self.exact_matches

    def __getitem__(self, index):
        self.fh.seek(index)
        self.fh.readline()
        try:
            return self.fh.readline().split(b'\t')[self.column]
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

    @property
    def dir(self):
        return dirname(self.p)

    def tag_class(self):
        return type('Tag', (Tag,), dict(root_dir=self.dir))

    def get_tags_dict_by_suffix(self, suffix, **kw):
        filters = kw.get('filters', [])
        return parse_tag_lines(self.get_by_suffix(suffix),
                               tag_class=self.tag_class(), filters=filters)

    def get_tags_dict(self, *tags, **kw):
        filters = kw.get('filters', [])
        return parse_tag_lines(self.get(*tags),
                               tag_class=self.tag_class(), filters=filters)
