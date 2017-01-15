#!/usr/bin/env python
"""igcommit - Configuration of the checks

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit import commit_list_checks, commit_checks, file_checks

checks = []

# Commit list checks
checks.append(commit_list_checks.CheckDuplicateCommitSummaries())
checks.append(commit_list_checks.CheckMisleadingMergeCommit())

# Commit checks
checks.append(commit_checks.CheckCommitMessage())
checks.append(commit_checks.CheckCommitSummary())
checks.append(commit_checks.CheckCommitTags())
checks.append(commit_checks.CheckChangedFilePaths())

# File meta checks
checks.append(file_checks.CheckExecutable())

# Go
checks.append(file_checks.CheckCommand(
    ['golint', '/dev/stdin'],
    extension='go',
))

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
jscs_check = file_checks.CheckCommandWithConfig(
    ['jscs', '--max-errors=-1', '--reporter=unix'],
    extension='js',
    config_name='.jscs.json',
    config_required=True,
)
checks.append(jscs_check)
checks.append(file_checks.CheckCommand(
    ['standard', '--stdin'],
    extension='js',
    header=2,
    preferred_checks=[jscs_check],
))

# PHP
checks.append(file_checks.CheckCommandWithConfig(
    ['phpcs', '-q', '--report=emacs'],
    extension='php',
    config_name='phpcs.xml',
))
