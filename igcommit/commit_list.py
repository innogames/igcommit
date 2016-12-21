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

    def get_all_new_commit_results(self, *args, **kwargs):
        """Yield results for new commit lists accessible from """
        for commit in self:
            commit_list = CommitList()
            for commit_id in commit.get_new_commit_ids():
                commit_list.append(Commit(commit_list, commit_id))
            # Appending the actual commit on the list to the new ones makes
            # testing easier.
            if commit not in commit_list:
                commit_list.append(commit)
            for result in commit_list.get_results(*args, **kwargs):
                yield result

    def get_results(self, commit_list_checks, commit_checks, file_checks):
        """Yield results for everything of the commit list"""
        for check in commit_list_checks:
            yield Result(self, check)

        failed_paths = []
        for commit in self:
            for check in commit_checks:
                yield Result(commit, check)

            checks = [c for c in file_checks if c.possible_on_commit(commit)]
            for changed_file in commit.get_changed_files():
                # We are not bothering to check the files on the following
                # commits again, if the check already failed on them.
                if changed_file.path in failed_paths:
                    continue

                for check in checks:
                    if not check.possible_on_file(changed_file):
                        continue

                    result = Result(changed_file, check)
                    yield result

                    if result.failed():
                        failed_paths.append(changed_file.path)

                        # It probably doesn't make sense to run the following
                        # checks on this file as the previous one failed.
                        break


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
