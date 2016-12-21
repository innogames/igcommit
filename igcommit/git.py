"""igcommit - Git routines

Copyright (c) 2016, InnoGames GmbH
"""

from subprocess import check_output

from igcommit.utils import get_exe_path

git_exe_path = get_exe_path('git')


class Commit(object):
    """Routines on a single commit"""
    null_commit_id = '0000000000000000000000000000000000000000'

    def __init__(self, commit_list, commit_id):
        self.commit_list = commit_list
        self.commit_id = commit_id
        self.message = None
        self.changed_files = None

    def __str__(self):
        return self.commit_id[:8]

    def __bool__(self):
        return self.commit_id != Commit.null_commit_id

    def __nonzero__(self):
        return self.__bool__()

    def __eq__(self, other):
        return isinstance(other, Commit) and self.commit_id == other.commit_id

    def get_new_commit_ids(self):
        """Get the list of parent new commits in order"""
        return check_output((
            git_exe_path,
            'rev-list',
            self.commit_id,
            '--not',
            '--all',
            '--reverse',
        )).decode().splitlines()

    def get_message(self):
        if self.message is None:
            self.message = check_output((
                git_exe_path,
                'log',
                '--format=%B',
                '--max-count=1',
                self.commit_id,
            )).decode()
        return self.message

    def get_summary(self):
        for line in self.get_message().splitlines():
            return line

    def parse_tags(self):
        tags = []
        rest = self.get_summary()
        while rest.startswith('[') and ']' in rest:
            end_index = rest.index(']')
            tags.append(rest[1:end_index])
            rest = rest[end_index + 1:]
        return tags, rest

    def can_soft_fail(self):
        return any(t in ('MESS', 'WIP') for t in self.parse_tags()[0])

    def get_changed_files(self):
        """Return the list of added or modified files on a commit"""
        if self.changed_files is None:
            output = check_output((
                git_exe_path,
                'diff-tree',
                '-r',
                '--no-commit-id',
                '--break-rewrites',     # Get rewrites as additions
                '--no-renames',         # Get rewrites as additions
                '--diff-filter=AM',     # Only additions and modifications
                self.commit_id,
            )).decode()
            changed_files = []
            for line in output.splitlines():
                line_split = line.split()
                assert len(line_split) == 6
                assert line_split[0].startswith(':')
                file_mode = line_split[1]
                file_path = line_split[5]
                changed_files.append(CommittedFile(self, file_path, file_mode))
            self.changed_files = changed_files
        return self.changed_files


class CommittedFile(object):
    """Routines on a single committed file"""

    def __init__(self, commit, path, mode=None):
        self.commit = commit
        self.path = path
        self.mode = mode
        self.shebang = None

    def __str__(self):
        return '{} at {}'.format(self.path, self.commit)

    def __eq__(self, other):
        return (
            isinstance(other, CommittedFile) and
            self.commit == other.commit and
            self.path == other.path
        )

    def exists(self):
        return bool(check_output((
            git_exe_path,
            'ls-tree',
            '--name-only',
            '-r',
            self.commit.commit_id,
            self.path,
        )))

    def changed(self):
        return self in self.commit.get_changed_files()

    def owner_can_execute(self):
        assert len(self.mode) > 3
        owner_bits = int(self.mode[-3])
        return bool(owner_bits & 1)

    def get_extension(self):
        if '.' in self.path:
            return self.path.rsplit('.', 1)[1]

    def get_content(self):
        """Return the content of a file on a commit as bytes"""
        return check_output((
            git_exe_path,
            'show',
            self.commit.commit_id + ':' + self.path,
        ))

    def get_shebang(self):
        if self.shebang is None:
            for line in self.get_content().splitlines():
                if line.startswith(b'#!'):
                    self.shebang = line[len('#!'):].decode()
                else:
                    self.shebang = ''
                break
        return self.shebang

    def get_shebang_exe(self):
        shebang = self.get_shebang()
        if not shebang:
            return None
        shebang_split = shebang.split(None, 2)
        if shebang_split[0] == '/usr/bin/env' and len(shebang_split) > 1:
            return shebang_split[1]
        return shebang_split[0]

    def write(self):
        with open(self.path, 'wb') as fd:
            fd.write(self.get_content())
