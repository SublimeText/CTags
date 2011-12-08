#coding: utf8
#################################### IMPORTS ###################################

# Std Libs
import functools
import glob
import os
import pprint
import re
import string
import threading

from contextlib import contextmanager
from itertools import chain
from operator import itemgetter as iget
from os.path import join, normpath, dirname

################################ SUBLIME IMPORTS ###############################
# Sublime Libs
import sublime
import sublime_plugin

from sublime import status_message

################################## APP IMPORTS #################################

# Ctags
import ctags
from ctags import (FILENAME, parse_tag_lines, PATH_ORDER, SYMBOL, Tag, TagFile)

################################### SETTINGS ###################################

setting = sublime.load_settings('CTags.sublime-settings').get # (key, None)

################################### CONSTANTS ##################################

OBJECT_PUNCTUATORS = {
    'class'    :  '.',
    'struct'   :  '::',
    'function' :  '/',
}

ENTITY_SCOPE = "entity.name.function, entity.name.type, meta.toc-list"

################################# AAA* IMPORTS #################################
# Inlined 07/26/11 20:39:51#
############################

ON_LOAD       = sublime_plugin.all_callbacks['on_load']

RE_SPECIAL_CHARS = re.compile ( #as “f
    '(\\\\|\\*|\\+|\\?|\\||\\{|\\}|\\[|\\]|\\(|\\)|\\^|\\$|\\.|\\#|\\ )' )

def escape_regex(s):
    return RE_SPECIAL_CHARS.sub(lambda m: '\\%s' % m.group(1), s)

def select(view, region):
    sel_set = view.sel()
    sel_set.clear()
    sel_set.add(region)
    view.show(region)

def in_main(f):
    @functools.wraps(f)
    def done_in_main(*args, **kw):
        sublime.set_timeout(functools.partial(f, *args, **kw), 0)

    return done_in_main

# TODO: allow thread per tag file. That makes more sense.
def threaded(finish=None, msg="Thread already running"):
    def decorator(func):
        func.running = 0
        @functools.wraps(func)
        def threaded(*args, **kwargs):
            def run():
                try:
                    result = func(*args, **kwargs)
                    if result is None:
                        result = ()

                    elif not isinstance(result, tuple):
                        result = (result, )

                    if finish:
                        sublime.set_timeout (
                            functools.partial(finish, args[0], *result), 0
                        )
                finally:
                    func.running = 0
            if not func.running:
                func.running = 1
                t = threading.Thread(target=run)
                t.setDaemon(True)
                t.start()
            else:
                sublime.status_message(msg)
        threaded.func = func
        return threaded
    return decorator

class one_shot(object):
    def __init__(self):
        self.callbacks.append(self)
        self.remove = lambda: self.callbacks.remove(self)

@contextmanager
def edition(view):
    edit = view.begin_edit()
    try:
        yield
    finally:
        view.end_edit(edit)

def on_load(f=None, window=None, encoded_row_col=True, begin_edit=False):
    window = window or sublime.active_window()
    def wrapper(cb):
        if not f: return cb(window.active_view())
        view = window.open_file( normpath(f), encoded_row_col )
        def wrapped():
            if begin_edit:
                with edition(view): cb(view)
            else: cb(view)

        if view.is_loading():
            class set_on_load(one_shot):
                callbacks = ON_LOAD
                def on_load(self, view):
                    try:wrapped()
                    finally: self.remove()
            set_on_load()
        else: wrapped()
    return wrapper

#################################### HELPERS ###################################

def view_fn(v): return v.file_name() or '.'

def find_tags_relative_to(view):
    fn = view.file_name()
    if not fn: return ''

    dirs = normpath(join(dirname(fn), '.tags')).split(os.path.sep)
    f = dirs.pop()

    while dirs:
        joined = normpath(os.path.sep.join(dirs + [f]))
        if os.path.exists(joined) and not os.path.isdir(joined): return joined
        else: dirs.pop()

    status_message("Can't find any relevant tags file")

def alternate_tags_paths(view, tags_file):
    tags_paths = '%s_search_paths' % tags_file
    search_paths = [tags_file]

    if os.path.exists(tags_paths):
        search_paths.extend(open(tags_paths).read().split('\n'))

    try:
        for (selector, platform), path in setting('extra_tag_paths'):
            if ( view.match_selector(view.sel()[0].begin(), selector) and
                 sublime.platform() == platform ):
                search_paths.append(path)
    except Exception, e:
        print e

    if os.path.exists(tags_paths):
        for extrafile in setting('extra_tag_files'):
            search_paths.append(normpath(join(dirname(tags_file), extrafile)))


    # Ok, didn't found the .tags file under the viewed file.
    # Let's look in the currently openened folder
    for folder in view.window().folders():
        search_paths.append(normpath(join(folder, '.tags')))
        for extrafile in setting('extra_tag_files'):
            search_paths.append(normpath(join(folder, extrafile)))

    return [p for p in search_paths if p and os.path.exists(p)]

################################# SCROLL TO TAG ################################

def find_with_scope(view, pattern, scope, start_pos=0, cond=True, flags=0):
    max_pos = view.size()

    while start_pos < max_pos:
        f = view.find(pattern, start_pos, flags )

        if not f or view.match_selector( f.begin(), scope) is cond:
            break
        else:
            start_pos = f.end()

    return f

def find_source(view, pattern, start_at, flags=sublime.LITERAL):
    return find_with_scope (
              view,
              pattern, "comment,string", start_at, False, flags )

def follow_tag_path(view, tag_path, pattern):
    regions = [sublime.Region(0, 0)]

    for p in list(tag_path)[1:-1]:
        while True:                               #.end() is BUG!
            regions.append(find_source(view, p, regions[-1].begin()))

            if ( regions[-1] is None or (regions[-1] == regions[-2]) or
                 view.match_selector(regions[-1].begin(), ENTITY_SCOPE) ):
                regions = [r for r in regions if r is not None]
                break

    start_at = max(regions, key=lambda r: r.begin()).begin() -1

    # Find the ex_command pattern
    pattern_region = find_source (
        view, '^' + escape_regex(pattern), start_at, flags=0 )

    if setting('debug'): # Leave a visual trail for easy debugging
        regions = regions  + ([pattern_region] if pattern_region else [])
        view.erase_regions('tag_path')
        view.add_regions('tag_path', regions, 'comment', 1)

    return pattern_region.begin() -1 if pattern_region else start_at

def scroll_to_tag(view, tag, hook=None):
    @on_load(join(tag.root_dir, tag.filename))
    def and_then(view):
        if tag.ex_command.isdigit():
            look_from = view.text_point(int(tag.ex_command)-1, 0)
        else:
            look_from = follow_tag_path(view, tag.tag_path, tag.ex_command)

        symbol_region = view.find(tag.symbol, look_from, sublime.LITERAL)

        select (
            view,
            (symbol_region or (
              view.line(look_from + 1) if look_from else sublime.Region(0, 0))))

        if hook: hook(view)

############################## FORMATTING HELPERS ##############################

def format_tag_for_quickopen(tag, file=1):
    format = []
    tag = ctags.Tag(tag)

    f=''
    for field in getattr(tag, "field_keys", []):
        if field in PATH_ORDER:
            punct = OBJECT_PUNCTUATORS.get(field, ' -> ')
            f += string.Template (
                '    %($field)s$punct%(symbol)s' ).substitute(locals())

    format = [(f or tag.symbol) % tag, tag.ex_command]
    format[1] = format[1].strip()
    if file: format.insert(1, tag.filename )
    return format

def prepared_4_quickpanel(formatter=format_tag_for_quickopen, path_cols=()):
    def compile_lists(sorter):
        args, display = [], []

        for t in sorter():
            display.append(formatter(t))
            args.append(t)

        return args, display# format_for_display(display,  paths=path_cols)

    return compile_lists

############################ FILE COLLECTION HELPERS ###########################

def commonfolder(m):
    if not m: return ''

    s1 = min(m).split(os.path.sep)
    s2 = max(m).split(os.path.sep)

    for i, c in enumerate(s1):
        if c != s2[i]:
            return os.path.sep.join(s1[:i])

    return os.path.sep.join(s1)

def tagged_project_files(view, tag_dir):
    window = view.window()
    if not window: return []
    project = None #window.project()
    fn = view_fn(view)

    if not project or ( project and
                        not  fn.startswith(dirname(project.fileName())) ):
        prefix_arg = fn
        files = glob.glob(join(dirname(fn),"*"))
    else:
        prefix_arg = project.fileName()
        mount_points = project.mountPoints()
        files = list( chain(*(d['files'] for d in mount_points)) )

    common_prefix = commonfolder([tag_dir, prefix_arg])

    return [fn[len(common_prefix)+1:] for fn in files]

def files_to_search(view, tags_file, multiple=True):
    fn = view.file_name()
    if not fn: return

    tag_dir = normpath(dirname(tags_file))

    common_prefix = commonfolder([tag_dir, fn])
    files = [fn[len(common_prefix)+1:]]

    if multiple:
        more_files = tagged_project_files(view, tag_dir)
        files.extend(more_files)

    return files

############################### JUMPBACK COMMANDS ##############################

def different_mod_area(f1, f2, r1, r2):
    same_file   = f1 == f2
    same_region = abs(r1[0] - r2[0]) < 40
    return not same_file or not same_region

class JumpBack(sublime_plugin.WindowCommand):
    def is_enabled(self, to=None):
        if to == 'last_modification':
            return len(self.mods) > 1
        return len(self.last) > 0

    def is_visible(self, to=None):
        return setting("show_context_menus")

    last    =     []
    mods    =     []

    def run(self, to=None):
        if to == 'last_modification' and self.mods:
            return self.lastModifications()

        if not JumpBack.last: return status_message('JumpBack buffer empty')

        f, sel = JumpBack.last.pop()
        self.jump(f, eval(sel))

    def lastModifications(self):
        # Current Region
        cv = sublime.active_window().active_view()
        cr = eval(`cv.sel()[0]`)
        cf   = cv.file_name()

        # Very latest, s)tarting modification

        sf, sr = JumpBack.mods.pop(0)

        if sf is None: return
        sr = eval(sr)

        in_different_mod_area = different_mod_area (sf, cf, cr, sr)

        # Default J)ump F)ile and R)egion
        jf, jr = sf, sr

        if JumpBack.mods:
            for i, (f, r) in enumerate(JumpBack.mods):
                region = eval(r)
                if different_mod_area(sf, f, sr, region):
                    break

            del JumpBack.mods[:i]
            if not in_different_mod_area:
                jf, jr = f, region

        if in_different_mod_area or not JumpBack.mods:
            JumpBack.mods.insert(0, (jf, `jr`))

        self.jump(jf, jr)

    def jump(self, fn, sel):
        @on_load(fn, begin_edit=True)
        def and_then(view):
            select(view, sublime.Region(*sel))

    @classmethod
    def append(cls, view):
        fn = view.file_name()
        if fn:
            cls.last.append((fn, `view.sel()[0]`))

class JumpBackListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        sel = view.sel()
        if len(sel):
            JumpBack.mods.insert(0, (view.file_name(), `sel[0]`))
            del JumpBack.mods[100:]

################################ CTAGS COMMANDS ################################

def ctags_goto_command(jump_directly_if_one=False):
    def wrapper(f):
        def command(self, edit, **args):
            view = self.view
            tags_file = find_tags_relative_to(view)

            result = f(self, self.view, args, tags_file, {})

            if result not in (True, False, None):
                args, display = result
                if not args: return

                def on_select(i):
                    if i != -1:
                        JumpBack.append(view)
                        scroll_to_tag(view, args[i])

                ( on_select(0) if   jump_directly_if_one and len(args) == 1
                               else view.window().show_quick_panel (
                                                  display, on_select ) )
        return command
    return wrapper

def check_if_building(self, **args):
    if rebuild_tags.build_ctags.func.running:
        status_message('Please wait while tags are built')

    else:  return 1


def compile_filters(view):
    filters = []
    for selector, regexes in setting('filters', {}).items():
        if view.match_selector (
            view.sel() and view.sel()[0].begin() or 0, selector ):
            filters.append(regexes)
    return filters

def compile_definition_filters(view):
    filters = []
    for selector, regexes in setting('definition_filters', {}).items():
        if view.match_selector (
            view.sel() and view.sel()[0].begin() or 0, selector ):
            filters.append(regexes)
    return filters

######################### GOTO DEFINITION UNDER CURSOR #########################

class NavigateToDefinition(sublime_plugin.TextCommand):
    is_enabled = check_if_building

    def is_visible(self):
        return setting("show_context_menus")

    @ctags_goto_command(jump_directly_if_one=True)
    def run(self, view, args, tags_file, tags):
        symbol = view.substr(view.word(view.sel()[0]))

        for tags_file in alternate_tags_paths(view, tags_file):
            tags = (TagFile( tags_file, SYMBOL)
                            .get_tags_dict( symbol,
                                            filters=compile_filters(view)) )
            if tags: break

        if not tags:
            return status_message('Can\'t find "%s"' % symbol)

        current_file = view.file_name().replace(dirname(tags_file) + os.sep, '')
        def definition_cmp(a, b):
            if normpath(a.tag_path[0]) == current_file:
                return -1
            if normpath(b.tag_path[0]) == current_file:
                return 1
            return 0

        def_filters = compile_definition_filters(view)
        def pass_def_filter(o):
            for f in def_filters:
                for k, v in f.items():
                    if re.match(v, o[k]):
                        return False
            return True

        @prepared_4_quickpanel()
        def sorted_tags():
            p_tags = filter(pass_def_filter, tags.get(symbol, []))
            if not p_tags:
                status_message('Can\'t find "%s"' % symbol)
            p_tags = sorted(p_tags, key=iget('tag_path'))
            if setting('definition_current_first', False):
                p_tags = sorted(p_tags, cmp=definition_cmp)
            return p_tags                

        return sorted_tags

################################# SHOW SYMBOLS #################################

class ShowSymbols(sublime_plugin.TextCommand):
    is_enabled = check_if_building

    def is_visible(self):
        return setting("show_context_menus")

    @ctags_goto_command()
    def run(self, view, args, tags_file, tags):
        if not tags_file: return
        multi = args.get('type') =='multi'

        files = files_to_search(view, tags_file, multi)
        if not files: return

        tags_file = tags_file + '_sorted_by_file'
        tags = (TagFile(tags_file, FILENAME)
                       .get_tags_dict(*files, filters=compile_filters(view)))
        if not tags:
            if multi:
                view.run_command('show_symbols', {'type':'multi'})
            else:
                sublime.status_message(
                    'No symbols found **FOR CURRENT FILE**; Try Rebuild?' )

        path_cols = (0, ) if len(files) > 1 else ()
        formatting = functools.partial( format_tag_for_quickopen,
                                        file = bool(path_cols)  )

        @prepared_4_quickpanel(formatting, path_cols=())
        def sorted_tags():
            return sorted (
                chain(*(tags[k] for k in tags)), key=iget('tag_path'))

        return sorted_tags

################################# REBUILD CTAGS ################################

class rebuild_tags(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        view=self.view
        tag_file = find_tags_relative_to(view)

        if not tag_file:
            if view.window().folders():
                base_path = view.window().folders()[0]
            else:
                base_path = dirname(view_fn(view))
            tag_file = join(base_path, '.tags')
            
            if 0: #not 1 or sublime.question_box('`ctags -R` in %s ?'% dirname(tag_file)):
                return

        self.build_ctags(setting('ctags_command'), tag_file)

    def done_building(self, tag_file):
        status_message('Finished building %s' % tag_file)

    @threaded(finish=done_building, msg="Already running CTags!")
    def build_ctags(self, cmd, tag_file):
        in_main(lambda: status_message('Re/Building CTags: Please be patient'))()
        ctags.build_ctags(cmd, tag_file)
        return tag_file

################################# AUTOCOMPLETE #################################

# class CTagsAutoComplete(sublime_plugin.EventListener):
#     def on_query_completions(self, view, prefix, locations):
#         tags = find_tags_relative_to(view)
#         completions = []

#         if tags:
#             tag_file = TagFile(tags, SYMBOL, MATCHES_STARTWITH)
#             completions = [(a,a) for a in sorted(tag_file.get_tags_dict(prefix[0]))]

#         return []

##################################### TEST #####################################

class test_ctags(sublime_plugin.TextCommand):
    routine = None

    def run(self, edit, **args):
        view=self.view
        if self.routine is None:
            self.routine = self.co_routine(view)
            self.routine.next()

    def next(self):
        try:
            self.routine.next()
        except Exception, e:
            print e
            self.routine = None

    def co_routine(self, view):
        tag_file = find_tags_relative_to(view)

        with open(tag_file) as tf:
            tags = parse_tag_lines(tf, tag_class=Tag)

        print 'Starting Test'

        ex_failures = []
        line_failures = []

        for symbol, tag_list in tags.items():
            for tag in tag_list:
                tag.root_dir = dirname(tag_file)

                def hook(av):
                    test_context = av.sel()[0]

                    if tag.ex_command.isdigit():
                        test_string = tag.symbol
                    else:
                        test_string = tag.ex_command
                        test_context = av.line(test_context)

                    if not ((av.substr(test_context) == test_string) #):
                            or
                            av.substr(test_context).startswith(test_string) ):

                        failure = 'FAILURE %s' % pprint.pformat(tag)
                        failure += av.file_name()

                        if setting('debug') and not sublime.question_box('%s\n\n\n' % failure):
                            self.routine = None
                            return sublime.set_clipboard(failure)

                        ex_failures.append(tag)

                    sublime.set_timeout( self.next, 5 )

                scroll_to_tag(view, tag, hook)
                yield

        failures = line_failures + ex_failures
        tags_tested = sum(len(v) for v in tags.values()) - len(failures)

        view = sublime.active_window().new_file()

        edit = view.begin_edit()
        view.insert(edit, view.size(), '%s Tags Tested OK\n' % tags_tested)
        view.insert(edit, view.size(), '%s Tags Failed'    % len(failures))
        view.end_edit(edit)
        view.set_scratch(True)
        view.set_name('CTags Test Results')

        if failures:
            sublime.set_clipboard(pprint.pformat(failures))

################################################################################