#!/usr/bin/env python
"""igcommit - Configuration of the checks

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit import commit_checks, file_checks

checks = []

# Commit checks
checks.append(commit_checks.CheckDuplicateCommitSummaries())
checks.append(commit_checks.CheckMisleadingMergeCommit())
checks.append(commit_checks.CheckCommitMessage())
checks.append(commit_checks.CheckCommitSummary())
checks.append(commit_checks.CheckCommitTags())
checks.append(commit_checks.CheckChangedFilePaths())

# File meta checks
checks.append(file_checks.CheckExecutable())

# Puppet
checks.append(file_checks.CheckCommand(
    [
        'puppet',
        'parser',
        'validate',
        '--color=false',
        '--confdir=/tmp',
        '--vardir=/tmp',
    ],
    extension='pp',
))
checks.append(file_checks.CheckCommandWithConfig(
    ['puppet-lint', '--no-autoloader_layout-check', '/dev/stdin'],
    extension='pp',
    config_name='.puppet-lint.rc',
))

# Python
flake8_check = file_checks.CheckCommandWithConfig(
    ['flake8', '-'],
    extension='py',
    config_name='.flake8',
)
checks.append(flake8_check)
checks.append(file_checks.CheckCommand(
    ['pycodestyle', '-'],
    extension='py',
    preferred_checks=[flake8_check],
))
checks.append(file_checks.CheckCommand(
    ['pyflakes'],
    extension='py',
    preferred_checks=[flake8_check],
))

# Ruby
checks.append(file_checks.CheckCommand(
    ['rubocop', '--format=emacs', '--stdin', '/dev/stdin'],
    extension='rb',
))

# Shell
checks.append(file_checks.CheckCommand(
    ['shellcheck', '--format=gcc', '/dev/stdin'],
    extension='sh',
))

# JavaScript
checks.append(file_checks.CheckCommandWithConfig(
    ['jscs', '--max-errors=-1', '--reporter=unix'],
    extension='js',
    config_name='.jscs.json',
    config_required=True,
))

# PHP
checks.append(file_checks.CheckCommandWithConfig(
    ['phpcs', '-q', '--report=emacs'],
    extension='php',
    config_name='phpcs.xml',
))
