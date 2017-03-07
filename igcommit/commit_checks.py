"""igcommit - Checks on Git commits

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.base_check import BaseCheck, Severity
from igcommit.git import Commit


class CommitCheck(BaseCheck):
    """Parent class for all single commit checks"""
    commit = None

    def prepare(self, obj):
        new = super(CommitCheck, self).prepare(obj)
        if not new or not isinstance(obj, Commit):
            return new

        new = new.clone()
        new.commit = obj
        return new

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.commit)


class CheckCommitMessage(CommitCheck):
    def get_problems(self):
        for line_id, line in enumerate(self.commit.get_message().splitlines()):
            if line_id == 1 and line:
                yield Severity.ERROR, 'summary extends the first line'
            if line and line[-1] == ' ':
                yield (
                    Severity.ERROR,
                    'line {}: trailing space'.format(line_id + 1)
                )
            if line_id > 1 and line.startswith('    ') or line.startswith('>'):
                continue
            if len(line) > 72:
                yield (
                    Severity.WARNING,
                    'line {}: longer than 72'.format(line_id + 1)
                )


class CheckCommitSummary(CommitCheck):
    commit_tags = {
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
        tags, rest = self.commit.parse_tags()
        if rest.startswith('['):
            yield Severity.WARNING, 'not terminated commit tags'
        if tags:
            for problem in self.get_commit_tag_problems(tags, rest):
                yield problem
            rest = rest[1:]

        if rest.startswith('Revert'):
            for problem in self.get_revert_commit_problems(rest):
                yield problem
            return

        category_index = rest[:24].find(': ')
        rest_index = category_index + len(': ')
        if category_index >= 0 and len(rest) > rest_index:
            for problem in self.get_category_problems(rest[:category_index]):
                yield problem
            rest = rest[rest_index:]

        for problem in self.get_summary_problems(rest):
            yield problem

    def get_revert_commit_problems(self, rest):
        rest = rest[len('Revert'):]
        if not rest.startswith(' "') or not rest.endswith('"'):
            yield Severity.WARNING, 'ill-formatted revert commit'

    def get_commit_tag_problems(self, tags, rest):
        used_tags = []
        for tag in tags:
            tag_upper = tag.upper()
            if tag != tag_upper:
                yield (
                    Severity.ERROR,
                    'commit tag [{}] not upper-case'.format(tag)
                )
            if tag_upper not in CheckCommitSummary.commit_tags:
                yield (
                    Severity.WARNING, 'commit tag [{}] not on list'.format(tag)
                )
            if tag_upper in used_tags:
                yield Severity.ERROR, 'duplicate commit tag [{}]'.format(tag)
            used_tags.append(tag_upper)

        if not rest.startswith(' '):
            yield Severity.WARNING, 'commit tags not separated with space'

    def get_category_problems(self, category):
        if not category[0].isalpha():
            yield Severity.WARNING, 'commit category starts with non-letter'
        if category != category.lower():
            yield Severity.WARNING, 'commit category has upper-case letter'
        if category[-1] == ' ':
            yield Severity.WARNING, 'commit category ends with a space'

    def get_summary_problems(self, rest):
        if not rest:
            yield Severity.ERROR, 'no summary'
            return

        if len(rest) > 50:
            yield Severity.WARNING, 'summary longer than 50 characters'

        if '  ' in rest:
            yield Severity.WARNING, 'multiple spaces'

        if not rest[0].isalpha():
            yield Severity.WARNING, 'summary start with non-letter'
        if rest[-1] == '.':
            yield Severity.WARNING, 'summary ends with a dot'

        first_word = rest.split(' ', 1)[0]
        if first_word.endswith('ed'):
            yield Severity.WARNING, 'past tense used on summary'
        if first_word.endswith('ing'):
            yield Severity.WARNING, 'continuous tense used on summary'


class CheckChangedFilePaths(CommitCheck):
    """Check file names and directories on a single commit"""
    def get_problems(self):
        for changed_file in self.commit.get_changed_files():
            extension = changed_file.get_extension()
            if (
                extension in ('pp', 'py', 'sh') and
                changed_file.path != changed_file.path.lower()
            ):
                yield Severity.ERROR, '{} has upper case'.format(changed_file)
