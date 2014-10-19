class sublime(object):
    """
    Mock object for ``sublime`` class in Sublime Text.
    """
    LITERAL = ''
    VERSION = '2.0'

    def load_settings(self, **kargs):
        pass

    @staticmethod
    def version():
        return sublime.VERSION

class sublime_plugin(object):
    """
    Mock object for ``sublime_plugin`` class in Sublime Text.
    """
    all_callbacks = {
        'on_load': []
    }

    class WindowCommand(object):
        pass

    class TextCommand(object):
        pass

    class EventListener(object):
        pass
