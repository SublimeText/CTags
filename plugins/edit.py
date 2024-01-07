"""
Buffer editing for both ST2 and ST3 that 'just works'.

Copyright, SublimeXiki project <https://github.com/lunixbochs/SublimeXiki>
"""

import inspect
import sublime
import sublime_plugin

try:
    sublime.edit_storage
except AttributeError:
    sublime.edit_storage = {}

def run_callback(func, *args, **kwargs):
    spec = inspect.getfullargspec(func)
    if spec.args or spec.varargs:
        func(*args, **kwargs)
    else:
        func()

class EditFuture:
    def __init__(self, func):
        self.func = func

    def resolve(self, view, edit):
        return self.func(view, edit)

class EditStep:
    def __init__(self, cmd, *args):
        self.cmd = cmd
        self.args = args

    def run(self, view, edit):
        if self.cmd == 'callback':
            return run_callback(self.args[0], view, edit)

        funcs = {
            'insert': view.insert,
            'erase': view.erase,
            'replace': view.replace,
        }
        func = funcs.get(self.cmd)
        if func:
            args = self.resolve_args(view, edit)
            func(edit, *args)

    def resolve_args(self, view, edit):
        args = []
        for arg in self.args:
            if isinstance(arg, EditFuture):
                arg = arg.resolve(view, edit)
            args.append(arg)
        return args

class Edit:
    def __init__(self, view):
        self.view = view
        self.steps = []

    def __nonzero__(self):
        return bool(self.steps)

    @classmethod
    def future(cls, func):
        return EditFuture(func)

    def step(self, cmd, *args):
        step = EditStep(cmd, *args)
        self.steps.append(step)

    def insert(self, point, string):
        self.step('insert', point, string)

    def erase(self, region):
        self.step('erase', region)

    def replace(self, region, string):
        self.step('replace', region, string)

    def sel(self, start, end=None):
        if end is None:
            end = start
        self.step('sel', start, end)

    def callback(self, func):
        self.step('callback', func)

    def run(self, view, edit):
        for step in self.steps:
            step.run(view, edit)

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        view = self.view
        if sublime.version().startswith('2'):
            edit = view.begin_edit()
            self.run(view, edit)
            view.end_edit(edit)
        else:
            key = str(hash(tuple(self.steps)))
            sublime.edit_storage[key] = self.run
            view.run_command('apply_edit', {'key': key})

class apply_edit(sublime_plugin.TextCommand):
    def run(self, edit, key):
        sublime.edit_storage.pop(key)(self.view, edit)
