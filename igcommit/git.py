#!/usr/bin/env python
"""igcommit - InnoGames Commit Validation Script

This the pre-receive script for Git repositories to validate pushed commits
on the server side.

Copyright (c) 2016, InnoGames GmbH
"""

import fileinput
from subprocess import check_output


class CommitList(list):
    """Routines on list of commits"""

    @classmethod
    def build(cls, commit_ids):
        return cls(Commit(c) for c in commit_ids)

    @classmethod
    def read_from_input(cls):
        """Build a commit list from the standart input"""
        return cls.build(l.split(None, 2)[1] for l in fileinput.input())

    def __str__(self):
        return '{}..{}'.format(self[0], self[-1])

    def get_new_commits(self):
        """Get the list of parent new commits in order"""
        cmd = (
            'git rev-list {} --not --all'
            .format(' '.join(c.commit_id for c in self))
        )
        output = check_output(cmd, shell=True).decode()
        return CommitList.build(reversed(output.splitlines()))

    def get_all_new_commits(self):
        """Get the list of new commits with the current ones

        Appending the actual commits on the list to the new ones makes testing
        easier.
        """
        all_new_commits = self.get_new_commits()
        for commit in self:
            if commit not in all_new_commits:
                all_new_commits.append(commit)
        return all_new_commits

    def get_results(self, commit_list_checks, commit_checks, file_checks):
        """Check everything of the commit list"""
        for check in commit_list_checks:
            yield Result(self, check)

        failed_paths = []
        for commit in self:
            for check in commit_checks:
                yield Result(commit, check)

            changed_file_checks = [
                c for c in file_checks if c.relevant_on_commit(commit)
            ]

            for changed_file in commit.get_changed_files():
                # We are not bothering to check the files on the following
                # commits again, if the check already failed on them.
                if changed_file.path in failed_paths:
                    continue

                for check in changed_file_checks:
                    result = Result(changed_file, check)
                    yield result

                    if result.failed():
                        failed_paths.append(changed_file.path)

                        # It probably doesn't make sense to run the following
                        # checks on this file as the previous one failed.
                        break


class Commit():
    """Routines on a single commit"""
    null_commit_id = '0000000000000000000000000000000000000000'

    def __init__(self, commit_id):
        self.commit_id = commit_id
        self.message = None
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

    def get_changed_files(self):
        """Return the list of added or modified files on a commit"""
        if self.changed_files is None:
            cmd = (
                'git diff-tree -r --no-commit-id --name-only --break-rewrites '
                '--no-renames --diff-filter=AM {}'
                .format(self.commit_id)
            )
            self.changed_files = [
                CommittedFile(self, path)
                for path in check_output(cmd, shell=True).decode().splitlines()
            ]
        return self.changed_files


class CommittedFile():
    """Routines on a single committed file"""

    def __init__(self, commit, path):
        self.commit = commit
        self.path = path

    def __str__(self):
        return '{} at {}'.format(self.path, self.commit)

    def __eq__(self, other):
        return (
            isinstance(other, CommittedFile) and
            self.commit == other.commit and
            self.path == other.path
        )

    def exists(self):
        cmd = (
            'git ls-tree --name-only -r {} {}'
            .format(self.commit.commit_id, self.path)
        )
        return bool(check_output(cmd, shell=True))

    def changed(self):
        return self in self.commit.get_changed_files()

    def get_extension(self):
        return self.path.rsplit('.', 1)[-1]

    def get_content(self):
        """Return the content of a file on a commit as bytes"""
        cmd = 'git show {}:{}'.format(self.commit.commit_id, self.path)
        return check_output(cmd, shell=True)

    def write(self):
        with open(self.path, 'wb') as fd:
            fd.write(self.get_content())


class Result():
    """Lazy result to be reported to the user"""
    def __init__(self, checkable, check):
        self.checkable = checkable
        self.check = check
        self.problems = check.get_problems(checkable)
        # We have to buffer the first problem to see if there are any.
        self.first_problem = None

    def failed(self):
        if self.first_problem:
            return True
        for problem in self.problems:
            # Problem cannot be empty.
            assert problem
            self.first_problem = problem
            return True
        return False

    def can_soft_fail(self):
        return (
            isinstance(self.checkable, CommittedFile) and
            self.checkable.commit.can_soft_fail()
        )

    def print_section(self):
        print('=== {} on {} ==='.format(self.check, self.checkable))
        if self.first_problem:
            print('* {}'.format(self.first_problem))
        for problem in self.problems:
            print('* {}'.format(problem))
        print('')
