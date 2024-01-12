"""
A ctags plugin for Sublime Text.
"""
import sublime

if int(sublime.version()) < 3143:
    print("CTags requires Sublime Text 3143+")

else:
    import sys

    # Clear module cache to force reloading all modules of this package.
    prefix = __package__ + "."  # don't clear the base package
    for module_name in [
        module_name
        for module_name in sys.modules
        if module_name.startswith(prefix) and module_name != __name__
    ]:
        del sys.modules[module_name]
    del prefix
    del sys

    # Publish Commands and EventListeners
    from .plugins.cmds import (
        CTagsAutoComplete,
        NavigateToDefinition,
        RebuildTags,
        SearchForDefinition,
        ShowSymbols,
        TestCtags,
    )

    from .plugins.edit import apply_edit
