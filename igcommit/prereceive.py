"""igcommit - Pre-receive hook routines

Copyright (c) 2021 InnoGames GmbH
Portions Copyright (c) 2021 Emre Hasegeli
"""

from fileinput import input
from sys import stderr, stdout
from traceback import print_exc

from igcommit.base_check import CheckState, prepare_checks
from igcommit.config import checks
from igcommit.git import Commit, CommitList
from igcommit.utils import iter_buffer


def main():
    try:
        state = run()
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


def run():
    state = CheckState.NEW

    # We are buffering the checks to let them run parallel in the background.
    # Parallelization only applies to the CheckCommands.  It has no overhead,
    # because we have to run those commands the same way externally, anyway.
    # We only have a limit to avoid consuming too many processes.
    # (See iter_buffer() to understand how buffering causes parallel
    # processing.)
    for check in iter_buffer(expand_checks(checks), 16):
        check.print_problems()
        assert check.state >= CheckState.DONE
        state = max(state, check.state)

    return state


def expand_checks(checks):
    """Clone, prepare, and yield the checks

    This is the entry function to start processing the checks.  The processing
    is done in here for all inputs.  They are the branches and the tags
    pushed to Git and received by the prereceive hook.

    The processing then continues to list of commits, the commits in every
    list, and the files changed by those commits by the following functions.
    Those functions clone the checks we start with in here for every object,
    so we end up yielding a lot more checks than we start.

    The checks are for different types of objects.  Some of them checks
    the list of commits, some particular commits, some just files.  These
    functions in here are agnostic about this.  They would keep preparing
    them on different levels with different types objects, and yield back
    the ones that are cloned and become ready.  The processing will stop
    there.  They will not be passed to the next function after they become
    ready.
    """
    checked_commit_ids = set()
    for line in input():
        for check in expand_checks_to_input(checks, line, checked_commit_ids):
            yield check


def expand_checks_to_input(checks, line, checked_commit_ids):
    line_split = line.split()
    ref_path_split = line_split[2].split('/', 2)
    if ref_path_split[0] != 'refs' or len(ref_path_split) != 3:
        # We have no idea what this is.
        return

    commit = Commit(line_split[1])
    if not commit:
        # This is a deletion.  We don't check anything on deletes.
        return

    name = line_split[2]
    if ref_path_split[1] == 'heads':
        commit_list = CommitList(commit.get_new_commits(), name)
    elif ref_path_split[1] == 'tags':
        commit_list = CommitList([commit], name)

    # Appending the actual commit on the list to the new ones makes
    # testing easier.
    if commit not in commit_list:
        commit_list.append(commit)

    for check in expand_checks_to_commit_list(
        checks, commit_list, checked_commit_ids
    ):
        yield check


def expand_checks_to_commit_list(checks, commit_list, checked_commit_ids):
    next_checks = []
    for check in prepare_checks(checks, commit_list, next_checks):
        yield check

    changed_file_checks = {}
    for commit in commit_list:
        if commit.commit_id not in checked_commit_ids:
            for check in expand_checks_to_commit(
                next_checks, commit, changed_file_checks
            ):
                yield check
            checked_commit_ids.add(commit.commit_id)


def expand_checks_to_commit(checks, commit, changed_file_checks):
    next_checks = []
    for check in prepare_checks(checks, commit, next_checks):
        yield check

    for changed_file in commit.get_changed_files():
        for check in expand_checks_to_file(
            next_checks, changed_file, changed_file_checks
        ):
            yield check


def expand_checks_to_file(checks, changed_file, changed_file_checks):
    # We first need to wait for the previous checks on the same file
    # to finish.  If one of them failed already, we don't bother checking
    # the same file again.  The committer should return back to her commit
    # she broke the file.  It makes too much noise to complain about the same
    # file on multiple commits.
    previous_checks = changed_file_checks.setdefault(changed_file.path, [])
    for check in previous_checks:
        assert check.state >= CheckState.READY

        # Wait for the check to run
        while check.state < CheckState.DONE:
            yield None

        if check.state >= CheckState.FAILED:
            return

    for check in prepare_checks(checks, changed_file):
        yield check
        previous_checks.append(check)
