Git Pre-Receive Hook to Validate Commits
========================================

The developers tend to be obsessed about code style.  It is exhausting to edit
files again and again to have a consistent style.  This project provides
a Git pre-receive hook to validate pushed commits on the Git server side.
The hook avoids all issues by rejecting any commit with inconsistent style
to get in to the repository in the first place.

The pre-receive hook searches runs some checks on the commits on its own,
and searches for programming language specific syntax checkers on the PATH.
The process is pretty fast, because  only the changed files on the pushed
commits are passed to the syntax checkers in parallel.  It wouldn't slow you
down unless your commits are touching hundreds of files.


Installation
------------

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
* Check commit message best practices (80 lines, first line summary...)
* Check commit summary formatting
* Validate commit tags against a list ``[BUGFIX]``, ``[FEATURE]``, ``[WIP]``...
* Check for changed file paths
* Accept commits tagged as ``[HOTFIX]``, ``[MESS]`` or ``[WIP]`` with issues
* Check executable bits and shebangs
* Check CSS files with ``csslint``
* Check Go files with ``golint``
* Check HTML files with ``htmlhint``
* Check Puppet files with ``puppet parser validate`` and ``puppet-lint``
* Check Python files with ``flake8`` or ``pycodestyle`` and ``pyflakes``
* Check Ruby files with ``rubocop``
* Check shell scripts with ``shellcheck``
* Check JavaScript files with ``eslint``, ``jshint``, ``jscs``, or ``standard``
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
csslint         .csslintrc                                  optional
htmlhint        .htmlhintrc                                 optional
puppet-lint     .puppet-lint.rc                             optional
flake8          .flake8, setup.cfg, or tox.ini              optional
pycodestyle     setup.cfg, or tox.ini                       optional
eslint          eslint.(js|yaml|yml|json), or package.json  required
jshint          .jshintrc, or package.json                  optional
jscs            .jscsrc, .jscs.json, or package.json        required
phpcs           phpcs.xml, or phpcs.xml.dist                optional
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

The script has no dependencies on Python 3.4 or above.  It runs on Python 2
as well with the backport of enum library "enum34".  The script executes
the validation commands using the shell.  The necessary ones for checked
repositories need to be installed separately.  See the complete list of
commands on the `config.py <igcommit/config.py>`_.  The commands which are not
available on the ``PATH`` is not going to be used.


Testing
-------

I found it useful to check what the script would have complained if it would
be active on different Git repositories.  You can run a command like this
to test it on a Git repository against last 50 commits::

    git log --reverse --oneline HEAD~50..HEAD |
        sed 's:\([^ ]*\) .*:\1 \1 refs/heads/master:' |
        python ../igcommit/igcommit-receive


License
-------

The script is released under the MIT License.  The MIT License is registered
with and approved by the Open Source Initiative [1]_.

.. [1] https://opensource.org/licenses/MIT
