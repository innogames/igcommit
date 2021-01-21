"""igcommit - Configuration of the checks

Copyright (c) 2021 InnoGames GmbH
Portions Copyright (c) 2021 Emre Hasegeli
"""

from json import loads
from json.decoder import JSONDecodeError
from re import compile as re_compile
from xml.etree import ElementTree

from igcommit.commit_checks import (
    CheckChangedFilePaths,
    CheckCommitMessage,
    CheckCommitSummary,
)
from igcommit.commit_list_checks import (
    CheckContributors,
    CheckDuplicateCommitSummaries,
    CheckMisleadingMergeCommit,
    CheckTimestamps,
)
from igcommit.file_checks import (
    CheckCommand,
    CheckExecutable,
    CheckLoading,
    CheckSymlink,
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
file_extensions = {
    'coffee': re_compile('^coffee'),
    'php': re_compile('^php'),
    'pp': re_compile('^puppet'),
    'py': re_compile('^python'),
    'rb': re_compile('^ruby'),
    'sh': re_compile('sh$'),
    'js': re_compile('js$'),
}
checks.append(CheckExecutable(
    file_extensions=file_extensions,
    general_names=[
        'exec',
        'go',
        'install',
        'run',
        'setup',
    ],
))
checks.append(CheckSymlink())

# Language independent configuration files
setup_config = CommittedFile('setup.cfg')
tox_config = CommittedFile('tox.ini')
package_config = CommittedFile('package.json')

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
    exe_pattern=file_extensions['pp'],
))
checks.append(CheckCommand(
    args=['puppet-lint', '--no-autoloader_layout-check', '/dev/stdin'],
    extension='pp',
    exe_pattern=file_extensions['pp'],
    config_files=[CommittedFile('.puppet-lint.rc')],
))

# Python
flake8_check = CheckCommand(
    args=['flake8', '-'],
    extension='py',
    exe_pattern=file_extensions['py'],
    config_files=[setup_config, tox_config, CommittedFile('.flake8')],
)
checks.append(flake8_check)
checks.append(CheckCommand(
    args=['pycodestyle', '-'],
    extension='py',
    exe_pattern=file_extensions['py'],
    config_files=[setup_config, tox_config],
    preferred_checks=[flake8_check],
))
checks.append(CheckCommand(
    args=['pyflakes'],
    extension='py',
    exe_pattern=file_extensions['py'],
    preferred_checks=[flake8_check],
))

# Ruby
checks.append(CheckCommand(
    args=['rubocop', '--format=emacs', '--stdin', '/dev/stdin'],
    extension='rb',
    exe_pattern=file_extensions['rb'],
    config_files=[CommittedFile('.rubocop.yml')],
))

# Shell
checks.append(CheckCommand(
    args=['shellcheck', '--format=gcc', '/dev/stdin'],
    extension='sh',
    exe_pattern=file_extensions['sh'],
    bogus_return_code=True,
))

# JavaScript
eslint_check = CheckCommand(
    args=['eslint', '--format=unix', '--quiet', '--stdin'],
    extension='js',
    exe_pattern=file_extensions['js'],
    config_files=[
        package_config,
        CommittedFile('.eslint.js'),
        CommittedFile('.eslint.yaml'),
        CommittedFile('.eslint.yml'),
        CommittedFile('.eslint.json'),
        CommittedFile('.eslintrc.js'),
        CommittedFile('.eslintrc.yaml'),
        CommittedFile('.eslintrc.yml'),
        CommittedFile('.eslintrc.json'),
    ],
    config_required=True,
)
checks.append(eslint_check)
jshint_check = CheckCommand(
    args=['jshint', '--reporter=unix', '/dev/stdin'],
    extension='js',
    exe_pattern=file_extensions['js'],
    config_files=[package_config, CommittedFile('.jshintrc')],
    preferred_checks=[eslint_check],
)
checks.append(jshint_check)
jscs_check = CheckCommand(
    args=['jscs', '--max-errors=-1', '--reporter=unix'],
    extension='js',
    exe_pattern=file_extensions['js'],
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
    exe_pattern=file_extensions['js'],
    header=2,
    preferred_checks=[eslint_check, jshint_check, jscs_check],
))

# CoffeeScript
checks.append(CheckCommand(
    args=['coffeelint', '--stdin', '--reporter=csv'],
    extension='coffee',
    exe_pattern=file_extensions['coffee'],
    header=1,
    config_files=[CommittedFile('coffeelint.json'), package_config],
))

# PHP
checks.append(CheckCommand(
    args=['phpcs', '-q', '--report=emacs'],
    extension='php',
    exe_pattern=file_extensions['php'],
    config_files=[
        CommittedFile('phpcs.xml'),
        CommittedFile('phpcs.xml.dist'),
    ],
))

# Data exchange formats
checks.append(CheckLoading(
    extension='json',
    # We need lambda to add the .decode() call, because json.loads()
    # on Python 3 versions before 3.6 doesn't accept bytes as input.
    # TODO: Remove once we don't support Python 3.5
    load_func=lambda s: loads(s.decode('utf-8')),
    exception_cls=JSONDecodeError,
))
checks.append(CheckLoading(
    extension='xml',
    load_func=ElementTree.fromstring,
    exception_cls=ElementTree.ParseError,
))
try:
    from yaml import YAMLError, load
except ImportError:
    pass
else:
    checks.append(CheckLoading(
        extension='yaml',
        load_func=load,
        exception_cls=YAMLError,
    ))
