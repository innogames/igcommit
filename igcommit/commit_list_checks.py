"""igcommit - Checks on Git commit lists

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.base_check import BaseCheck, Severity
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
                yield (
                    Severity.ERROR, 'summary "{}" duplicated {} times'.format(
                        min(duplicate_summaries, key=len),
                        len(duplicate_summaries),
                    )
                )
            duplicate_summaries = [summary]


class CheckMisleadingMergeCommit(CommitListCheck):
    merge_template = "Merge branch '{}'"

    def get_problems(self):
        ref_name = self.commit_list.ref_path.rsplit('/', 1)[-1]
        for commit in self.commit_list:
            summary = commit.get_summary()
            if summary.startswith(self.merge_template.format(ref_name)):
                yield Severity.WARNING, 'merge commit to itself'
            elif summary.startswith(self.merge_template.format('master')):
                yield Severity.WARNING, 'merge commit master'
