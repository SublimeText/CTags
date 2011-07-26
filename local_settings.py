from os.path import join
import sublime

CTAGS_EXE = join(sublime.packages_path(), 'CTags', 'ctags.exe')
#CTAGS_CMD = [CTAGS_EXE, '-R', '--fields=fksl', '--languages=python,css,html']