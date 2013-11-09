class sublime(object):

    '''Constants'''

    LITERAL = ''
    VERSION = '2.0'

    '''Functions'''

    def load_settings(self, **kargs):
        pass

    @staticmethod
    def version():
        return sublime.VERSION


class sublime_plugin(object):

    '''Constants'''

    all_callbacks = {
        'on_load': []
    }

    '''Classes'''

    class WindowCommand(object):
        pass

    class TextCommand(object):
        pass

    class EventListener(object):
        pass
