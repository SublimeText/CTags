"""
A ctags plugin for Sublime Text 2/3.
"""

import functools
from functools import reduce
import codecs
import locale
import sys
import os
import pprint
import re
import string
import threading
import subprocess

from itertools import chain
from operator import itemgetter as iget
from collections import defaultdict, deque

try:
    import sublime
    import sublime_plugin
    from sublime import status_message, error_message

    # hack the system path to prevent the following issue in ST3
    #     ImportError: No module named 'ctags'
    sys.path.append(os.path.dirname(os.path.realpath(__file__)))
except ImportError:  # running tests
    from tests.sublime_fake import sublime
    from tests.sublime_fake import sublime_plugin

    sys.modules['sublime'] = sublime
    sys.modules['sublime_plugin'] = sublime_plugin

import ctags
from ctags import (FILENAME, parse_tag_lines, PATH_ORDER, SYMBOL,
                   TagElements, TagFile)
from helpers.edit import Edit

from helpers.common import *
from ranking.rank import RankMgr
from ranking.parse import Parser

#
# Contants
#

OBJECT_PUNCTUATORS = {
    'class': '.',
    'struct': '::',
    'function': '/',
}

ENTITY_SCOPE = 'entity.name.function, entity.name.type, meta.toc-list'

RUBY_SPECIAL_ENDINGS = r'\?|!'

ON_LOAD = sublime_plugin.all_callbacks['on_load']


#
# Functions
#


def select(view, region):
    sel_set = view.sel()
    sel_set.clear()
    sel_set.add(region)
    sublime.set_timeout(functools.partial(view.show_at_center, region), 1)


def in_main(f):
    @functools.wraps(f)
    def done_in_main(*args, **kw):
        sublime.set_timeout(functools.partial(f, *args, **kw), 0)

    return done_in_main

# TODO: allow thread per tag file. That makes more sense.


def threaded(finish=None, msg='Thread already running'):
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
                        sublime.set_timeout(
                            functools.partial(finish, args[0], *result), 0)
                finally:
                    func.running = 0
            if not func.running:
                func.running = 1
                t = threading.Thread(target=run)
                t.setDaemon(True)
                t.start()
            else:
                status_message(msg)
        threaded.func = func

        return threaded

    return decorator


def on_load(path=None, window=None, encoded_row_col=True, begin_edit=False):
    """
    Decorator to open or switch to a file.

    Opens and calls the "decorated function" for the file specified by path,
    or the current file if no path is specified. In the case of the former, if
    the file is open in another tab that tab will gain focus, otherwise the
    file will be opened in a new tab with a requisite delay to allow the file
    to open. In the latter case, the "decorated function" will be called on
    the currently open file.

    :param path: path to a file
    :param window: the window to open the file in
    :param encoded_row_col: the ``sublime.ENCODED_POSITION`` flag for
        ``sublime.Window.open_file``
    :param begin_edit: if editing the file being opened

    :returns: None
    """
    window = window or sublime.active_window()

    def wrapper(f):
        # if no path, tag is in current open file, return that
        if not path:
            return f(window.active_view())
        # else, open the relevant file
        view = window.open_file(os.path.normpath(path), encoded_row_col)

        def wrapped():
            # if editing the open file
            if begin_edit:
                with Edit(view):
                    f(view)
            else:
                f(view)

        # if buffer is still loading, wait for it to complete then proceed
        if view.is_loading():
            class set_on_load():
                callbacks = ON_LOAD

                def __init__(self):
                    # append self to callbacks
                    self.callbacks.append(self)

                def remove(self):
                    # remove self from callbacks, hence disconnecting it
                    self.callbacks.remove(self)

                def on_load(self, view):
                    # on file loading
                    try:
                        wrapped()
                    finally:
                        # disconnect callback
                        self.remove()

            set_on_load()
        # else just proceed (file was likely open already in another tab)
        else:
            wrapped()

    return wrapper


def find_tags_relative_to(path, tag_file):
    """
    Find the tagfile relative to a file path.

    :param path: path to a file
    :param tag_file: name of tag file

    :returns: path of deepest tag file with name of ``tag_file``
    """
    if not path:
        return None

    dirs = os.path.dirname(os.path.normpath(path)).split(os.path.sep)

    while dirs:
        joined = os.path.sep.join(dirs + [tag_file])

        if os.path.exists(joined) and not os.path.isdir(joined):
            return joined
        else:
            dirs.pop()

    return None


def get_alternate_tags_paths(view, tags_file):
    """
    Search for additional tag files.

    Search for additional tag files to use, including those define by a
    ``search_paths`` file, the ``extra_tag_path`` setting and the
    ``extra_tag_files`` setting. This is mostly used for including library tag
    files.

    :param view: sublime text view
    :param tags_file: path to a tag file

    :returns: list of valid, existing paths to additional tag files to search
    """
    tags_paths = '%s_search_paths' % tags_file
    search_paths = [tags_file]

    # read and add additional tag file paths from file
    if os.path.exists(tags_paths):
        search_paths.extend(
            codecs.open(tags_paths, encoding='utf-8').read().split('\n'))

    # read and add additional tag file paths from 'extra_tag_paths' setting
    try:
        for (selector, platform), path in setting('extra_tag_paths'):
            if view.match_selector(view.sel()[0].begin(), selector):
                if sublime.platform() == platform:
                    search_paths.append(
                        os.path.join(
                            path, setting('tag_file')))
    except Exception as e:
        print(e)

    if os.path.exists(tags_paths):
        for extrafile in setting('extra_tag_files'):
            search_paths.append(
                os.path.normpath(
                    os.path.join(os.path.dirname(tags_file), extrafile)))

    # ok, didn't find the tags file under the viewed file.
    # let's look in the currently opened folder
    for folder in view.window().folders():
        search_paths.append(
            os.path.normpath(
                os.path.join(folder, setting('tag_file'))))
        for extrafile in setting('extra_tag_files'):
            search_paths.append(
                os.path.normpath(
                    os.path.join(folder, extrafile)))

    # use list instead of set  for keep order
    ret = []
    for path in search_paths:
        if path and (path not in ret) and os.path.exists(path):
            ret.append(path)
    return ret


def get_common_ancestor_folder(path, folders):
    """
    Get common ancestor for a file and a list of folders.

    :param path: path to file
    :param folders: list of folder paths

    :returns: path to common ancestor for files and folders file
    """
    old_path = ''  # must initialise to nothing due to lack of do...while
    path = os.path.dirname(path)

    while path != old_path:  # prevent continuing past root directory
        matches = [path for x in folders if x.startswith(path)]

        if matches:
            return max(matches)  # in case of multiple matches, return closest

        old_path = path
        path = os.path.dirname(path)  # go up one level

    return path  # return the root directory

# Scrolling functions


def find_with_scope(view, pattern, scope, start_pos=0, cond=True, flags=0):
    max_pos = view.size()
    while start_pos < max_pos:
        estrs = pattern.split(r'\ufffd')
        if(len(estrs) > 1):
            pattern = estrs[0]
        f = view.find(pattern, start_pos, flags)

        if not f or view.match_selector(f.begin(), scope) is cond:
            break
        else:
            start_pos = f.end()

    return f


def find_source(view, pattern, start_at, flags=sublime.LITERAL):
    return find_with_scope(view, pattern, 'string',
                           start_at, False, flags)


def follow_tag_path(view, tag_path, pattern):
    regions = [sublime.Region(0, 0)]

    for p in list(tag_path)[1:-1]:
        while True:  # .end() is BUG!
            regions.append(find_source(view, p, regions[-1].begin()))

            if ((regions[-1] in (None, regions[-2]) or
                 view.match_selector(regions[-1].begin(), ENTITY_SCOPE))):
                regions = [r for r in regions if r is not None]
                break

    start_at = max(regions, key=lambda r: r.begin()).begin() - 1

    # find the ex_command pattern
    pattern_region = find_source(
        view, '^' + escape_regex(pattern) + '$', start_at, flags=0)

    if setting('debug'):  # leave a visual trail for easy debugging
        regions = regions + ([pattern_region] if pattern_region else [])
        view.erase_regions('tag_path')
        view.add_regions('tag_path', regions, 'comment', '', 1)

    return pattern_region.begin() - 1 if pattern_region else None


def scroll_to_tag(view, tag, hook=None):
    @on_load(os.path.join(tag.root_dir, tag.filename))
    def and_then(view):
        do_find = True

        if tag.ex_command.isdigit():
            look_from = view.text_point(int(tag.ex_command) - 1, 0)
        else:
            look_from = follow_tag_path(view, tag.tag_path, tag.ex_command)
            if not look_from:
                do_find = False

        if do_find:
            search_symbol = tag.get('def_symbol', tag.symbol)
            symbol_region = view.find(
                escape_regex(search_symbol) + r"(?:[^_]|$)", look_from, 0)

        if do_find and symbol_region:
            # Using reversed symbol_region so cursor stays in front of the
            # symbol. - 1 to discard the additional regex part.
            select_region = sublime.Region(
                symbol_region.end() - 1, symbol_region.begin())
            select(view, select_region)
            if not setting('select_searched_symbol'):
                view.run_command('exit_visual_mode')
        else:
            status_message('Can\'t find "%s"' % tag.symbol)

        if hook:
            hook(view)

# Formatting helper functions


def format_tag_for_quickopen(tag, show_path=True):
    """
    Format a tag for use in quickopen panel.

    :param tag: tag to display in quickopen
    :param show_path: show path to file containing tag in quickopen

    :returns: formatted tag
    """
    format_ = []
    tag = ctags.TagElements(tag)
    f = ''

    for field in getattr(tag, 'field_keys', []):
        if field in PATH_ORDER:
            punct = OBJECT_PUNCTUATORS.get(field, ' -> ')
            f += string.Template(
                '    %($field)s$punct%(symbol)s').substitute(locals())

    format_ = [f % tag if f else tag.symbol, tag.ex_command]
    format_[1] = format_[1].strip()

    if show_path:
        format_.insert(1, tag.filename)

    return format_


def prepare_for_quickpanel(formatter=format_tag_for_quickopen):
    """
    Prepare list of matching ctags for the quickpanel.

    :param formatter: formatter function to apply to tag

    :returns: tuple containing tag and formatted string representation of tag
    """
    def compile_lists(sorter):
        args, display = [], []

        for t in sorter():
            display.append(formatter(t))
            args.append(t)

        return args, display

    return compile_lists

# File collection helper functions


def get_rel_path_to_source(path, tag_file, multiple=True):
    """
    Get relative path from tag_file to source file.

    :param path: path to a source file
    :param tag_file: path to a tag file
    :param multiple: if multiple tag files open

    :returns: list containing relative path from tag_file to source file
    """
    if multiple:
        return []

    tag_dir = os.path.dirname(tag_file)  # get tag directory
    common_prefix = os.path.commonprefix([tag_dir, path])
    relative_path = os.path.relpath(path, common_prefix)

    return [relative_path]


def get_current_file_suffix(path):
    """
    Get file extension

    :param path: path to a source file

    :returns: file extension for file
    """
    _, file_suffix = os.path.splitext(path)

    return file_suffix

#
# Sublime Commands
#

# JumpPrev Commands


class JumpPrev(sublime_plugin.WindowCommand):
    """
    Provide ``jump_back`` command.

    Command "jumps back" to the previous code point before a tag was navigated
    or "jumped" to.

    This is functionality supported natively by ST3 but not by ST2. It is
    therefore included for legacy purposes.
    """
    buf = deque(maxlen=100)  # virtually a "ring buffer"

    def is_enabled(self):
        # disable if nothing in the buffer
        return len(self.buf) > 0

    def is_visible(self):
        return setting('show_context_menus')

    def run(self):
        if not self.buf:
            return status_message('JumpPrev buffer empty')

        file_name, sel = self.buf.pop()
        self.jump(file_name, sel)

    def jump(self, path, sel):
        @on_load(path, begin_edit=True)
        def and_then(view):
            select(view, sel)

    @classmethod
    def append(cls, view):
        """Append a code point to the list"""
        name = view.file_name()
        if name:
            sel = [s for s in view.sel()][0]
            cls.buf.append((name, sel))

# CTags commands


def show_build_panel(view):
    """
    Handle build ctags command.

    Allows user to select whether tags should be built for the current file,
    a given directory or all open directories.
    """
    display = []

    if view.file_name() is not None:
        if not setting('recursive'):
            display.append(['Open File', view.file_name()])
        else:
            display.append([
                'Open File\'s Directory', os.path.dirname(view.file_name())])

    if len(view.window().folders()) > 0:
        # append option to build for all open folders
        display.append(
            ['All Open Folders', '; '.join(
                ['\'{0}\''.format(os.path.split(x)[1])
                 for x in view.window().folders()])])
        # Append options to build for each open folder
        display.extend(
            [[os.path.split(x)[1], x] for x in view.window().folders()])

    def on_select(i):
        if i != -1:
            if display[i][0] == 'All Open Folders':
                paths = view.window().folders()
            else:
                paths = display[i][1:]

            command = setting('command')
            recursive = setting('recursive')
            tag_file = setting('tag_file')
            opts = setting('opts')

            rebuild_tags = RebuildTags(False)
            rebuild_tags.build_ctags(paths, command, tag_file, recursive, opts)

    view.window().show_quick_panel(display, on_select)


def show_tag_panel(view, result, jump_directly):
    """
    Handle tag navigation command.

    Jump directly to a tag entry, or show a quick panel with a list of
    matching tags
    """
    if result not in (True, False, None):
        args, display = result
        if not args:
            return

        def on_select(i):
            if i != -1:
                JumpPrev.append(view)
                # Work around bug in ST3 where the quick panel keeps focus after
                # selecting an entry.
                # See https://github.com/SublimeText/Issues/issues/39
                view.window().run_command('hide_overlay')
                scroll_to_tag(view, args[i])

        if jump_directly and len(args) == 1:
            on_select(0)
        else:
            view.window().show_quick_panel(display, on_select)


def ctags_goto_command(jump_directly=False):
    """
    Decorator to goto a ctag entry.

    Allow jump to a ctags entry, directly or otherwise
    """
    def wrapper(func):
        def command(self, edit, **args):
            view = self.view
            tags_file = find_tags_relative_to(
                view.file_name(), setting('tag_file'))

            if not tags_file:
                status_message('Can\'t find any relevant tags file')
                return

            result = func(self, self.view, args, tags_file)
            show_tag_panel(self.view, result, jump_directly)

        return command
    return wrapper


def check_if_building(self, **args):
    """
    Check if ctags are currently being built.
    """
    if RebuildTags.build_ctags.func.running:
        status_message('Tags not available until built')
        if setting('display_rebuilding_message'):
            error_message('Please wait while tags are built')
        return False
    return True


# Goto definition under cursor commands

class JumpToDefinition:
    """
    Provider for NavigateToDefinition and SearchForDefinition commands.
    """
    @staticmethod
    def run(symbol, region, sym_line, mbrParts, view, tags_file):
        # print('JumpToDefinition')

        tags = {}
        for tags_file in get_alternate_tags_paths(view, tags_file):
            with TagFile(tags_file, SYMBOL) as tagfile:
                tags = tagfile.get_tags_dict(
                    symbol, filters=compile_filters(view))
            if tags:
                break

        if not tags:
            return status_message('Can\'t find "%s"' % symbol)

        rankmgr = RankMgr(region, mbrParts, view, symbol, sym_line)

        @prepare_for_quickpanel()
        def sorted_tags():
            taglist = tags.get(symbol, [])
            p_tags = rankmgr.sort_tags(taglist)
            if not p_tags:
                status_message('Can\'t find "%s"' % symbol)
            return p_tags

        return sorted_tags


class NavigateToDefinition(sublime_plugin.TextCommand):
    """
    Provider for the ``navigate_to_definition`` command.

    Command navigates to the definition for a symbol in the open file(s) or
    folder(s).
    """
    is_enabled = check_if_building

    def __init__(self, args):
        sublime_plugin.TextCommand.__init__(self, args)
        self.endings = re.compile(RUBY_SPECIAL_ENDINGS)

    def is_visible(self):
        return setting('show_context_menus')

    @ctags_goto_command(jump_directly=True)
    def run(self, view, args, tags_file):
        region = view.sel()[0]
        if region.begin() == region.end():  # point
            region = view.word(region)

            # handle special line endings for Ruby
            language = view.settings().get('syntax')
            endings = view.substr(
                sublime.Region(
                    region.end(),
                    region.end() + 1))

            if 'Ruby' in language and self.endings.match(endings):
                region = sublime.Region(region.begin(), region.end() + 1)
        symbol = view.substr(region)

        sym_line = view.substr(view.line(region))
        (row, col) = view.rowcol(region.begin())
        line_to_symbol = sym_line[:col]
        #print ("line_to_symbol %s" % line_to_symbol)
        source = get_source(view)
        arrMbrParts = Parser.extract_member_exp(line_to_symbol, source)
        return JumpToDefinition.run(
            symbol,
            region,
            sym_line,
            arrMbrParts,
            view,
            tags_file)


class SearchForDefinition(sublime_plugin.WindowCommand):
    """
    Provider for the ``search_for_definition`` command.

    Command searches for definition for a symbol in the open file(s) or
    folder(s).
    """
    is_enabled = check_if_building

    def is_visible(self):
        return setting('show_context_menus')

    def run(self):
        self.window.show_input_panel(
            '', '', self.on_done, self.on_change, self.on_cancel)

    def on_done(self, symbol):
        view = self.window.active_view()
        tags_file = find_tags_relative_to(
            view.file_name(), setting('tag_file'))

        if not tags_file:
            status_message('Can\'t find any relevant tags file')
            return

        result = JumpToDefinition.run(symbol, None, "", [], view, tags_file)
        show_tag_panel(view, result, True)

    def on_change(self, text):
        pass

    def on_cancel(self):
        pass

# Show Symbol commands

tags_cache = defaultdict(dict)


class ShowSymbols(sublime_plugin.TextCommand):
    """
    Provider for the ``show_symbols`` command.

    Command shows all symbols for the open file(s) or folder(s).
    """
    is_enabled = check_if_building

    def is_visible(self):
        return setting('show_context_menus')

    @ctags_goto_command()
    def run(self, view, args, tags_file):
        if not tags_file:
            return

        multi = args.get('type') == 'multi'
        lang = args.get('type') == 'lang'

        if view.file_name():
            files = get_rel_path_to_source(
                view.file_name(), tags_file, multi)

        if lang:
            suffix = get_current_file_suffix(view.file_name())
            key = suffix
        else:
            key = ','.join(files)

        tags_file = tags_file + '_sorted_by_file'
        base_path = get_common_ancestor_folder(
            view.file_name(), view.window().folders())

        def get_tags():
            with TagFile(tags_file, FILENAME) as tagfile:
                if lang:
                    return tagfile.get_tags_dict_by_suffix(
                        suffix, filters=compile_filters(view))
                elif multi:
                    return tagfile.get_tags_dict(
                        filters=compile_filters(view))
                else:
                    return tagfile.get_tags_dict(
                        *files, filters=compile_filters(view))

        if key in tags_cache[base_path]:
            print('loading symbols from cache')
            tags = tags_cache[base_path][key]
        else:
            print('loading symbols from file')
            tags = get_tags()
            tags_cache[base_path][key] = tags

        print(('loaded [%d] symbols' % len(tags)))

        if not tags:
            if multi:
                sublime.status_message(
                    'No symbols found **FOR CURRENT FOLDERS**; Try Rebuild?')
            else:
                sublime.status_message(
                    'No symbols found **FOR CURRENT FILE**; Try Rebuild?')

        path_cols = (0, ) if len(files) > 1 or multi else ()
        formatting = functools.partial(
            format_tag_for_quickopen, show_path=bool(path_cols))

        @prepare_for_quickpanel(formatting)
        def sorted_tags():
            return sorted(
                chain(*(tags[k] for k in tags)), key=iget('tag_path'))

        return sorted_tags

# Rebuild CTags commands


class RebuildTags(sublime_plugin.TextCommand):
    """
    Provider for the ``rebuild_tags`` command.

    Command (re)builds tag files for the open file(s) or folder(s), reading
    relevant settings from the settings file.
    """

    def run(self, edit, **args):
        """Handler for ``rebuild_tags`` command"""
        paths = []

        command = setting('command')
        recursive = setting('recursive')
        opts = setting('opts')
        tag_file = setting('tag_file')

        if 'dirs' in args and args['dirs']:
            paths.extend(args['dirs'])
            self.build_ctags(paths, command, tag_file, recursive, opts)
        elif 'files' in args and args['files']:
            paths.extend(args['files'])
            # build ctags and ignore recursive flag - we clearly only want
            # to build them for a file
            self.build_ctags(paths, command, tag_file, False, opts)
        elif (self.view.file_name() is None and
                len(self.view.window().folders()) <= 0):
            status_message('Cannot build CTags: No file or folder open.')
            return
        else:
            show_build_panel(self.view)

    @threaded(msg='Already running CTags!')
    def build_ctags(self, paths, command, tag_file, recursive, opts):
        """
        Build tags for the open file or folder(s).

        :param paths: paths to build ctags for
        :param command: ctags command
        :param tag_file: filename to use for the tag file. Defaults to ``tags``
        :param recursive: specify if search should be recursive in directory
            given by path. This overrides filename specified by ``path``
        :param opts: list of additional parameters to pass to the ``ctags``
            executable

        :returns: None
        """
        def tags_building(tag_file):
            """Display 'Building CTags' message in all views"""
            print(('Building CTags for %s: Please be patient' % tag_file))
            in_main(lambda: status_message('Building CTags for {0}: Please be'
                                           ' patient'.format(tag_file)))()

        def tags_built(tag_file):
            """Display 'Finished Building CTags' message in all views"""
            print(('Finished building %s' % tag_file))
            in_main(lambda: status_message('Finished building {0}'
                                           .format(tag_file)))()
            in_main(lambda: tags_cache[os.path.dirname(tag_file)].clear())()

        for path in paths:
            tags_building(path)

            try:
                result = ctags.build_ctags(path=path, tag_file=tag_file,
                                           recursive=recursive, opts=opts,
                                           cmd=command)
            except IOError as e:
                error_message(e.strerror)
                return
            except subprocess.CalledProcessError as e:
                if sublime.platform() == 'windows':
                    str_err = ' '.join(
                        e.output.decode('windows-1252').splitlines())
                else:
                    str_err = e.output.decode(
                        locale.getpreferredencoding()).rstrip()

                error_message(str_err)
                return
            except Exception as e:
                error_message(
                    "An unknown error occured.\nCheck the console for info.")
                raise e

            tags_built(result)

        GetAllCTagsList.ctags_list = []  # clear the cached ctags list

# Autocomplete commands


class GetAllCTagsList():
    """
    Cache all the ctags list.
    """
    ctags_list = []

    def __init__(self, list):
        self.ctags_list = list


class CTagsAutoComplete(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):
        if setting('autocomplete'):
            prefix = prefix.strip().lower()
            tags_path = view.window().folders()[0] + '/' + setting('tag_file')

            sub_results = [v.extract_completions(prefix)
                           for v in sublime.active_window().views()]
            sub_results = [(item, item) for sublist in sub_results
                           for item in sublist]  # flatten

            if GetAllCTagsList.ctags_list:
                results = [sublist for sublist in GetAllCTagsList.ctags_list
                           if sublist[0].lower().startswith(prefix)]
                results = sorted(set(results).union(set(sub_results)))

                return results
            else:
                tags = []

                # check if a project is open and the tags file exists
                if not (view.window().folders() and os.path.exists(tags_path)):
                    return tags

                if sublime.platform() == "windows":
                    prefix = ""
                else:
                    prefix = "\\"

                f = os.popen(
                    "awk \"{ print " + prefix + "$1 }\" \"" + tags_path + "\"")

                for i in f.readlines():
                    tags.append([i.strip()])

                tags = [(item, item) for sublist in tags
                        for item in sublist]  # flatten
                tags = sorted(set(tags))  # make unique
                GetAllCTagsList.ctags_list = tags
                results = [sublist for sublist in GetAllCTagsList.ctags_list
                           if sublist[0].lower().startswith(prefix)]
                results = sorted(set(results).union(set(sub_results)))

                return results

# Test CTags commands


class TestCtags(sublime_plugin.TextCommand):
    routine = None

    def run(self, edit, **args):
        if self.routine is None:
            self.routine = self.co_routine(self.view)
            next(self.routine)

    def __next__(self):
        try:
            next(self.routine)
        except Exception as e:
            print(e)
            self.routine = None

    def co_routine(self, view):
        tag_file = find_tags_relative_to(
            view.file_name(), setting('tag_file'))

        with codecs.open(tag_file, encoding='utf-8') as tf:
            tags = parse_tag_lines(tf, tag_class=TagElements)

        print('Starting Test')

        ex_failures = []
        line_failures = []

        for symbol, tag_list in list(tags.items()):
            for tag in tag_list:
                tag.root_dir = os.path.dirname(tag_file)

                def hook(av):
                    test_context = av.sel()[0]

                    if tag.ex_command.isdigit():
                        test_string = tag.symbol
                    else:
                        test_string = tag.ex_command
                        test_context = av.line(test_context)

                    if not av.substr(test_context).startswith(test_string):
                        failure = 'FAILURE %s' % pprint.pformat(tag)
                        failure += av.file_name()

                        if setting('debug'):
                            if not sublime.question_box('%s\n\n\n' % failure):
                                self.routine = None

                            return sublime.set_clipboard(failure)
                        ex_failures.append(tag)
                    sublime.set_timeout(self.__next__, 5)
                scroll_to_tag(view, tag, hook)
                yield

        failures = line_failures + ex_failures
        tags_tested = sum(len(v) for v in list(tags.values())) - len(failures)

        view = sublime.active_window().new_file()

        with Edit(view) as edit:
            edit.insert(view.size(), '%s Tags Tested OK\n' % tags_tested)
            edit.insert(view.size(), '%s Tags Failed' % len(failures))

        view.set_scratch(True)
        view.set_name('CTags Test Results')

        if failures:
            sublime.set_clipboard(pprint.pformat(failures))
