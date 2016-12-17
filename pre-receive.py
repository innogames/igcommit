#!/usr/bin/env python
"""igcommit - InnoGames Commit Validation Script

This the pre-receive script for Git repositories to validate pushed commits
on the server side.

Copyright (c) 2016, InnoGames GmbH
"""
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the 'Software'), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import fileinput
from subprocess import check_output, Popen, PIPE, STDOUT


def configure():
    """The configuration of the checks

    This could go to a configuration file.
    """
    CommitList.checks = (
        CheckDuplicateCommitSummaries(),
    )
    Commit.checks = (
        CheckMisleadingMergeCommit(),
        CheckCommitMessage(),
        CheckCommitSummary(),
        CheckCommitTags(),
        CheckChangedFilePaths(),
    )
    ChangedFile.checks = (
        CheckCmd(
            'puppet parser validate --color=false '
            '--confdir=/tmp --vardir=/tmp',
            extension='pp',
        ),
        CheckCmd(
            'puppet-lint --fail-on-warnings --no-autoloader_layout-check '
            '/dev/stdin',
            extension='pp',
        ),
        CheckCmd(
            'flake8 /dev/stdin',
            extension='py',
        ),
        CheckCmdWithConfig(
            'jscs --max-errors=-1 --reporter=unix',
            extension='js',
            config_name='.jscs.json',
        ),
    )


def main():
    """The main program"""
    commits = CommitList.read_from_input()
    if not any(commits):
        raise SystemExit()
    if not all(commits):
        raise SystemExit('New commits with deletes')

    configure()
    failed = False
    for result in commits.check_all_new():
        if result.failed():
            result.print_section()
            if not result.can_soft_fail():
                failed = True

    if failed:
        raise SystemExit('Checks failed')


class Named(object):
    """Class to name object with its name"""
    def __str__(self):
        return type(self).__name__


class Checkable(Named):
    """Abstract class for check-ables"""
    checks = ()

    def check(self):
        """Execute the checks yielding the results"""
        for check in self.checks:
            yield Result(self, check)


class CommitList(list, Checkable):
    """Routines on list of commits"""

    @classmethod
    def build(cls, commit_ids):
        return cls(Commit(c) for c in commit_ids)

    @classmethod
    def read_from_input(cls):
        """Build a commit list from the standart input"""
        return cls.build(l.split(None, 2)[1] for l in fileinput.input())

    def check_all_new(self):
        """Check everything for all new commits

        We are checking the actual commits on the list too, even if they
        are not new.  This, at least, makes testing easier.
        """
        new_commits = self.get_new_commits()
        for commit in self:
            if commit not in new_commits:
                new_commits.append(commit)
        for result in new_commits.check_all():
            yield result

    def check_all(self):
        """Check everything of the commit list"""
        for result in self.check():
            yield result

        failed_paths = []
        for commit in self:
            for result in commit.check():
                yield result

            for changed_file in commit.get_changed_files():
                # We are not bothering to check the files on the following
                # commits again, if the check already failed on them.
                if changed_file.path in failed_paths:
                    continue

                for result in changed_file.check():
                    yield result

                    if result.failed():
                        failed_paths.append(changed_file.path)

                        # It probably doesn't make sense to run the following
                        # checks on this file as the previous one failed.
                        break

    def get_new_commits(self):
        """Get the list of parent new commits in order"""
        cmd = (
            'git rev-list {} --not --all'
            .format(' '.join(c.commit_id for c in self))
        )
        output = check_output(cmd, shell=True).decode()
        return CommitList.build(reversed(output.splitlines()))


class Commit(Checkable):
    null_commit_id = '0000000000000000000000000000000000000000'

    def __init__(self, commit_id):
        self.commit_id = commit_id
        self.message = None
        self.all_file_paths = None
        self.changed_files = None

    def __str__(self):
        return self.commit_id[:8]

    def __bool__(self):
        return self.commit_id != Commit.null_commit_id

    def __nonzero__(self):
        return self.__bool__()

    def __eq__(self, other):
        return isinstance(other, Commit) and self.commit_id == other.commit_id

    def get_message(self):
        if self.message is None:
            cmd = 'git log --format=%B -n 1 {}'.format(self.commit_id)
            output = check_output(cmd, shell=True).decode()
            self.message = output.strip()
        return self.message

    def get_summary(self):
        for line in self.get_message().splitlines():
            return line

    def parse_tags(self):
        tags = []
        rest = self.get_summary()
        while rest.startswith('[') and ']' in rest:
            end_index = rest.index(']')
            tags.append(rest[1:end_index])
            rest = rest[end_index + 1:]
        return tags, rest

    def can_soft_fail(self):
        return any(t in ('MESS', 'WIP') for t in self.parse_tags()[0])

    def get_all_file_paths(self):
        """Return the list of added or modified files on a commit"""
        if self.all_file_paths is None:
            cmd = 'git ls-tree --name-only -r {}'.format(self.commit_id)
            self.all_file_paths = set(
                check_output(cmd, shell=True).decode().splitlines()
            )
        return self.all_file_paths

    def file_exists(self, path):
        return path in self.get_all_file_paths()

    def get_changed_files(self):
        """Return the list of added or modified files on a commit"""
        if self.changed_files is None:
            cmd = (
                'git diff-tree -r --no-commit-id --name-only --break-rewrites '
                '--no-renames --diff-filter=AM {}'
                .format(self.commit_id)
            )
            self.changed_files = [
                ChangedFile(self, path)
                for path in check_output(cmd, shell=True).decode().splitlines()
            ]
        return self.changed_files

    def get_file_content(self, path):
        """Return the content of a file on a commit as bytes"""
        cmd = 'git show {}:{}'.format(self.commit_id, path)
        return check_output(cmd, shell=True)


class ChangedFile(Checkable):
    """Changed file to be checked"""

    def __init__(self, commit, path):
        self.commit = commit
        self.path = path

    def __str__(self):
        return '{} at {}'.format(self.path, self.commit)

    def get_extension(self):
        return self.path.rsplit('.', 1)[-1]

    def get_content(self):
        return self.commit.get_file_content(self.path)


class Result(object):
    """Lazy result to be reported to the user"""
    def __init__(self, checkable, check):
        self.checkable = checkable
        self.check = check
        self.generator = check(checkable)
        # We have to buffer the first line to see if there are any problems.
        self.first_line = None

    def failed(self):
        if self.first_line:
            return True
        for line in self.generator:
            self.first_line = line
            return True
        return False

    def can_soft_fail(self):
        return (
            isinstance(self.checkable, ChangedFile) and
            self.checkable.commit.can_soft_fail()
        )

    def print_section(self):
        print('=== {} on {} ==='.format(self.check, self.checkable))
        if self.first_line:
            print('* {}'.format(self.first_line))
        for line in self.generator:
            print('* {}'.format(line))
        print('')


class Check(Named):
    def __call__(self, checkable):
        pass


class CheckDuplicateCommitSummaries(Check):
    def __call__(self, commit_list):
        duplicate_summaries = [()]  # Nothing starts with an empty tuple.
        for commit in sorted(commit_list, key=Commit.get_summary):
            summary = commit.get_summary()
            if summary.startswith(duplicate_summaries[0]):
                duplicate_summaries.append(summary)
                continue
            if len(duplicate_summaries) > 1:
                for summary in duplicate_summaries:
                    yield summary
            duplicate_summaries = [summary]


class CheckMisleadingMergeCommit(Check):
    def __call__(self, commit):
        summary = commit.get_summary()
        if summary.startswith("Merge branch 'master'"):
            yield summary


class CheckCommitMessage(Check):
    def __call__(self, commit):
        for line_id, line in enumerate(commit.get_message().splitlines()):
            if line_id == 1 and line:
                yield 'has no summary'
            if line and line[-1] == ' ':
                yield 'line {} has trailing space'.format(line_id + 1)
            if line_id > 1 and line.startswith('    ') or line.startswith('>'):
                continue
            if len(line) >= 80:
                yield 'line {} is longer than 80'.format(line_id + 1)


class CheckCommitSummary(Check):
    def __call__(self, commit):
        tags, rest = commit.parse_tags()
        if '  ' in rest:
            yield 'multiple spaces'

        if rest.startswith('['):
            yield 'not terminated commit tags'
        if tags:
            if not rest.startswith(' '):
                yield 'commit tags not separated with space'
            rest = rest[1:]

        if rest.startswith('Revert'):
            rest = rest[len('Revert'):]
            if not rest.startswith(' "') or not rest.endswith('"'):
                yield 'ill-formatted revert commit'
            return

        if len(rest) > 72:
            yield 'summary longer than 72 characters'

        if ':' in rest[:24]:
            category, rest = rest.split(':', 1)
            if not category[0].isalpha():
                yield 'commit category start with non-letter'
            if category != category.lower():
                yield 'commit category has upper-case letter'
            if not rest.startswith(' '):
                yield 'commit category not separated with space'
            rest = rest[1:]

        if not rest:
            yield 'no summary'
        if not rest[0].isalpha():
            yield 'summary start with non-letter'
        if rest[-1] == '.':
            yield 'summary ends with a dot'

        first_word = rest.split(' ', 1)[0]
        if first_word.endswith('ed'):
            yield 'past tense used on summary'
        if first_word.endswith('ing'):
            yield 'continuous tense used on summary'


class CheckCommitTags(Check):
    tags = {
        'BUGFIX',
        'CLEANUP',
        'FEATURE',
        'HOTFIX',
        'MESS',
        'REFACTORING',
        'REVIEW'
        'SECURITY',
        'STYLE',
        'TASK',
        'WIP',
        '!!',
    }

    def __call__(self, commit):
        used_tags = []
        for tag in commit.parse_tags()[0]:
            tag_upper = tag.upper()
            if tag != tag_upper:
                yield 'commit tag [{}] not upper-case'.format(tag)
            if tag_upper not in CheckCommitTags.tags:
                yield 'commit tag [{}] not on list'.format(tag)
            if tag_upper in used_tags:
                yield 'duplicate commit tag [{}]'.format(tag)
            used_tags.append(tag_upper)


class CheckChangedFilePaths(Check):
    def __call__(self, commit):
        for changed_file in commit.get_changed_files():
            extension = changed_file.get_extension()
            if (
                extension in ('pp', 'py', 'sh') and
                changed_file.path != changed_file.path.lower()
            ):
                yield '{} has upper case'.format(changed_file)


class CheckCmd(Check):
    """Check command to be executed on file contents"""
    def __init__(self, cmd, extension=None):
        self.cmd = cmd
        self.extension = extension

    def __str__(self):
        binary = self.cmd.split(None, 1)[0]
        return '{} "{}"'.format(super(CheckCmd, self).__str__(), binary)

    def __call__(self, changed_file):
        if self.extension and self.extension != changed_file.get_extension():
            return
        process = Popen(
            self.cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT
        )
        content = changed_file.get_content()
        output = process.communicate(content)[0]
        if process.returncode != 0:
            for line in output.splitlines():
                yield line.decode().strip()


class CheckCmdWithConfig(CheckCmd):
    def __init__(self, cmd, config_name, **kwargs):
        super(CheckCmdWithConfig, self).__init__(cmd, **kwargs)
        self.config_name = config_name
        self.config_commit = None

    def __call__(self, changed_file):
        if changed_file.commit != self.config_commit:
            self.update_config(changed_file.commit)
        if not self.config_exists:
            return
        for line in super(CheckCmdWithConfig, self).__call__(changed_file):
            yield line

    def update_config(self, commit):
        self.config_commit = commit
        self.config_exists = commit.file_exists(self.config_name)
        if self.config_exists:
            with open(self.config_name, 'w') as fd:
                fd.write(commit.get_file_content(self.config_name))


if __name__ == '__main__':
    main()
