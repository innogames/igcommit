"""igcommit - Commit list logic

Copyright (c) 2016, InnoGames GmbH
"""

import fileinput

from igcommit.git import Commit


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
        used_commit_ids = set()
        for commit in self:
            if not commit:
                continue

            commit_list = CommitList()
            for commit_id in commit.get_new_commit_ids():
                if commit_id not in used_commit_ids:
                    commit_list.append(Commit(commit_list, commit_id))
                    used_commit_ids.add(commit_id)

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
