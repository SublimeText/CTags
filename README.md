# CTags

![CI](https://github.com/SublimeText/CTags/actions/workflows/ci.yaml/badge.svg)

This [Sublime Text][] package provides support for working with tags generated
by [Exuberant CTags][] or [Universal CTags][].

`ctags` command is searched for on the system PATH. It works by doing a binary
search of a memory-mapped tags file, so it will work efficiently with very large
(50MB+) tags files if needed.


## Installation

### Package Control

The easiest way to install is using [Package Control][]. It's listed as `CTags`.

1. Open `Command Palette` using menu item `Tools → Command Palette...`
2. Choose `Package Control: Install Package`
3. Find `CTags` and hit `Enter`

### Manual Download

1. [Download the `.zip`][release]
2. Unzip and rename folder to `CTags`
3. Copy folder into `Packages` directory, 
   which can be found using the menu item `Preferences → Browse Packages...`

### Using Git

Go to your Sublime Text Packages directory and clone the repository
using the command below::

```sh
git clone https://github.com/SublimeText/CTags
```


## Additional Setup Steps

### Linux

To install ctags use your package manager. 

* For Debian-based systems (Ubuntu, Mint, etc.)::

  ```sh
  sudo apt-get install exuberant-ctags
  ```

  or

  ```sh
  sudo apt-get install universal-ctags
  ```

* For Red Hat-based systems (Red Hat, Fedora, CentOS)::

  ```sh
  sudo yum install ctags  
  ```
 
### MacOS

The default `ctags` executable in OSX does not support recursive directory
search (i.e. `ctags -R`). To get a proper copy of ctags, use one of the
following options:

* Using [Homebrew][]

  ```sh
  brew install ctags
  ```

* Using [MacPorts][]
  
  ```sh
  port install ctags  
  ```
  
Ensure that the `PATH` is updated so the correct version is run:

* If `which ctags` doesn't point at ctags in `/usr/local/bin`, make sure
  you add `/usr/local/bin` to your `PATH` ahead of the folder 
  `which ctags` reported.
* Alternatively, add the path to the new `ctags` executable to the settings,
  under `command`. If you have Xcode / Apple Developer Tools installed this
  path will likely be `/usr/local/bin/ctags`.
 
### Windows

* Download [Exuberant CTags binary][] or [Universal CTags binary][]

* Extract `ctags.exe` from the downloaded zip to 
  `C:\Program Files\Sublime Text` or any folder within your PATH so that
  Sublime Text can run it.

* Alternatively, extract to any folder and add the path to this folder to
  the `command` setting.


## Usage

This uses tag files created by the `ctags -R -f .tags` command by default
(although this can be overridden in settings).

The plugin will try to find a `.tags` file in the same directory as the
current view, walking up directories until it finds one. If it can't find one
it will offer to build one (in the directory of the current view)

If a symbol can't be found in a tags file, it will search in additional
locations that are specified in the `CTags.sublime-settings` file (see 
below).

If you are a Rubyist, you can build a Ruby Gem's tags with the following
script:

```ruby
require 'bundler'
paths = Bundler.load.specs.map(&:full_gem_path)
system("ctags -R -f .gemtags #{paths.join(' ')}")
```


## Settings

To open CTags.sublime-settings

1. Open `Command Palette` using menu item `Tools → Command Palette...`
2. Choose `Preferences: CTags Settings` and hit `Enter`

---

* `filters` will allow you to set scope specific filters against a field of
  the tag. In the excerpt above, imports tags like `from a import b` are 
  filtered:

  ```
  '(?P<symbol>[^\t]+)\t'
  '(?P<filename>[^\t]+)\t'
  '(?P<ex_command>.*?);"\t'
  '(?P<type>[^\t\r\n]+)'
  '(?:\t(?P<fields>.*))?'
  ```

* `extra_tag_paths` is a list of extra places to look for keyed by 
* `(selector, platform)`. Note the `platform` is tested against 
  `sublime.platform()` so any values that function returns are valid.
* `extra_tag_files` is a list of extra files relative to the original file
* `command` is the path to the version of ctags to use, for example::

  ```jsonc
  "command" : "/usr/local/bin/ctags"  
  ```
  
  or:

  ```jsonc
  "command" : "C:\\Users\\<username>\\Downloads\\CTags\\ctag.exe"
  ```

The rest of the options are fairly self explanatory.

### Hide .tags files from side bar

By default, Sublime will include ctags files in your project, which causes
them to show up in the file tree and search results. To disable this behaviour
you should add a `file_exclude_patterns` entry to your 
`Preferences.sublime-settings` or your project file. For example:

```jsonc
"file_exclude_patterns": [".tags", ".tags_sorted_by_file", ".gemtags"]
```


## Support

If there are any problems or you have a suggestion, [open an issue][issues], and
we will receive a notification.


## Commands Listing

| Command                      | Key Binding                 | Alt Binding          | Mouse Binding
|---                           |---                          |---                   |---
| rebuild_ctags                | <kbd>ctrl+t, ctrl+r</kbd>   |                      |
| navigate_to_definition       | <kbd>ctrl+t, ctrl+t</kbd>   | <kbd>ctrl+&gt;</kbd> | <kbd>ctrl+shift+left_click</kbd>
| jump_back                    | <kbd>ctrl+t, ctrl+b</kbd>   | <kbd>ctrl+&lt;</kbd> | <kbd>ctrl+shift+right_click</kbd>
| show_symbols                 | <kbd>alt+s</kbd>            |                      |
| show_symbols (all files)     | <kbd>alt+shift+s</kbd>      |                      |
| show_symbols (suffix)        | <kbd>ctrl+alt+shift+s</kbd> |                      |


[issues]: https://github.com/SublimeText/CTags/issues
[release]: https://github.com/SublimeText/CTags/releases/latest

[Sublime Text]: http://sublimetext.com/
[Package Control]: http://packagecontrol.io/

[Exuberant CTags]: http://ctags.sourceforge.net/
[Exuberant CTags binary]: http://prdownloads.sourceforge.net/ctags/ctags58.zip

[Universal CTags]: https://github.com/universal-ctags/ctags
[Universal CTags binary]: https://github.com/universal-ctags/ctags-win32/releases/latest

[Homebrew]: https://brew.sh/
[MacPorts]: https://www.macports.org/
