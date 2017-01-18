"""igcommit - Git routines

Copyright (c) 2016, InnoGames GmbH
"""

from subprocess import check_output, CalledProcessError, Popen, PIPE

from igcommit.utils import get_exe_path

git_exe_path = get_exe_path('git')


class CommitList(list):
    """Routines on a list of sequential commits"""
    ref_path = None

    def __init__(self, other, ref_path=None):
        super(CommitList, self).__init__(other)
        if ref_path:
            self.ref_path = ref_path

    def __str__(self):
        name = '{}..{}'.format(self[0], self[-1])
        if self.ref_path:
            name += ' ({})'.format(self.ref_path)
        return name


class Commit(object):
    """Routines on a single commit"""
    null_commit_id = '0000000000000000000000000000000000000000'

    def __init__(self, commit_id, commit_list=None):
        self.commit_id = commit_id
        self.commit_list = commit_list
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

    def get_new_commit_list(self, ref_path):
        """Get the list of parent new commits in order"""
        output = check_output((
            git_exe_path,
            'rev-list',
            self.commit_id,
            '--not',
            '--all',
            '--reverse',
        )).decode()
        commit_list = CommitList([], ref_path)
        for commit_id in output.splitlines():
            commit_list.append(Commit(commit_id, commit_list))
        return commit_list

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

    def content_can_fail(self):
        return any(
            t in ['HOTFIX', 'MESS', 'WIP'] for t in self.parse_tags()[0]
        )

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
                changed_files.append(CommittedFile(file_path, self, file_mode))
            self.changed_files = changed_files
        return self.changed_files


class CommittedFile(object):
    """Routines on a single committed file"""

    def __init__(self, path, commit=None, mode=None):
        self.path = path
        self.commit = commit
        self.mode = mode
        self.shebang = None
        self.not_consumed_content_proc = None

    def __str__(self):
        return '{} at {}'.format(self.path, self.commit)

    def __eq__(self, other):
        return (
            isinstance(other, CommittedFile) and
            self.path == other.path and
            self.commit == other.commit
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

    def get_content_proc(self, stdout=PIPE):
        """Return the content of a file on a commit as bytes"""
        if self.not_consumed_content_proc is not None:
            proc = self.not_consumed_content_proc
            self.not_consumed_content_proc = None
            return proc

        return Popen((
            git_exe_path,
            'show',
            self.commit.commit_id + ':' + self.path,
        ), stdout=stdout)

    def get_shebang(self):
        """Get the shebang from the file content

        The shebang is always on the first line.  It is not really part of
        the file, so we are trying to get it from the buffer that is going
        to be used later on checking the file content.  This is an optimistic
        approach that only works, if the first line is actually the shebang.
        """
        if self.shebang is None:
            assert self.not_consumed_content_proc is None
            proc = self.get_content_proc()
            line = proc.stdout.readline()
            if line.startswith(b'#!'):
                self.not_consumed_content_proc = proc
                self.shebang = line[len('#!'):].decode()
            else:
                self.shebang = ''

            if proc.poll() not in (None, 0):
                raise CalledProcessError(
                    'Git command returned non-zero exit status {}'
                    .format(proc.returncode)
                )
        return self.shebang

    def get_exe(self):
        shebang_split = self.get_shebang().split(None, 2)
        if not shebang_split:
            return ''
        if shebang_split[0] == '/usr/bin/env' and len(shebang_split) > 1:
            return shebang_split[1]
        return shebang_split[0].rsplit('/', 1)[-1]

    def write(self):
        with open(self.path, 'wb') as fd:
            proc = self.get_content_proc(fd)

        if proc.wait() != 0:
            raise CalledProcessError(
                'Git command returned non-zero exit status {}'
                .format(proc.returncode)
            )
