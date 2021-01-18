Git Pre-Receive Hook to Validate Commits
========================================

It is exhausting to edit files again and again to have a consistent style.
This project provides a Git pre-receive hook to validate pushed commits on
the Git server side.  The hook avoids all issues by rejecting any commit
not matching the rules to get in to the repository in the first place.

The pre-receive hook runs some checks on commits on its own, and searches
for programming language specific syntax checkers on the PATH of the server
to check changed files with them.  The process is pretty fast, because only
the added and modified files on the pushed commits are passed to the syntax
checkers, also in parallel.  It wouldn't slow you down unless your commits
are touching hundreds of files.


Installation
------------

It is possible to install the tool with `pip`::

    pip install igcommit

Link the `script <igcommit-receive>`_ to ``hooks/pre-receive`` on you Git
repositories on your Git server::

    ln -s igcommit-receive /home/git/repositories/myproject.git/hooks/pre-receive


Features
--------

* Validate received commits one by one not just the last one
* Only validate added or modified files on the commits
* Report all problems before failing
* Check for duplicate commit summaries
* Check for misleading merge commits
* Validate committer and author timestamps
* Validate committer and author names and email addresses
* Check commit message best practices (80 lines, first line summary...)
* Check commit summary formatting
* Validate commit tags against a list ``[BUGFIX]``, ``[FEATURE]``, ``[WIP]``...
* Check for changed file paths
* Accept commits tagged as ``[HOTFIX]``, ``[MESS]``, ``[TEMP]``, or ``[WIP]``
  with issues
* Check executable bits and shebangs
* Check symlinks
* Check CSS files with ``csslint``
* Check Go files with ``golint``
* Check HTML files with ``htmlhint``
* Check Puppet files with ``puppet parser validate`` and ``puppet-lint``
* Check Python files with ``flake8`` or ``pycodestyle`` and ``pyflakes``
* Check Ruby files with ``rubocop``
* Check shell scripts with ``shellcheck``
* Check JavaScript files with ``eslint``, ``jshint``, ``jscs``, or ``standard``
* Check CoffeeScript files with ``coffeelint``
* Check PHP files with ``phpcs``
* Run the external check commands in parallel
* Validate JSON, XML, YAML file formats

Here is an example problem output::

    === CheckDuplicateCommitSummaries on CommitList ===
    ERROR: summary "Add nagios check for early expiration of licenses" duplicated 2 times

    === CheckCommitSummary on 31d0f6b ===
    WARNING: summary longer than 72 characters

    === CheckCommitSummary on 6bded65 ===
    WARNING: past tense used on summary

    === CheckCommand "flake8" on src/check_multiple.py at 6bded65 ===
    INFO: line 10 col 5: E225 missing whitespace around operator
    INFO: line 17 col 80: E501 line too long (122 > 79 characters)
    INFO: line 17 col 85: E203 whitespace before ','

    === CheckCommitMessage on 6fdbc00 ===
    WARNING: line 7 is longer than 80
    WARNING: line 9 is longer than 80


Configuration
-------------

The script itself is currently configuration free.  Though, some of the syntax
checkers called by the script uses or requires configurations.  Those
configuration files has to be on the top level of the Git repository.

==============  ==========================================  ========
Syntax Checker   Configuration File
==============  ==========================================  ========
coffeelint      coffeelint.json, or package.json            optional
csslint         .csslintrc                                  optional
eslint          eslint.(js|yaml|yml|json), or package.json  required
flake8          .flake8, setup.cfg, or tox.ini              optional
htmlhint        .htmlhintrc                                 optional
jscs            .jscsrc, .jscs.json, or package.json        required
jshint          .jshintrc, or package.json                  optional
phpcs           phpcs.xml, or phpcs.xml.dist                optional
puppet-lint     .puppet-lint.rc                             optional
pycodestyle     setup.cfg, or tox.ini                       optional
rubocop         .rubocop.yml                                optional
==============  ==========================================  ========


Pros and Cons of Pre-receive Hook
---------------------------------

Continuous Integration Server
    A continuous integration server can run such checks with the many other
    things it is doing.  Moving this job from it has many benefits:

    * Synchronous feedback
    * More efficient
    * Disallow any commit violating the rules

Pre-commit Hook
    Even though, pre-receive hook gives later feedback than pre-commit hook,
    it has many advantages over it:

    * No client side configuration
    * Plugins has to be installed only once to the Git server
    * Everybody gets the same checks
    * Enforcement, nobody can skip the checks
    * Commit checking (pre-commit hook only gets what is changed in the commit)

IDE Integration
    The same advantages compared to pre-commit hooks applies to IDE
    integration.  Though, IDE integration gives much sooner and nicer feedback,
    so it is still a good idea, even with the pre-receive hook.


Dependencies
------------

The script has no dependencies on Python 3.4 or above.  The script executes
the validation commands using the shell.  The necessary ones for checked
repositories need to be installed separately.  See the complete list of
commands on the `config.py <igcommit/config.py>`_.  The commands which are not
available on the ``PATH`` is not going to be used.


Testing
-------

I found it useful to check what the script would have complained if it had
been active on different Git repositories.  You can run a command like this
to test this inside a Git repository against last 50 commits::

    git log --reverse --oneline HEAD~50..HEAD |
        sed 's:\([^ ]*\) .*:\1 \1 refs/heads/master:' |
        python ../igcommit/igcommit-receive


Changes
-------

Version 2.0
    * Fix line numbers on syntax errors for executables being 1 off
    * Recognize and validate symlinks
    * Validate committer and author timestamps
    * Validate contributor names and email addresses
    * Reduce commit message line length limits
    * Complain about file extensions on executables

Version 2.1
    * Add [TEMP] to recognized commit tags
    * Fix getting the changes of the initial commit (Zheng Wei)
    * Fix various file descriptor leaks
    * Check commit summaries more strictly
    * Check shebangs of non-executable files too
    * Don't check on empty file contents
    * Improve unicode support on Python 2
    * Fix checking symlink targets

Version 2.2
    * Fix ``eslint`` configuration (Jerevia)
    * Accepts commits with ``[TEMP]`` with issues
    * Stop skipping empty files
    * Make sure not to get unknown file contents
    * Move file extensions to config
    * Increase timestamp comparison tolerance for 1 more minute
    * Handle spaces on shebangs

Version 2.3
    * Handle check command failing immediately
    * Support pushed tags
    * Fix failing on file check with bogus return code
    * Include list of commit tags on warning
    * Fix recognising commit tags ``[REVIEW]`` and ``[SECURITY]``

Version 2.4
    * Fix recognising removed configuration files
    * Support `coffeelint`

Version 2.5
    * Fix unicode issue on Python 2 for XML, YAML, and JSON (jcoetsie)

Version 3.0
    * Drop Python 2 support
    * Fix handling filenames with spaces (Friz-zy)

Version 3.1
    * Stop complaining about the same commit for Git tags
    * Fix checking contributor names and email addresses
    * Stop complaining about file extensions we don't know about
    * Filter out checking format of files under ``templates/`` directories
    * Improve code quality and style


License
-------

The script is released under the MIT License.  The MIT License is registered
with and approved by the Open Source Initiative [1]_.

.. [1] https://opensource.org/licenses/MIT
