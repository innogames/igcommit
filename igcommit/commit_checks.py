"""igcommit - Checks on Git commits

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.base_check import BaseCheck
from igcommit.git import CommitList, Commit


class CheckDuplicateCommitSummaries(BaseCheck):
    """Check repeated commit summaries on a single commit list

    We are not exact matching the commit summaries, but searching summaries
    on the beginning of other ones.  This covers summaries like "Fix the bug"
    and "Fix the bug really" which is common bad practice for some reason.
    """
    commit_list = None

    def prepare(self, obj):
        assert isinstance(obj, CommitList)

        if len(obj) <= 1:
            return None

        new = self.clone()
        new.commit_list = obj
        new.ready = True
        return new

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
                self.failed = True
            duplicate_summaries = [summary]

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.commit_list)


class CommitCheck(BaseCheck):
    """Parent class for all single commit checks"""
    commit = None

    def prepare(self, obj):
        if not isinstance(obj, Commit):
            return super(CommitCheck, self).prepare(obj)

        new = self.clone()
        new.commit = obj
        new.ready = True
        return new

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.commit)


class CheckMisleadingMergeCommit(CommitCheck):
    def get_problems(self):
        summary = self.commit.get_summary()
        if summary.startswith("Merge branch 'master'"):
            yield 'error: merge commit from "master"'
            self.failed = True


class CheckCommitMessage(CommitCheck):
    def get_problems(self):
        for line_id, line in enumerate(self.commit.get_message().splitlines()):
            if line_id == 1 and line:
                yield 'error: summary extends the first line'
                self.failed = True
            if line and line[-1] == ' ':
                yield 'error: line {}: trailing space'.format(line_id + 1)
                self.failed = True
            if line_id > 1 and line.startswith('    ') or line.startswith('>'):
                continue
            if len(line) >= 80:
                yield 'warning: line {}: longer than 80'.format(line_id + 1)


class CheckCommitSummary(CommitCheck):
    def get_problems(self):
        tags, rest = self.commit.parse_tags()
        if '  ' in rest:
            yield 'warning: multiple spaces'

        if rest.startswith('['):
            yield 'warning: not terminated commit tags'
        if tags:
            if not rest.startswith(' '):
                yield 'warning: commit tags not separated with space'
            rest = rest[1:]

        if rest.startswith('Revert'):
            rest = rest[len('Revert'):]
            if not rest.startswith(' "') or not rest.endswith('"'):
                yield 'warning: ill-formatted revert commit'
            return

        if len(rest) > 72:
            yield 'warning: summary longer than 72 characters'

        if ':' in rest[:24]:
            category, rest = rest.split(':', 1)
            if not category[0].isalpha():
                yield 'warning: commit category start with non-letter'
            if category != category.lower():
                yield 'warning: commit category has upper-case letter'
            if not rest.startswith(' '):
                yield 'warning: commit category not separated with space'
            rest = rest[1:]

        if not rest:
            yield 'error: no summary'
            self.failed = True
            return

        if not rest[0].isalpha():
            yield 'warning: summary start with non-letter'
        if rest[-1] == '.':
            yield 'warning: summary ends with a dot'

        first_word = rest.split(' ', 1)[0]
        if first_word.endswith('ed'):
            yield 'warning: past tense used on summary'
        if first_word.endswith('ing'):
            yield 'warning: continuous tense used on summary'


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
                yield 'error: commit tag [{}] not upper-case'.format(tag)
                self.failed = True
            if tag_upper not in CheckCommitTags.tags:
                yield 'warning: commit tag [{}] not on list'.format(tag)
            if tag_upper in used_tags:
                yield 'error: duplicate commit tag [{}]'.format(tag)
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
                yield 'error: {} has upper case'.format(changed_file)
                self.failed = True
