"""igcommit - Checks on Git commits

Copyright (c) 2021 InnoGames GmbH
Portions Copyright (c) 2021 Emre Hasegeli
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
        for line_id, line in enumerate(self.commit.get_message_lines()):
            if line_id == 0:
                continue
            elif line_id == 1:
                if line.strip():
                    yield Severity.ERROR, 'no single line commit summary'
            else:
                if line.startswith('    ') or line.startswith('>'):
                    continue

            if line:
                for problem in self.get_line_problems(line_id + 1, line):
                    yield problem

    def get_line_problems(self, line_number, line):
        if line.rstrip() != line:
            line = line.rstrip()
            yield (
                Severity.ERROR,
                'line {}: trailing space'.format(line_number)
            )

        if line.lstrip() != line:
            line = line.lstrip()
            yield (
                Severity.WARNING,
                'line {}: leading space'.format(line_number)
            )

        if len(line) > 72:
            yield (
                Severity.WARNING,
                'line {}: longer than 72'.format(line_number)
            )


class CheckCommitSummary(CommitCheck):
    commit_tags = {
        'BREAKING',
        'BUGFIX',
        'CLEANUP',
        'FEATURE',
        'HOTFIX',
        'MESS',
        'MIGRATE',
        'REFACTORING',
        'REVIEW',
        'SECURITY',
        'STYLE',
        'TASK',
        'TEMP',
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

        for problem in self.get_summary_problems(rest):
            yield problem

    def get_revert_commit_problems(self, rest):
        rest = rest[len('Revert'):]
        if not rest.startswith(' "') or not rest.endswith('"'):
            yield Severity.WARNING, 'ill-formatted revert commit message'

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
                    Severity.WARNING,
                    'commit tag [{}] not on the list {}'.format(
                        tag, ', '.join(
                            '[{}]'.format(t)
                            for t in CheckCommitSummary.commit_tags
                        )
                    )
                )
            if tag_upper in used_tags:
                yield Severity.ERROR, 'duplicate commit tag [{}]'.format(tag)
            used_tags.append(tag_upper)

        if not rest.startswith(' '):
            yield Severity.WARNING, 'commit tags not separated with space'

    def get_summary_problems(self, rest):
        if not rest:
            yield Severity.ERROR, 'no commit summary'
            return

        rest_len = len(rest)
        if rest_len > 72:
            yield Severity.ERROR, 'commit summary longer than 72 characters'
        elif rest_len > 50:
            yield Severity.WARNING, 'commit summary longer than 50 characters'

        if '  ' in rest:
            yield Severity.WARNING, 'multiple spaces'

        category_index = rest[:24].find(': ')
        rest_index = category_index + len(': ')
        if category_index >= 0 and len(rest) > rest_index:
            for problem in self.get_category_problems(rest[:category_index]):
                yield problem
            rest = rest[rest_index:]

        for problem in self.get_title_problems(rest):
            yield problem

    def get_category_problems(self, category):
        if not category[0].isalpha():
            yield Severity.WARNING, 'commit category starts with non-letter'
        if category.lower() != category:
            yield Severity.WARNING, 'commit category has upper-case letter'
        if category.rstrip() != category:
            yield Severity.WARNING, 'commit category with trailing space'

    def get_title_problems(self, rest):
        if not rest:
            yield Severity.ERROR, 'no commit title'
            return

        first_letter = rest[0]
        if not first_letter.isalpha():
            yield Severity.WARNING, 'commit title start with non-letter'
        elif first_letter.upper() != first_letter:
            yield Severity.WARNING, 'commit title not capitalized'

        if rest.endswith('.'):
            yield Severity.WARNING, 'commit title ends with a dot'

        first_word = rest.split(' ', 1)[0]
        if first_word.endswith('ed'):
            yield Severity.WARNING, 'past tense used on commit title'
        if first_word.endswith('ing'):
            yield Severity.WARNING, 'continuous tense used on commit title'


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
