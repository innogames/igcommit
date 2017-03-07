"""igcommit - Configuration of the checks

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.commit_list_checks import (
    CheckDuplicateCommitSummaries,
    CheckMisleadingMergeCommit,
    CheckTimestamps,
    CheckContributors,
)
from igcommit.commit_checks import (
    CheckCommitMessage,
    CheckCommitSummary,
    CheckChangedFilePaths,
)
from igcommit.file_checks import (
    CheckExecutable,
    CheckSymlink,
    CheckCommand,
    CheckJSON,
    CheckXML,
    CheckYAML,
)
from igcommit.git import CommittedFile

checks = []

# Commit list checks
checks.append(CheckDuplicateCommitSummaries())
checks.append(CheckMisleadingMergeCommit())
checks.append(CheckTimestamps())
checks.append(CheckContributors())

# Commit checks
checks.append(CheckCommitMessage())
checks.append(CheckCommitSummary())
checks.append(CheckChangedFilePaths())

# File meta checks
checks.append(CheckExecutable())
checks.append(CheckSymlink())

# CSS
checks.append(CheckCommand(
    args=['csslint', '--format=compact', '/dev/stdin'],
    extension='css',
    config_files=[CommittedFile('.csslintrc')],
))

# Go
checks.append(CheckCommand(
    args=['golint', '/dev/stdin'],
    extension='go',
))

# HTML
checks.append(CheckCommand(
    args=['htmlhint', '--format=unix', '/dev/stdin'],
    extension='html',
    footer=2,
    config_files=[CommittedFile('.htmlhintrc')],
))

# Puppet
checks.append(CheckCommand(
    args=[
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
    args=['puppet-lint', '--no-autoloader_layout-check', '/dev/stdin'],
    extension='pp',
    config_files=[CommittedFile('.puppet-lint.rc')],
))

# Python
setup_file = CommittedFile('setup.cfg')
tox_file = CommittedFile('tox.ini')
flake8_check = CheckCommand(
    args=['flake8', '-'],
    extension='py',
    config_files=[setup_file, tox_file, CommittedFile('.flake8')],
)
checks.append(flake8_check)
checks.append(CheckCommand(
    args=['pycodestyle', '-'],
    extension='py',
    config_files=[setup_file, tox_file],
    preferred_checks=[flake8_check],
))
checks.append(CheckCommand(
    args=['pyflakes'],
    extension='py',
    preferred_checks=[flake8_check],
))

# Ruby
checks.append(CheckCommand(
    args=['rubocop', '--format=emacs', '--stdin', '/dev/stdin'],
    extension='rb',
))

# Shell
checks.append(CheckCommand(
    args=['shellcheck', '--format=gcc', '/dev/stdin'],
    extension='sh',
    bogus_return_code=True,
))

# JavaScript
package_config = CommittedFile('package.json')
eslint_check = CheckCommand(
    args=['eslint', '--format=unix', '--quite', '--stdin'],
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
    args=['jshint', '--reporter=unix', '/dev/stdin'],
    extension='js',
    config_files=[package_config, CommittedFile('.jshintrc')],
    preferred_checks=[eslint_check],
)
checks.append(jshint_check)
jscs_check = CheckCommand(
    args=['jscs', '--max-errors=-1', '--reporter=unix'],
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
    args=['standard', '--stdin'],
    extension='js',
    header=2,
    preferred_checks=[eslint_check, jshint_check, jscs_check],
))

# PHP
checks.append(CheckCommand(
    args=['phpcs', '-q', '--report=emacs'],
    extension='php',
    config_files=[
        CommittedFile('phpcs.xml'),
        CommittedFile('phpcs.xml.dist'),
    ],
))

# Data exchange formats
checks.append(CheckJSON())
checks.append(CheckXML())
checks.append(CheckYAML())
