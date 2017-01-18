"""igcommit - Checks on Git commits

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.base_check import CheckState, BaseCheck
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
                yield 'error: summary extends the first line'
                self.set_state(CheckState.failed)
            if line and line[-1] == ' ':
                yield 'error: line {}: trailing space'.format(line_id + 1)
                self.set_state(CheckState.failed)
            if line_id > 1 and line.startswith('    ') or line.startswith('>'):
                continue
            if len(line) >= 80:
                yield 'warning: line {}: longer than 80'.format(line_id + 1)
        self.set_state(CheckState.done)


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
            yield 'warning: not terminated commit tags'
        if tags:
            for problem in self.get_commit_tag_problems(tags, rest):
                yield problem
            rest = rest[1:]

        if rest.startswith('Revert'):
            for problem in self.get_revert_commit_problems(rest):
                yield problem
            return

        if ':' in rest[:24]:
            for problem in self.get_commit_category_problems(rest):
                yield problem
            rest = rest[(rest.index(':') + 1):]

        for problem in self.get_summary_problems(rest):
            yield problem

        self.set_state(CheckState.done)

    def get_revert_commit_problems(self, rest):
        rest = rest[len('Revert'):]
        if not rest.startswith(' "') or not rest.endswith('"'):
            yield 'warning: ill-formatted revert commit'
        self.set_state(CheckState.done)

    def get_commit_tag_problems(self, tags, rest):
        used_tags = []
        for tag in tags:
            tag_upper = tag.upper()
            if tag != tag_upper:
                yield 'error: commit tag [{}] not upper-case'.format(tag)
                self.set_state(CheckState.failed)
            if tag_upper not in CheckCommitSummary.commit_tags:
                yield 'warning: commit tag [{}] not on list'.format(tag)
            if tag_upper in used_tags:
                yield 'error: duplicate commit tag [{}]'.format(tag)
                self.set_state(CheckState.failed)
            used_tags.append(tag_upper)

        if not rest.startswith(' '):
            yield 'warning: commit tags not separated with space'

    def get_commit_category_problems(self, rest):
        category, rest = rest.split(':', 1)
        if not category[0].isalpha():
            yield 'warning: commit category start with non-letter'
        if category != category.lower():
            yield 'warning: commit category has upper-case letter'
        if not rest.startswith(' '):
            yield 'warning: commit category not separated with space'

    def get_summary_problems(self, rest):
        if not rest:
            yield 'error: no summary'
            self.set_state(CheckState.failed)
            return

        if len(rest) > 72:
            yield 'warning: summary longer than 72 characters'

        if '  ' in rest:
            yield 'warning: multiple spaces'

        if not rest[0].isalpha():
            yield 'warning: summary start with non-letter'
        if rest[-1] == '.':
            yield 'warning: summary ends with a dot'

        first_word = rest.split(' ', 1)[0]
        if first_word.endswith('ed'):
            yield 'warning: past tense used on summary'
        if first_word.endswith('ing'):
            yield 'warning: continuous tense used on summary'


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
                self.set_state(CheckState.failed)
        self.set_state(CheckState.done)
