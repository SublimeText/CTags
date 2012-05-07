CTags
-----

CTags Sublime Text 2 Plugin with autocompletion love. This plugin autocompletes from all open tabs and from .tags file.


Installation
------------

Install good ctags:

    brew install ctags
    brew link ctags

Install awk

    brew install awk

Clone to Packages

**Note**: remove CTags package from Package Control if you have it installed.

    rm -rf ~/Library/Application\ Support/Sublime\ Text\ 2/Packages/CTags
    git clone https://github.com/yury/CTags ~/Library/Application\ Support/Sublime\ Text\ 2/Packages/CTags
    
Keybindings
-----------

<table>
    <tr>
        <th>
            Command
        </th>
        <th>
            Key Binding
        </th>
        <th>
            Mouse Binding
        </th>
    </tr>
    <tr>
        <td>
            rebuild_ctags
        </td>
        <td>
            ctrl+shift+r
        </td>
        <td></td>
    </tr>
    <tr>
        <td>navigate_to_definition</td>
        <td>cmd+&gt;</td>
        <td>ctrl+shift+click</td>
    </tr>
    <tr>
        <td>jump_back</td>
        <td>cmd+&lt;</td>
        <td></td>
    </tr>
    <tr>
        <td>show_symbols</td>
        <td>alt+s</td>
        <td></td>
    </tr>
</table>

Basic CoffeeScript support
--------------------------

Drop [this](https://gist.github.com/1932675) to ~/.tags or [this](https://gist.github.com/2624883) for better class detection

Objective-C support
-------------------

See [Greg Sexton](http://www.gregsexton.org/2011/04/objective-c-exuberant-ctags-regex/) ctags regex

RubyMotion love
---------------

Add this rake task to your Rakefile

```ruby
desc "Generate ctags for sublime"
task :tags do
  config = App.config
  files = config.bridgesupport_files + config.vendor_projects.map { |p| Dir.glob(File.join(p.path, '*.bridgesupport')) }.flatten
  files += Dir.glob(config.project_dir + "/app/**/*").flatten
  files += Dir.glob(config.project_dir + "/spec/**/*").flatten
  tags_config = File.join(config.motiondir, 'data', 'bridgesupport-ctags.cfg')
  sh "ctags --options=\"#{tags_config}\" -f .tags #{files.map { |x| '"' + x + '"' }.join(' ')}"
end
```


**Do not forget to add .tags and .tags_sorted_by_file to your .gitignore file**

