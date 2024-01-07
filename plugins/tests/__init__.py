import sys

from . import mock_sublime
from . import mock_sublime_plugin

sys.modules["sublime"] = mock_sublime
sys.modules["sublime_plugin"] = mock_sublime_plugin
