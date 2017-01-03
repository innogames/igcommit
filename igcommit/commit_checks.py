"""igcommit - Checks on Git commits

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.base_check import BaseCheck
from igcommit.git import Commit


class CheckDuplicateCommitSummaries(BaseCheck):
    """Check repeated commit summaries on a single commit list

    We are not exact matching the commit summaries, but searching summaries
    on the beginning of other ones.  This covers summaries like "Fix the bug"
    and "Fix the bug really" which is common bad practice for some reason.
    """
    commit_list = None

    def for_commit_list(self, commit_list):
        if len(commit_list) <= 1:
            return None
        new = self.clone()
        new.commit_list = commit_list
        new.ready = True
        return new

    def for_commit(self, commit):
        return None

    def get_problems(self):
        duplicate_summaries = [()]  # Nothing starts with an empty tuple.
        for commit in sorted(self.commit_list, key=Commit.get_summary):
            summary = commit.get_summary()
            if summary.startswith(duplicate_summaries[0]):
                duplicate_summaries.append(summary)
                continue
            if len(duplicate_summaries) > 1:
                for summary in duplicate_summaries:
                    yield summary
                self.failed = True
            duplicate_summaries = [summary]

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.commit_list)


class CommitCheck(BaseCheck):
    """Parent class for all single commit checks"""
    commit = None

    def for_commit(self, commit):
        new = self.clone()
        new.commit = commit
        new.ready = True
        return new

    def for_committed_file(self, committed_file):
        return None

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.commit)


class CheckMisleadingMergeCommit(CommitCheck):
    def get_problems(self):
        summary = self.commit.get_summary()
        if summary.startswith("Merge branch 'master'"):
            yield summary
            self.failed = True


class CheckCommitMessage(CommitCheck):
    def get_problems(self):
        for line_id, line in enumerate(self.commit.get_message().splitlines()):
            if line_id == 1 and line:
                yield 'summary extends the first line'
                self.failed = True
            if line and line[-1] == ' ':
                yield 'line {}: trailing space'.format(line_id + 1)
                self.failed = True
            if line_id > 1 and line.startswith('    ') or line.startswith('>'):
                continue
            if len(line) >= 80:
                yield 'line {}: longer than 80'.format(line_id + 1)


class CheckCommitSummary(CommitCheck):
    def get_problems(self):
        tags, rest = self.commit.parse_tags()
        if '  ' in rest:
            yield 'multiple spaces'

        if rest.startswith('['):
            yield 'not terminated commit tags'
        if tags:
            if not rest.startswith(' '):
                yield 'commit tags not separated with space'
            rest = rest[1:]

        if rest.startswith('Revert'):
            rest = rest[len('Revert'):]
            if not rest.startswith(' "') or not rest.endswith('"'):
                yield 'ill-formatted revert commit'
            return

        if len(rest) > 72:
            yield 'summary longer than 72 characters'

        if ':' in rest[:24]:
            category, rest = rest.split(':', 1)
            if not category[0].isalpha():
                yield 'commit category start with non-letter'
            if category != category.lower():
                yield 'commit category has upper-case letter'
            if not rest.startswith(' '):
                yield 'commit category not separated with space'
            rest = rest[1:]

        if not rest:
            yield 'no summary'
            self.failed = True
            return

        if not rest[0].isalpha():
            yield 'summary start with non-letter'
        if rest[-1] == '.':
            yield 'summary ends with a dot'

        first_word = rest.split(' ', 1)[0]
        if first_word.endswith('ed'):
            yield 'past tense used on summary'
        if first_word.endswith('ing'):
            yield 'continuous tense used on summary'


class CheckCommitTags(CommitCheck):
    """Check the tags on the commit summaries"""
    tags = {
        'BUGFIX',
        'CLEANUP',
        'FEATURE',
        'HOTFIX',
        'MESS',
        'REFACTORING',
        'REVIEW'
        'SECURITY',
        'STYLE',
        'TASK',
        'WIP',
        '!!',
    }

    def get_problems(self):
        used_tags = []
        for tag in self.commit.parse_tags()[0]:
            tag_upper = tag.upper()
            if tag != tag_upper:
                yield 'commit tag [{}] not upper-case'.format(tag)
                self.failed = True
            if tag_upper not in CheckCommitTags.tags:
                yield 'commit tag [{}] not on list'.format(tag)
            if tag_upper in used_tags:
                yield 'duplicate commit tag [{}]'.format(tag)
                self.failed = True
            used_tags.append(tag_upper)


class CheckChangedFilePaths(CommitCheck):
    """Check file names and directories on a single commit"""
    def get_problems(self):
        for changed_file in self.commit.get_changed_files():
            extension = changed_file.get_extension()
            if (
                extension in ('pp', 'py', 'sh') and
                changed_file.path != changed_file.path.lower()
            ):
                yield '{} has upper case'.format(changed_file)
                self.failed = True
