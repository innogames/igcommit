#!/usr/bin/env python
"""igcommit - InnoGames Commit Validation Script

This the pre-receive script for Git repositories to validate pushed commits
on the server side.

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.git import CommitList
from igcommit import commit_checks, file_checks


commits = CommitList.read_from_input()
if not any(commits):
    raise SystemExit()
if not all(commits):
    raise SystemExit('New commits with deletes')

results = commits.get_all_new_commits().get_results(
    commit_list_checks=(
        commit_checks.CheckDuplicateCommitSummaries(),
    ),
    commit_checks=(
        commit_checks.CheckMisleadingMergeCommit(),
        commit_checks.CheckCommitMessage(),
        commit_checks.CheckCommitSummary(),
        commit_checks.CheckCommitTags(),
        commit_checks.CheckChangedFilePaths(),
    ),
    file_checks=(
        file_checks.CheckExe(),
        file_checks.CheckShebang(),
        file_checks.CheckShebangExe(),
        file_checks.CheckCmd(
            (
                'puppet',
                'parser',
                'validate',
                '--color=false',
                '--confdir=/tmp',
                '--vardir=/tmp',
            ),
            extension='pp',
        ),
        file_checks.CheckCmd(
            (
                'puppet-lint',
                '--fail-on-warnings',
                '--no-autoloader_layout-check',
                '/dev/stdin',
            ),
            extension='pp',
        ),
        file_checks.CheckCmd(
            ('flake8', '/dev/stdin'),
            extension='py',
        ),
        file_checks.CheckCmd(
            ('shellcheck', '--format=gcc', '/dev/stdin'),
            extension='sh',
        ),
        file_checks.CheckCmdWithConfig(
            ('jscs', '--max-errors=-1', '--reporter=unix', '/dev/stdin'),
            extension='js',
            config_name='.jscs.json',
        ),
    ),
)

failed = False
for result in results:
    if result.failed():
        result.print_section()
        if not result.can_soft_fail():
            failed = True

if failed:
    raise SystemExit('Checks failed')
