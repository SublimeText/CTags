"""
Mock module for ``sublime`` in Sublime Text.
"""

import sys

# find flags
LITERAL = 1
IGNORECASE = 2
WHOLEWORD = 4
REVERSE = 8
WRAP = 16


def arch():
    return 'x64'


def platform():
    if sys.platform == 'darwin':
        return 'osx'
    if sys.platform == 'win32':
        return 'windows'
    return 'linux'


def version():
    return '4126'


def load_settings(self, **kargs):
    pass


def status_message(msg):
    pass


def error_message(msg):
    pass
