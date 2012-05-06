CTags
-----

CTags Sublime Text 2 Plugin with autocompletion love


Installation
------------

Install good ctags:

    brew install ctags
    brew link ctags

Install awk

    brew install awk

Clone to Packages

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


**Do not forget to add .tags and .tags_sorted_by_file to your .gitignore file**

