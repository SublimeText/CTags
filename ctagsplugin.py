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
from collections import defaultdict

################################ SUBLIME IMPORTS ###############################
# Sublime Libs
import sublime
import sublime_plugin

from sublime import status_message

################################## APP IMPORTS #################################
sublime_version = 2
if int(sublime.version()) > 3000:
    sublime_version = 3
# Ctags
if sublime_version == 2:
    import ctags
    from ctags import (FILENAME, parse_tag_lines, PATH_ORDER, SYMBOL, Tag, TagFile)
elif sublime_version == 3:
    from . import ctags
    from .ctags import (FILENAME, parse_tag_lines, PATH_ORDER, SYMBOL, Tag, TagFile)


################################### SETTINGS ###################################

def get_settings():
    return sublime.load_settings("CTags.sublime-settings")

def get_setting(key, default=None, view=None):
    try:
        if view == None:
            view = sublime.active_window().active_view()
        s = view.settings()
        if s.has("ctags_%s" % key):
            return s.get("ctags_%s" % key)
    except:
        pass
    return get_settings().get(key, default)

setting = get_setting

################################### CONSTANTS ##################################

OBJECT_PUNCTUATORS = {
    'class'    :  '.',
    'struct'   :  '::',
    'function' :  '/',
}

ENTITY_SCOPE = "entity.name.function, entity.name.type, meta.toc-list"

RUBY_SPECIAL_ENDINGS = "\?|!"
RUBY_SCOPES = ".*(ruby|rails).*"

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

def find_tags_relative_to(file_name):
    if not file_name: return None

    dirs = dirname(normpath(file_name)).split(os.path.sep)

    while dirs:
        joined = os.path.sep.join(dirs + ['.tags'])
        if os.path.exists(joined) and not os.path.isdir(joined): return joined
        else: dirs.pop()

    return None

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
    except Exception as e:
        print (e)

    if os.path.exists(tags_paths):
        for extrafile in setting('extra_tag_files'):
            search_paths.append(normpath(join(dirname(tags_file), extrafile)))


    # Ok, didn't found the .tags file under the viewed file.
    # Let's look in the currently openened folder
    for folder in view.window().folders():
        search_paths.append(normpath(join(folder, '.tags')))
        for extrafile in setting('extra_tag_files'):
            search_paths.append(normpath(join(folder, extrafile)))

    return set(p for p in search_paths if p and os.path.exists(p))


def reached_top_level_folders(folders, oldpath, path):
    if oldpath == path:
        return True
    for folder in folders:
        if folder[:len(path)] == path:
            return True
        if path == os.path.dirname(folder):
            return True
    return False


def find_top_folder(view, filename):
    folders = view.window().folders()
    path = os.path.dirname(filename)

    # We don't have any folders open, return the folder this file is in
    if len(folders) == 0:
        return path

    oldpath = ''
    while not reached_top_level_folders(folders, oldpath, path):
        oldpath = path
        path = os.path.dirname(path)
    return path


################################# SCROLL TO TAG ################################

def find_with_scope(view, pattern, scope, start_pos=0, cond=True, flags=0):
    max_pos = view.size()

    while start_pos < max_pos:
        f = view.find(pattern[:-5] + "$", start_pos, flags )

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

        symbol_region = view.find(tag.ex_command, look_from, sublime.LITERAL)

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

def files_to_search(view, tags_file, multiple=True):

    if multiple:
        return []

    fn = view.file_name()
    if not fn: return

    tag_dir = normpath(dirname(tags_file))

    common_prefix = commonfolder([tag_dir, fn])
    files = [fn[len(common_prefix)+1:]]

    return files

def get_current_file_suffix(view):
    current = view.file_name()
    fileName, fileExtension = os.path.splitext(current)
    return fileExtension


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
        cr = eval(repr(cv.sel()[0]))
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
            JumpBack.mods.insert(0, (jf, repr(jr)))

        self.jump(jf, jr)

    def jump(self, fn, sel):
        @on_load(fn, begin_edit=True)
        def and_then(view):
            select(view, sublime.Region(*sel))

    @classmethod
    def append(cls, view):
        fn = view.file_name()
        if fn:
            cls.last.append((fn, repr(view.sel()[0])))

class JumpBackListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        sel = view.sel()
        if len(sel):
            JumpBack.mods.insert(0, (view.file_name(), repr(sel[0])))
            del JumpBack.mods[100:]

################################ CTAGS COMMANDS ################################

def show_tag_panel(view, result, jump_directly_if_one):
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

def ctags_goto_command(jump_directly_if_one=False):
    def wrapper(f):
        def command(self, edit, **args):
            view = self.view
            tags_file = find_tags_relative_to(view.file_name())
            if not tags_file:
                status_message("Can't find any relevant tags file")
                return

            result = f(self, self.view, args, tags_file)
            show_tag_panel(self.view, result, jump_directly_if_one)

        return command
    return wrapper

def check_if_building(self, **args):
    if rebuild_tags.build_ctags.func.running:
        status_message('Please wait while tags are built')

    else:  return True

def compile_filters(view):
    filters = []
    for selector, regexes in list(setting('filters', {}).items()):
        if view.match_selector (
            view.sel() and view.sel()[0].begin() or 0, selector ):
            filters.append(regexes)
    return filters

def compile_definition_filters(view):
    filters = []
    for selector, regexes in list(setting('definition_filters', {}).items()):
        if view.match_selector (
            view.sel() and view.sel()[0].begin() or 0, selector ):
            filters.append(regexes)
    return filters

######################### GOTO DEFINITION UNDER CURSOR #########################

class JumpToDefinition:
    @staticmethod
    def run(symbol, view, tags_file):
        tags = {}
        for tags_file in alternate_tags_paths(view, tags_file):
            tags = (TagFile( tags_file, SYMBOL)
                            .get_tags_dict( symbol,
                                            filters=compile_filters(view)) )
            if tags: break

        if not tags:
            return status_message('Can\'t find "%s"' % symbol)

        current_file = view.file_name().replace(dirname(tags_file) + os.sep, '')

        def_filters = compile_definition_filters(view)
        def pass_def_filter(o):
            for f in def_filters:
                for k, v in list(f.items()):
                    if k in o:
                        if re.match(v, o[k]):
                            return False
            return True

        @prepared_4_quickpanel()
        def sorted_tags():
            p_tags = list(filter(pass_def_filter, tags.get(symbol, [])))
            if not p_tags:
                status_message('Can\'t find "%s"' % symbol)
            p_tags = sorted(p_tags, key=iget('tag_path'))
            return p_tags

        return sorted_tags


class NavigateToDefinition(sublime_plugin.TextCommand):
    is_enabled = check_if_building
    def __init__(self, args):
      sublime_plugin.TextCommand.__init__(self,args)
      self.scopes = re.compile(RUBY_SCOPES)
      self.endings = re.compile(RUBY_SPECIAL_ENDINGS)

    def is_visible(self):
        return setting("show_context_menus")

    @ctags_goto_command(jump_directly_if_one=True)
    def run(self, view, args, tags_file):
        region = view.sel()[0]
        if region.begin() == region.end(): #point
          region = view.word(region)
        symbol = view.substr(region)
        return JumpToDefinition.run(symbol, view, tags_file)


class SearchForDefinition(sublime_plugin.WindowCommand):
    is_enabled = check_if_building

    def is_visible(self):
        return setting("show_context_menus")

    def run(self):
        self.window.show_input_panel('','', self.on_done, self.on_change, self.on_cancel)

    def on_done(self, symbol):
        view = self.window.active_view()
        tags_file = find_tags_relative_to(view.file_name())
        if not tags_file:
            status_message("Can't find any relevant tags file")
            return

        result = JumpToDefinition.run(symbol, view, tags_file)
        show_tag_panel(view, result, True)

    def on_change(self, text):
        pass

    def on_cancel(self):
        pass

################################# SHOW SYMBOLS #################################

tags_cache = defaultdict(dict)

class ShowSymbols(sublime_plugin.TextCommand):
    is_enabled = check_if_building

    def is_visible(self):
        return setting("show_context_menus")

    @ctags_goto_command()
    def run(self, view, args, tags_file):
        if not tags_file: return
        multi = args.get('type') == 'multi'
        lang = args.get('type') == 'lang'
        files = files_to_search(view, tags_file, multi)

        if lang:
            suffix = get_current_file_suffix(view)
            key = suffix
        else:
            key = ",".join(files)

        tags_file = tags_file + '_sorted_by_file'

        base_path = find_top_folder(view, view.file_name())


        def get_tags():
            loaded = TagFile(tags_file, FILENAME)
            if lang: return loaded.get_tags_dict_by_suffix(suffix, filters=compile_filters(view))
            else: 
                return loaded.get_tags_dict(*files, filters=compile_filters(view))

        if key in tags_cache[base_path]:
            print ("loading symbols from cache")
            tags = tags_cache[base_path][key]
        else:
            print ("loading symbols from file")
            tags = get_tags()
            tags_cache[base_path][key] = tags

        print(("loaded [%d] symbols" % len(tags)))

        if not tags:
            if multi:
                view.run_command('show_symbols', {'type':'multi'})
            else:
                sublime.status_message(
                    'No symbols found **FOR CURRENT FILE**; Try Rebuild?' )

        path_cols = (0, ) if len(files) > 1 or multi else ()
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

        tag_dirs = []
        if "dirs" in args:
            # User has requested to rebuild CTags for the specific folders (via context menu in Folders pane)
            tag_dirs.extend(args["dirs"])
        elif view.file_name() is not None:
            # Rebuild and rebuild tags relative to the currently opened file
            tag_dir = find_top_folder(view, view.file_name())
            tag_dirs.append(tag_dir)
        elif len(view.window().folders()) > 0:
            # No file is open, rebuild tags for all opened folders
            tag_dirs.extend(view.window().folders())
        else:
            status_message("Cannot build CTags: No file or folder open.")
            return

        tag_files = [join(t, ".tags") for t in tag_dirs]

        # Any .tags file found when walking up the directory tree has precedence
        def replace_with_parent_tags_if_exists(tag_file):
            parent_tag_file = find_tags_relative_to(tag_file)
            return parent_tag_file if parent_tag_file else tag_file
        tag_files = set(map(replace_with_parent_tags_if_exists, tag_files))

        # TODO: replace with sublime.ok_cancel_dialog or maybe just delete?
        if 0:  # not 1 or sublime.question_box(''ctags -R' in %s ?'% dirname(tag_file)):
            return

        command = setting('command', setting('ctags_command'))
        self.build_ctags(command, tag_files)
        GetAllCTagsList.ctags_list = []  # clear the cached ctags list

    @threaded(msg="Already running CTags!")
    def build_ctags(self, cmd, tag_files):

        def tags_built(tag_file):
            print(('Finished building %s' % tag_file))
            in_main(lambda: status_message('Finished building %s' % tag_file))()
            in_main(lambda: tags_cache[dirname(tag_file)].clear())()

        for tag_file in tag_files:
            print(('Re/Building CTags for %s: Please be patient' % tag_file))
            in_main(lambda: status_message('Re/Building CTags for %s: Please be patient' % tag_file))()
            ctags.build_ctags(cmd, tag_file)
            tags_built(tag_file)

################################# AUTOCOMPLETE #################################

class GetAllCTagsList():
    ctags_list = []
    """cache all the ctags list"""
    def __init__(self, list):
        self.ctags_list = list

class CTagsAutoComplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if setting('autocomplete'):
            prefix = prefix.strip().lower()
            tags_path = view.window().folders()[0]+"/.tags"

            sub_results = [v.extract_completions(prefix) for v in sublime.active_window().views()]
            sub_results = [(item,item) for sublist in sub_results for item in sublist] #flatten

            if GetAllCTagsList.ctags_list:
                results = [sublist for sublist in GetAllCTagsList.ctags_list if sublist[0].lower().startswith(prefix)]
                results = list(set(results).union(set(sub_results)))
                results.sort()
                return results
            else:
                tags = []
                if (not view.window().folders() or not os.path.exists(tags_path)): #check if a project is open and the .tags file exists
                    return tags
                f=os.popen("awk '{ print $1 }' '" + tags_path + "'")
                for i in f.readlines():
                    tags.append([i.strip()])
                tags = [(item,item) for sublist in tags for item in sublist] #flatten
                tags = list(set(tags)) # make unique
                tags.sort()
                GetAllCTagsList.ctags_list = tags
                results = [sublist for sublist in GetAllCTagsList.ctags_list if sublist[0].lower().startswith(prefix)]
                results = list(set(results).union(set(sub_results)))
                results.sort()
                return results

##################################### TEST #####################################

class test_ctags(sublime_plugin.TextCommand):
    routine = None

    def run(self, edit, **args):
        view=self.view
        if self.routine is None:
            self.routine = self.co_routine(view)
            next(self.routine)

    def __next__(self):
        try:
            next(self.routine)
        except Exception as e:
            print (e)
            self.routine = None

    def co_routine(self, view):
        tag_file = find_tags_relative_to(view.file_name())

        with open(tag_file) as tf:
            tags = parse_tag_lines(tf, tag_class=Tag)

        print ('Starting Test')

        ex_failures = []
        line_failures = []

        for symbol, tag_list in list(tags.items()):
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

                    sublime.set_timeout( self.__next__, 5 )

                scroll_to_tag(view, tag, hook)
                yield

        failures = line_failures + ex_failures
        tags_tested = sum(len(v) for v in list(tags.values())) - len(failures)

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
