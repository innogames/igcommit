"""igcommit - Commit list logic

Copyright (c) 2016, InnoGames GmbH
"""

import fileinput

from igcommit.git import Commit, CommittedFile


class CommitList(list):
    """Routines on list of commits"""

    @classmethod
    def read_from_input(cls):
        """Build a commit list from the standart input"""
        commit_list = cls()
        for line in fileinput.input():
            commit_list.append(Commit(commit_list, line.split(None, 2)[1]))
        return commit_list

    def __str__(self):
        return '{}..{}'.format(self[0], self[-1])

    def expand_checks_all(self, checks):
        """Yield results for new commit lists accessible from """
        for commit in self:
            commit_list = CommitList()
            for commit_id in commit.get_new_commit_ids():
                commit_list.append(Commit(commit_list, commit_id))
            # Appending the actual commit on the list to the new ones makes
            # testing easier.
            if commit not in commit_list:
                commit_list.append(commit)
            for result in commit_list.expand_checks(checks):
                yield result

    def expand_checks(self, checks):
        """Expand the checks to the list, the commits and the files

        It yields the checks prepared and ready.
        """
        checks_for_commits = []
        for check in checks:
            check_prepared = check.for_commit_list(self)
            if check_prepared:
                if check_prepared.ready:
                    yield check_prepared
                else:
                    checks_for_commits.append(check_prepared)

        for commit in self:
            checks_for_files = []
            for check in checks_for_commits:
                check_prepared = check.for_commit(commit)
                if check_prepared:
                    if check_prepared.ready:
                        yield check_prepared
                    else:
                        checks_for_files.append(check_prepared)

            for changed_file in commit.get_changed_files():
                for check in checks_for_files:
                    check_prepared = check.for_committed_file(changed_file)
                    if check_prepared:
                        # No more objects to expand
                        assert check_prepared.ready
                        yield check_prepared


class Check(object):
    def __str__(self):
        return type(self).__name__

    def possible_on_commit(self, commit):
        return True

    def get_problems(self, checkable):
        raise NotImplementedError()


class Result(object):
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
            print('* ' + self.first_problem)
        for problem in self.problems:
            print('* ' + problem)
        print('')
