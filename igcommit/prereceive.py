# -*- coding: utf-8 -*-
"""igcommit - Pre-receive hook routines

Copyright (c) 2016, InnoGames GmbH
"""

from __future__ import print_function, unicode_literals

from collections import defaultdict
from fileinput import input
from sys import stdout, stderr
from traceback import print_exc

from igcommit.base_check import CheckState, prepare_checks
from igcommit.config import checks
from igcommit.git import Commit
from igcommit.utils import iter_buffer


class Runner(object):
    def __init__(self):
        self.checked_commit_ids = set()
        self.changed_file_checks = defaultdict(list)

    def run(self):
        state = CheckState.NEW

        # We are buffering the checks to let them run parallel in
        # the background.  Parallelization only applies to the CheckCommands.
        # It has no overhead, because we have to run those commands the same
        # way externally, anyway.  We only have a limit to avoid consuming
        # too many processes.
        for check in iter_buffer(self.expand_checks(checks), 16):
            check.print_problems()
            assert check.state >= CheckState.DONE
            state = max(state, check.state)

        return state

    def expand_checks(self, checks):
        next_checks = []
        for check in prepare_checks(checks, None, next_checks):
            yield check

        for line in input():
            for check in self.expand_checks_to_input(next_checks, line):
                yield check

    def expand_checks_to_input(self, checks, line):
        line_split = line.split()
        ref_path_split = line_split[2].split('/', 2)
        if ref_path_split[0] != 'refs' or len(ref_path_split) != 3:
            # We have no idea what this is.
            return

        commit = Commit(line_split[1])
        if not commit:
            # This is a delete.  We don't check anything on deletes.
            return

        if ref_path_split[1] == 'heads':
            name = line_split[2]
            for check in self.expand_checks_to_branch(checks, commit, name):
                yield check
        elif ref_path_split[1] == 'tags':
            for check in self.expand_checks_to_commit(checks, commit):
                yield check

    def expand_checks_to_branch(self, checks, commit, name):
        commit_list = commit.get_new_commit_list(name)

        # Appending the actual commit on the list to the new ones makes
        # testing easier.
        if commit not in commit_list:
            commit_list.append(commit)

        for check in self.expand_checks_to_commit_list(checks, commit_list):
            yield check

    def expand_checks_to_commit_list(self, checks, commit_list):
        next_checks = []
        for check in prepare_checks(checks, commit_list, next_checks):
            yield check

        for commit in commit_list:
            if commit.commit_id not in self.checked_commit_ids:
                for check in self.expand_checks_to_commit(next_checks, commit):
                    yield check
                self.checked_commit_ids.add(commit.commit_id)

    def expand_checks_to_commit(self, checks, commit):
        next_checks = []
        for check in prepare_checks(checks, commit, next_checks):
            yield check

        for changed_file in commit.get_changed_files():
            for check in self.expand_checks_to_file(next_checks, changed_file):
                yield check

    def expand_checks_to_file(self, checks, changed_file):
        for check in self.changed_file_checks[changed_file.path]:
            assert check.state >= CheckState.CLONED
            # Wait for the check to run
            while check.state < CheckState.DONE:
                yield None
            if check.state >= CheckState.FAILED:
                return

        for check in prepare_checks(checks, changed_file):
            yield check
            self.changed_file_checks[changed_file.path].append(check)


def main():
    try:
        state = Runner().run()
    except Exception:
        # Flush the problems we have printed so far to avoid the traceback
        # appearing in between them.
        stdout.flush()
        print(file=stderr)
        print('An error occurred, but the commits are accepted.', file=stderr)
        print_exc()
    else:
        if state >= CheckState.FAILED:
            return 1

    return 0
