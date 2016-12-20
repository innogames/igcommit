InnoGames Commit Validation Script
==================================

The repository provides a Git pre-receive hook to validate pushed commits on
the server side.

Features
--------

* Validate received commits one by one not just the last one
* Only validate added or modified files on the commits
* Report all problems before failing
* Check for duplicate commit summaries
* Check for misleading merge commits
* Check commit message best practices (80 lines, first line summary...)
* Check commit summary formatting
* Validate commit tags against a list `[BUGFIX]`, `[FEATURE]`, `[WIP]`...
* Check for changed file paths
* Accept commits tagged as `[WIP]` or `[MESS]` with issues 
* Check executable bits and shebangs
* Check Puppet files with `puppet parser validate` and `puppet-lint`
* Check Python files with `flake8`
* Check shell scripts with `shellcheck`
* Check JavaScript files with `jscs` (requires `.jscs.json` on repository)

Here is an example problem output:

```
=== CheckDuplicateCommitSummaries on CommitList ===
* Add nagios check for early expiration of licenses
* Add nagios check for early expiration of licenses for Jira (#18)

=== CheckCommitSummary on 31d0f6b ===
* summary longer than 72 characters

=== CheckCommitSummary on 6bded65 ===
* past tense used on summary

=== CheckCmd "flake8" on src/check_multiple.py at 6bded65 ===
* line 7:80: E501 line too long (140 > 79 characters)
* line 8:80: E501 line too long (201 > 79 characters)
* line 9:80: E501 line too long (106 > 79 characters)
* line 10:5: E225 missing whitespace around operator
* line 17:80: E501 line too long (122 > 79 characters)
* line 17:85: E203 whitespace before ','

=== CheckCommitMessage on 6fdbc00 ===
* line 7 is longer than 80
* line 9 is longer than 80
```

Dependencies
------------

The script has no dependencies other than Python 2.7, 3.3 or above.  It runs
the validation commands using the shell.  The necessary ones for checked
repositories need to be installed separately.  See the complete list of
commands on the [script](pre-receive.py).  The commands which are not available
on the `PATH` is not going to be used.

Installation
------------

Link the [script](pre-receive.py) to `hooks/pre-receive` on you Git
repositories on your Git server:

```shell
ln -s pre-receive.py /home/git/repositories/myproject.git/hooks/pre-receive
```

FAQ
---

### Why should I check my commits?

The developers tend to be obsessed about code style.  It is exhausting
to edit files again and again to have a consistent style.  The pre-receive
hook avoid these by rejecting any commit with inconsistent style to get
in to the repository in the first place.

### But our continuous integration server runs the tests

The pre-receive hook is more practical than a continuous integration server
to run these tests, because it gives immediate feedback.  Besides, it checks
every commit one by one.  Continuous integration server would check the state
on the last commit letting intermediate commits with bad style in to
the repository.  The hook is also more efficient to run these tests, because
it only checks the changed files.

### But we do code reviews

Those problems can be easily caught by doing code reviews, but it is time
consuming for the reviewer and the author.  The pre-receive hook reject such
problems before anyone can even see them, so you can concentrate more
important details on code reviews.

### But my IDE warns me anyway

The even more efficient way to address that problem is IDE integration, but
IDEs are not restrictive.  The pre-receive hook would reject you on the server
side in case something went wrong.

### But it would slow pushing down

The pre-receive hook is pretty fast because it only checks the changed files
on the pushed commits.  It wouldn't slow you down unless your commits are
touching hundreds of files.

Testing
-------

I found it useful to check what the script would have complained if it would
be active on different Git repositories.  You can run a command like this
to test it on a Git repository against last 50 commits:

```shell
git log --oneline HEAD~50..HEAD | sed 's/^/x /' | python ../igcommit/pre-receive.py
```

Contributing
------------

Pull requests are welcome.  The script itself is currently configuration free.
It would be nice, if you can design your feature in a way it would work
for most people without any configuration.

License
-------

The script is released under the MIT License.  The MIT License is registered
with and approved by the Open Source Initiative [1].

[1] https://opensource.org/licenses/MIT
