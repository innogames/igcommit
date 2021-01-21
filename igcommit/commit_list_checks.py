"""igcommit - Checks on Git commit lists

Copyright (c) 2021 InnoGames GmbH
Portions Copyright (c) 2021 Emre Hasegeli
"""

from time import time

from igcommit.base_check import BaseCheck, Severity
from igcommit.git import Commit, CommitList


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
        branch_name = self.commit_list.branch_name
        for commit in self.commit_list:
            summary = commit.get_summary()
            if summary.startswith(self.merge_template.format(branch_name)):
                yield Severity.WARNING, 'merge commit to itself'
            elif summary.startswith(self.merge_template.format('master')):
                yield Severity.WARNING, 'merge commit master'


class CheckTimestamps(CommitListCheck):
    current_timestamp = time()

    def get_problems(self):
        previous_author_timestamp = 0
        previous_committer_timestamp = 0
        for commit in self.commit_list:
            author_timestamp = commit.get_author().timestamp
            committer_timestamp = commit.get_committer().timestamp
            if author_timestamp > self.current_timestamp + 2:
                yield (
                    Severity.ERROR,
                    'author timestamp of commit {} in future'
                    .format(commit),
                )
            if committer_timestamp > self.current_timestamp + 2:
                yield (
                    Severity.ERROR,
                    'committer timestamp of commit {} in future'
                    .format(commit),
                )
            if author_timestamp > committer_timestamp:
                yield (
                    Severity.ERROR,
                    'author timestamp of commit {} after committer'
                    .format(commit),
                )
            if previous_author_timestamp > author_timestamp:
                yield (
                    Severity.NOTICE,
                    'author timestamp of commit {} before previous commit'
                    .format(commit),
                )
            if previous_committer_timestamp > committer_timestamp:
                yield (
                    Severity.ERROR,
                    'committer timestamp of commit {} before previous commit'
                    .format(commit),
                )
            previous_author_timestamp = author_timestamp
            previous_committer_timestamp = committer_timestamp


class CheckContributors(CommitListCheck):
    """Validate consistency of committer and author name and email addresses

    We threat committers and authors the same way in this class.  It is common
    Git bad practice to commit with different combinations of names and
    email addresses ruining useful statistics that can be made using the Git
    history.  There is not too much we can do about without having
    the possible list of all users, and that is certainly not something we
    would like.

    In this class, we are searching and indexing the Git commits in the past
    to find out the same names and email address, and cross check them with
    the current commits.  We are using the name together with the domain part
    of the email address.  It is common for some systems to commit changes
    in behalf of the user with a different email address.  Including
    the domain on the index would let it happen.
    """
    def prepare(self, obj):
        new = super(CheckContributors, self).prepare(obj)
        if new and isinstance(obj, CommitList):
            new.email_index = {}
            new.domain_index = {}
            new.name_index = {}

        return new

    def get_problems(self):
        old_contributors = self.get_old_contributors()
        for commit in self.commit_list:
            for contributor in commit.get_contributors():
                found = self.index_contributors(old_contributors, contributor)

                for problem in self.check_contributor(contributor, commit):
                    yield problem

                    # If there are any problems, evidently the contributor
                    # is not consistent with the indexes.  We override
                    # the indexes after reporting problem to avoid the same
                    # ones to be reported again.
                    found = False

                if not found:
                    self.index_contributor(contributor, override=True)

    def get_old_commits(self):
        """Yield old commits in reverse order

        We could call "git rev-list" here, but it is easy enough to implement
        the same using the content we already need for other reasons.  Though
        "git rev-list" would order the commits nicer, we are not putting any
        effort to the ordering in here as our caller is not sensitive.
        """
        unused_commits = self.commit_list[0].get_parents()
        commit_ids = {c.commit_id for c in unused_commits}
        while unused_commits:
            unused_commit = unused_commits.pop(0)
            yield unused_commit
            for commit in unused_commit.get_parents():
                if commit.commit_id not in commit_ids:
                    unused_commits.append(commit)
                    commit_ids.add(commit.commit_id)

    def get_old_contributors(self):
        for commit in self.get_old_commits():
            for contributor in commit.get_contributors():
                yield contributor

    def index_contributor(self, contributor, override=False, dry_run=False):
        """Index a single contributor

        The function does nothing when the contributor is already indexed.
        It returns true when if would add the contributor to any index.
        The dry_run argument is used to test only, if the contributor is
        indexed.
        """
        found = False

        if contributor.email not in self.email_index or override:
            if not dry_run:
                self.email_index[contributor.email] = contributor
            found = True

        domain = contributor.get_email_domain()
        if domain not in self.domain_index or override:
            if not dry_run:
                self.domain_index[domain] = None
            found = True

        if (contributor.name, domain) not in self.name_index or override:
            if not dry_run:
                self.name_index[(contributor.name, domain)] = contributor
            found = True

        return found

    def index_contributors(self, contributors, searched):
        """Index contributors until the searched one is found

        The function stops when the searched one is found.  We assume
        the caller to pass the existing generator again to avoid starting over
        to search the next one.  It returns with true when the searched one
        is found; returns with false when all of the items are indexes but
        the searched one is not found.
        """
        while self.index_contributor(searched, dry_run=True):
            for contributor in contributors:
                if self.index_contributor(contributor):
                    break
            else:
                return False
        return True

    def check_contributor(self, contributor, commit):
        """Check one contributor against the indexes"""

        other = self.email_index.get(contributor.email)
        if other and contributor.name != other.name:
            yield (
                Severity.ERROR,
                'contributor of commit {} has a different name "{}" '
                'than "{}" the contributor with the same email address'
                .format(commit, contributor.name, other.name),
            )

        domain = contributor.get_email_domain()
        if domain not in self.domain_index:
            yield (
                Severity.NOTICE,
                'contributor of commit {} has a email address with a new '
                'domain "{}" '
                .format(commit, domain),
            )

        other = self.name_index.get((contributor.name, domain))
        if other and contributor.email != other.email:
            yield (
                Severity.ERROR,
                'contributor of commit {} has a different email address "{}" '
                'with the same domain than "{}" from contributor with '
                'the same name'
                .format(commit, contributor.email, other.email),
            )
