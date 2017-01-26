#!/usr/bin/env python
"""igcommit - Configuration of the checks

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.commit_list_checks import (
    CheckDuplicateCommitSummaries,
    CheckMisleadingMergeCommit,
)
from igcommit.commit_checks import (
    CheckCommitMessage,
    CheckCommitSummary,
    CheckChangedFilePaths,
)
from igcommit.file_checks import CheckExecutable, CheckCommand
from igcommit.git import CommittedFile

checks = []

# Commit list checks
checks.append(CheckDuplicateCommitSummaries())
checks.append(CheckMisleadingMergeCommit())

# Commit checks
checks.append(CheckCommitMessage())
checks.append(CheckCommitSummary())
checks.append(CheckChangedFilePaths())

# File meta checks
checks.append(CheckExecutable())

# CSS
checks.append(CheckCommand(
    ['csslint', '--format=compact', '/dev/stdin'],
    extension='css',
    config_files=[CommittedFile('.csslintrc')],
))

# Go
checks.append(CheckCommand(['golint', '/dev/stdin'], extension='go'))

# Puppet
checks.append(CheckCommand(
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
checks.append(CheckCommand(
    ['puppet-lint', '--no-autoloader_layout-check', '/dev/stdin'],
    extension='pp',
    config_files=[CommittedFile('.puppet-lint.rc')],
))

# Python
setup_file = CommittedFile('setup.cfg')
tox_file = CommittedFile('tox.ini')
flake8_check = CheckCommand(
    ['flake8', '-'],
    extension='py',
    config_files=[setup_file, tox_file, CommittedFile('.flake8')],
)
checks.append(flake8_check)
checks.append(CheckCommand(
    ['pycodestyle', '-'],
    extension='py',
    config_files=[setup_file, tox_file],
    preferred_checks=[flake8_check],
))
checks.append(CheckCommand(
    ['pyflakes'],
    extension='py',
    preferred_checks=[flake8_check],
))

# Ruby
checks.append(CheckCommand(
    ['rubocop', '--format=emacs', '--stdin', '/dev/stdin'],
    extension='rb',
))

# Shell
checks.append(CheckCommand(
    ['shellcheck', '--format=gcc', '/dev/stdin'],
    extension='sh',
))

# JavaScript
package_config = CommittedFile('package.json')
eslint_check = CheckCommand(
    ['eslint', '--format=unix', '--quite', '--stdin'],
    extension='js',
    config_files=[
        package_config,
        CommittedFile('.eslint.js'),
        CommittedFile('.eslint.yaml'),
        CommittedFile('.eslint.yml'),
        CommittedFile('.eslint.json'),
    ],
    config_required=True,
)
checks.append(eslint_check)
jshint_check = CheckCommand(
    ['jshint', '--reporter=unix', '/dev/stdin'],
    extension='js',
    config_files=[package_config, CommittedFile('.jshintrc')],
    preferred_checks=[eslint_check],
)
checks.append(jshint_check)
jscs_check = CheckCommand(
    ['jscs', '--max-errors=-1', '--reporter=unix'],
    extension='js',
    config_files=[
        package_config,
        CommittedFile('.jscsrc'),
        CommittedFile('.jscs.json'),
    ],
    config_required=True,
    preferred_checks=[eslint_check, jshint_check],
)
checks.append(jscs_check)
checks.append(CheckCommand(
    ['standard', '--stdin'],
    extension='js',
    header=2,
    preferred_checks=[eslint_check, jshint_check, jscs_check],
))

# PHP
checks.append(CheckCommand(
    ['phpcs', '-q', '--report=emacs'],
    extension='php',
    config_files=[
        CommittedFile('phpcs.xml'),
        CommittedFile('phpcs.xml.dist'),
    ],
))
