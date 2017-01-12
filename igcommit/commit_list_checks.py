"""igcommit - Checks on Git commit lists

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.base_check import CheckState, BaseCheck
from igcommit.git import CommitList, Commit


class CommitListCheck(BaseCheck):
    """Parent class for all commit list checks"""
    commit_list = None

    def prepare(self, obj):
        if not isinstance(obj, CommitList):
            return super(CommitListCheck, self).prepare(obj)

        new = self.clone()
        new.commit_list = obj
        return new

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.commit_list)


class CheckDuplicateCommitSummaries(CommitListCheck):
    """Check repeated commit summaries on a single commit list

    We are not exact matching the commit summaries, but searching summaries
    on the beginning of other ones.  This covers summaries like "Fix the bug"
    and "Fix the bug really" which is common bad practice for some reason.
    """

    def prepare(self, obj):
        if isinstance(obj, CommitList) and len(obj) <= 1:
            return None
        return super(CheckDuplicateCommitSummaries, self).prepare(obj)

    def get_problems(self):
        duplicate_summaries = [()]  # Nothing starts with an empty tuple.
        for commit in sorted(self.commit_list, key=Commit.get_summary):
            summary = commit.get_summary()
            if summary.startswith(duplicate_summaries[0]):
                duplicate_summaries.append(summary)
                continue
            if len(duplicate_summaries) > 1:
                yield 'error: summary "{}" duplicated {} times'.format(
                    min(duplicate_summaries, key=len),
                    len(duplicate_summaries),
                )
                self.set_state(CheckState.failed)
            duplicate_summaries = [summary]
        self.set_state(CheckState.done)


class CheckMisleadingMergeCommit(CommitListCheck):
    merge_template = "Merge branch '{}'"

    def get_problems(self):
        ref_name = self.commit_list.ref_path.rsplit('/', 1)[-1]
        for commit in self.commit_list:
            summary = commit.get_summary()
            if summary.startswith(self.merge_template.format(ref_name)):
                yield 'error: merge commit to itself'
                self.set_state(CheckState.failed)
            elif summary.startswith(self.merge_template.format('master')):
                yield 'warning: merge commit master'
        self.set_state(CheckState.done)
