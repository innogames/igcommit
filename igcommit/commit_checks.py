#!/usr/bin/env python
"""igcommit - Checks on Git commits

Copyright (c) 2016, InnoGames GmbH
"""

from igcommit.git import Commit


class Check():
    def __str__(self):
        return type(self).__name__


class CheckDuplicateCommitSummaries(Check):
    def get_problems(self, commit_list):
        duplicate_summaries = [()]  # Nothing starts with an empty tuple.
        for commit in sorted(commit_list, key=Commit.get_summary):
            summary = commit.get_summary()
            if summary.startswith(duplicate_summaries[0]):
                duplicate_summaries.append(summary)
                continue
            if len(duplicate_summaries) > 1:
                for summary in duplicate_summaries:
                    yield summary
            duplicate_summaries = [summary]


class CheckMisleadingMergeCommit(Check):
    def get_problems(self, commit):
        summary = commit.get_summary()
        if summary.startswith("Merge branch 'master'"):
            yield summary


class CheckCommitMessage(Check):
    def get_problems(self, commit):
        for line_id, line in enumerate(commit.get_message().splitlines()):
            if line_id == 1 and line:
                yield 'has no summary'
            if line and line[-1] == ' ':
                yield 'line {} has trailing space'.format(line_id + 1)
            if line_id > 1 and line.startswith('    ') or line.startswith('>'):
                continue
            if len(line) >= 80:
                yield 'line {} is longer than 80'.format(line_id + 1)


class CheckCommitSummary(Check):
    def get_problems(self, commit):
        tags, rest = commit.parse_tags()
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
        if not rest[0].isalpha():
            yield 'summary start with non-letter'
        if rest[-1] == '.':
            yield 'summary ends with a dot'

        first_word = rest.split(' ', 1)[0]
        if first_word.endswith('ed'):
            yield 'past tense used on summary'
        if first_word.endswith('ing'):
            yield 'continuous tense used on summary'


class CheckCommitTags(Check):
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

    def get_problems(self, commit):
        used_tags = []
        for tag in commit.parse_tags()[0]:
            tag_upper = tag.upper()
            if tag != tag_upper:
                yield 'commit tag [{}] not upper-case'.format(tag)
            if tag_upper not in CheckCommitTags.tags:
                yield 'commit tag [{}] not on list'.format(tag)
            if tag_upper in used_tags:
                yield 'duplicate commit tag [{}]'.format(tag)
            used_tags.append(tag_upper)


class CheckChangedFilePaths(Check):
    def get_problems(self, commit):
        for changed_file in commit.get_changed_files():
            extension = changed_file.get_extension()
            if (
                extension in ('pp', 'py', 'sh') and
                changed_file.path != changed_file.path.lower()
            ):
                yield '{} has upper case'.format(changed_file)
