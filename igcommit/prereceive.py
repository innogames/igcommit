"""igcommit - Pre-receive hook routines

Copyright (c) 2016, InnoGames GmbH
"""

from fileinput import input

from igcommit.git import Commit


def run(checks):
    """Yield prepared checks for every new object"""
    checked_commit_ids = set()
    for commit_list in read_prereceive_input():
        commit_checks = []
        for check in expand_checks(checks, commit_list, commit_checks):
            yield check

        for commit in commit_list:
            if commit.commit_id in checked_commit_ids:
                continue

            file_checks = []
            for check in expand_checks(commit_checks, commit, file_checks):
                yield check

            for changed_file in commit.get_changed_files():
                for check in expand_checks(file_checks, changed_file):
                    yield check

            checked_commit_ids.add(commit.commit_id)


def read_prereceive_input():
    """Yield commit lists from the standart input"""
    for line in input():
        commit = Commit(line.split(None, 2)[1])
        if not commit:
            continue

        commit_list = commit.get_new_commit_list()

        # Appending the actual commit on the list to the new ones makes
        # testing easier.
        if commit not in commit_list:
            commit_list.append(commit)

        yield commit_list


def expand_checks(checks, obj, next_checks=None):
    """Expand the checks to the object

    It yields the checks prepared and ready.  The checks which are not ready
    yet are going do be appended to the next_checks list.
    """
    for check in checks:
        prepared_check = check.prepare(obj)
        if prepared_check:
            assert next_checks is not None or prepared_check.ready

            if prepared_check.ready:
                yield prepared_check
            else:
                next_checks.append(prepared_check)
