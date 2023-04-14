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

    @classmethod
    def get_key(cls):
        return 'check_commit_message'

    length = 72
    msg_leading_space = True
    msg_trailing_space = True
    msg_single_line_summary = True
    msg_leading_tab_or_biggerthan_sign = True

    def get_problems(self):
        for line_id, line in enumerate(self.commit.get_message_lines()):
            if line_id == 0:
                continue
            elif line_id == 1:
                if self.msg_single_line_summary and line.strip():
                    yield Severity.ERROR, 'no single line commit summary'
            else:
                if self.msg_leading_tab_or_biggerthan_sign and (line.startswith('    ') or line.startswith('>')):
                    continue

            if line:
                for problem in self.get_line_problems(line_id + 1, line):
                    yield problem

    def get_line_problems(self, line_number, line):
        if self.msg_trailing_space and line.rstrip() != line:
            line = line.rstrip()
            yield (
                Severity.ERROR,
                'line {}: trailing space'.format(line_number)
            )

        if self.msg_leading_space and line.lstrip() != line:
            line = line.lstrip()
            yield (
                Severity.WARNING,
                'line {}: leading space'.format(line_number)
            )

        if len(line) > self.length:
            yield (
                Severity.WARNING,
                'line {}: longer than {}'.format(line_number, str(self.length))
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

    soft_length = 50
    hard_length = 72
    category_non_letter_start = True
    category_upper_case_letter = True
    category_trailing_space = True
    title_non_letter_start = True
    title_not_capitalized = True
    title_end_dot = True
    title_past_tense = True
    title_continuous_tense = True
    revert_commit = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.soft_length < 0:
            self.soft_length = float('inf')
        if self.hard_length < 0:
            self.hard_length = float('inf')

    @classmethod
    def get_key(cls):
        return 'check_commit_summary'

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
        if self.revert_commit:
            rest = rest[len('Revert'):]
            if self.revert_commit and (not rest.startswith(' "') or not rest.endswith('"')):
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
        if rest_len > self.hard_length:
            if rest.startswith('Merge branch '):
                sev = Severity.WARNING
            else:
                sev = Severity.ERROR
            yield sev, f'commit summary longer than {self.hard_length} characters'
        elif rest_len > self.soft_length:
            yield Severity.WARNING, f'commit summary longer than {self.soft_length} characters'

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
        if self.category_non_letter_start and not category[0].isalpha():
            yield Severity.WARNING, 'commit category starts with non-letter'
        if self.category_upper_case_letter and category.lower() != category:
            yield Severity.WARNING, 'commit category has upper-case letter'
        if self.category_trailing_space and category.rstrip() != category:
            yield Severity.WARNING, 'commit category with trailing space'

    def get_title_problems(self, rest):
        if not rest:
            yield Severity.ERROR, 'no commit title'
            return

        first_letter = rest[0]
        if self.title_non_letter_start and not first_letter.isalpha():
            yield Severity.WARNING, 'commit title starts with non-letter'
        elif self.title_not_capitalized and first_letter.upper() != first_letter:
            yield Severity.WARNING, 'commit title not capitalized'

        if self.title_end_dot and rest.endswith('.'):
            yield Severity.WARNING, 'commit title ends with a dot'

        first_word = rest.split(' ', 1)[0]
        if self.title_past_tense and first_word.endswith('ed'):
            yield Severity.WARNING, 'past tense used on commit title'
        if self.title_continuous_tense and first_word.endswith('ing'):
            yield Severity.WARNING, 'continuous tense used on commit title'


class CheckChangedFilePaths(CommitCheck):
    """Check file names and directories on a single commit"""

    extensions = ['pp', 'py', 'sh']

    @classmethod
    def get_key(cls):
        return 'check_changed_file_paths'

    def get_problems(self):
        for changed_file in self.commit.get_changed_files():
            extension = changed_file.get_extension()
            if (
                extension and
                extension.lower() in self.extensions and
                changed_file.path != changed_file.path.lower()
            ):
                yield Severity.ERROR, '{} has upper case'.format(changed_file)
