"""igcommit - Checks on Git commit lists

Copyright (c) 2021 InnoGames GmbH
Portions Copyright (c) 2021 Emre Hasegeli
"""

from time import time


from igcommit.base_check import BaseCheck, Severity
from igcommit.git import Commit, CommitList, git_exe_path, Contributor

from subprocess import check_output


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
        for commit in self.commit_list:
            for contributor in commit.get_contributors():
                # use git log to search for author (important that git log just shows us commits before the pre-receive)
                # use git log to search for committer
                # if nothing is in there, we know that there is no former commit of those contributors
                # if found then we directly can check with the last found specific commit
                # in the end we can store the contributors in a list to not check them again
                for problem in self.check_contributor(contributor, commit):
                    yield problem

    def check_contributor(self, contributor, commit):
        """Check one contributor against the indexes"""

        # TODO: Take always two and check for the latest one.
        # git log with email -> check if name is the same
        # `git log ... --author "^.+ <{email}>$" -E
        for log_check in ['author', 'committer']:
            commit_hash = check_output([
                git_exe_path,
                '--no-pager',
                'log',
                '--pretty=format:%H',
                f'--{log_check}',
                f'^.+ <{contributor.email}>$',
                '-E',
                '-1',
            ]).decode('utf-8')
            if commit_hash:
                break

        if commit_hash:
            commit = Commit(commit_hash)
            cb = getattr(commit, f'get_{log_check}')
            other = cb()
            if other and contributor.name != other.name:
                yield (
                    Severity.ERROR,
                    'contributor of commit {} has a different name "{}" '
                    'than "{}" the contributor with the same email address'
                    .format(commit, contributor.name, other.name),
                )

        # git log with just domain `git log ... --author "^.+ <.*@{get_email_domain()}>$" -E`
        # if no hash could be found, then this is a new domain
        for log_check in ['author', 'committer']:
            commit_hash = check_output([
                git_exe_path,
                '--no-pager',
                'log',
                '--pretty=format:%H',
                f'--{log_check}',
                f'^.+ <.*@{contributor.get_email_domain()}>$',
                '-E',
                '-1',
            ]).decode('utf-8')
            if commit_hash:
                break

        if not commit_hash:
            yield (
                Severity.NOTICE,
                'contributor of commit {} has a email address with a new '
                'domain "{}" '
                .format(commit, contributor.get_email_domain()),
            )

        # git log with name plus email domain
        # git log ... --author "^{name} <.*@{get_email_domain()}>$"
        for log_check in ['author', 'committer']:
            commit_hash = check_output([
                git_exe_path,
                '--no-pager',
                'log',
                '--pretty=format:%H',
                f'--{log_check}',
                f'^{contributor.name} <.*@{contributor.get_email_domain()}>$',
                '-E',
                '-1',
            ]).decode('utf-8')
            if commit_hash:
                break

        if commit_hash:
            commit = Commit(commit_hash)
            cb = getattr(commit, f'get_{log_check}')
            other = cb()
            if other and contributor.email != other.email:
                yield (
                    Severity.ERROR,
                    'contributor of commit {} has a different email address "{}" '
                    'with the same domain than "{}" from contributor with '
                    'the same name'
                    .format(commit, contributor.email, other.email),
                )
