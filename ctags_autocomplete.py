# CTags based autocompletion plugin for Sublime Text 2
# You can add the file to the User Package in ~/Library/Application Support/Sublime Text 2/Packages and restart Sublime Text 2.
# generate the .tags file in your project root with "ctags -R -f .tags"

import sublime, sublime_plugin, os

class AutocompleteAll(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):
        window = sublime.active_window()
        # get results from each tab
        results = [v.extract_completions(prefix) for v in window.views() if v.buffer_id() != view.buffer_id()]
        results = [(item,item) for sublist in results for item in sublist] #flatten
        results = list(set(results)) # make unique

        # get results from tags
        tags_path = view.window().folders()[0]+"/.tags"

        if (not view.window().folders() or not os.path.exists(tags_path)): #check if a project is open and the .tags file exists
            return results
        prefix = prefix.replace("'", "''")
        count = 100
        f=os.popen("grep -i '^"+prefix+"' '"+tags_path+"' | awk 'uniq[$1] == 0 && i < " + str(count) + " { print $1; uniq[$1] = 1; i++ }'") # grep tags from project directory .tags file
        for i in f.readlines():
            results.append([i.strip()])
        return results