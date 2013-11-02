################################################################################
# coding: utf8
################################################################################

# Std Libs


import re
import unittest
import os
import subprocess
import bisect
import mmap
import platform
import sublime

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
def cmp(a,b):
    return (str(a) > str(b)) - (str(a) < str(b))
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
        search_obj = TAGS_RE.search(l)
        if not search_obj:
            continue

        tag = post_process_tag(search_obj)
        if tag_class is not None: tag = tag_class(tag)

        skip = False
        for f in filters:
            for k, v in list(f.items()):
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
    import codecs

    with codecs.open(tag_file, encoding="utf-8") as fh:
        for l in fh:
            keys.setdefault(l.split('\t')[FILENAME], []).append(l)

    with codecs.open(tag_file + '_sorted_by_file', 'w', encoding="utf-8") as fw:
        for k in sorted(keys):
            for line in keys[k]:
                split = line.split('\t')
                split[FILENAME] = split[FILENAME].lstrip('.\\')
                fw.write('\t'.join(split))

def build_ctags(cmd, tag_file, env=None):
    if platform.system() == "Windows":
        ctags_path = str(sublime.packages_path())+"\\Ctags\\ctags58\\"
        env = os.environ.copy()
        env["PATH"] = ";".join([env["PATH"], ctags_path])
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
    except Exception as e:
        print ('OK')
        print (e)
    else:
        raise "Should have died"
    # EnvironmentError: (['ctags.exe -R'], 1, '\'"ctags.exe -R"\' is not recognized as an internal or external command,\r\noperable program or batch file.\r\n')

def test_build_ctags__dodgy_command():
    try:
        build_ctags(['ctags', '--arsts'], r'C:\Users\nick\AppData\Roaming\Sublime Text 2\Packages\CTags\tags')
    except Exception as e:
        print ('OK')
        print (e)
    else:
        raise "Should have died"

################################################################################

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
        try:  return self.fh.readline().split(b'\t')[self.column]
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
            comp = cmp(l.split('\t')[self.column], tag.decode())

            if    comp == -1:    continue
            elif  comp:          break

            yield l

    def starts_with(self, iterator, tag):
        for l in iterator:
            field = l.split('\t')[self.column]
            comp = cmp(field, tag.decode())

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
