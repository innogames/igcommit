"""igcommit - Git routines

Copyright (c) 2016, InnoGames GmbH
"""

from subprocess import check_output, CalledProcessError, Popen, PIPE, STDOUT

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
        self._content_proc = None
        self._message = None
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
        output = check_output([
            git_exe_path,
            'rev-list',
            self.commit_id,
            '--not',
            '--all',
            '--reverse',
        ]).decode()
        commit_list = CommitList([], ref_path)
        for commit_id in output.splitlines():
            commit = Commit(commit_id, commit_list)
            commit_list.append(commit)
        return commit_list

    def _fetch_content(self):
        self._content_proc = Popen(
            [git_exe_path, 'cat-file', '-p', self.commit_id],
            stdout=PIPE,
        )
        self._parents = []
        # The commit message starts after the empty line.  We iterate until
        # we find one, and then consume the rest as the message.
        for line in iter(self._content_proc.stdout.readline, b'\n'):
            if line.startswith(b'parent '):
                self._parents.append(Commit(line[len(b'parent '):].rstrip()))
            if line.startswith(b'author '):
                self._author = Contribution.parse(line[len(b'author '):])
            if line.startswith(b'committer '):
                self._committer = Contribution.parse(line[len(b'committer '):])
            check_returncode(self._content_proc)

    def get_parents(self):
        if not self._content_proc:
            self._fetch_content()
        return self._parents

    def get_author(self):
        if not self._content_proc:
            self._fetch_content()
        return self._author

    def get_committer(self):
        if not self._content_proc:
            self._fetch_content()
        return self._committer

    def get_contributors(self):
        yield self.get_author()
        yield self._committer

    def get_message(self):
        if not self._content_proc:
            self._fetch_content()
        if not self._message:
            self._message = self._content_proc.stdout.read().decode('utf8')
            check_returncode(self._content_proc)
        return self._message

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
            output = check_output([
                git_exe_path,
                'diff-tree',
                '-r',
                '--no-commit-id',
                '--break-rewrites',     # Get rewrites as additions
                '--no-renames',         # Get renames as additions
                '--diff-filter=AM',     # Only additions and modifications
                self.commit_id,
            ]).decode()
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


class Contribution(object):
    """Routines on contribution properties of a commit"""

    def __init__(self, name, email, timestamp):
        self.name = name
        self.email = email
        self.timestamp = timestamp

    @classmethod
    def parse(cls, line):
        """Parse the contribution line as bytes"""
        name, line = line.split(b' <', 1)
        email, line = line.split(b'> ', 1)
        timestamp, line = line.split(b' ', 1)
        return cls(name.decode('utf8'), email.decode(), int(timestamp))

    def get_email_domain(self):
        return self.email.split('@', 1)[-1]


class CommittedFile(object):
    """Routines on a single committed file"""

    def __init__(self, path, commit=None, mode=None):
        self.path = path
        self.commit = commit
        assert mode is None or len(mode) == 6
        self.mode = mode
        self._not_consumed_content_proc = None
        self._first_content_line = None

    def __str__(self):
        return '{} at {}'.format(self.path, self.commit)

    def __eq__(self, other):
        return (
            isinstance(other, CommittedFile) and
            self.path == other.path and
            self.commit == other.commit
        )

    def exists(self):
        return bool(check_output([
            git_exe_path,
            'ls-tree',
            '--name-only',
            '-r',
            self.commit.commit_id,
            self.path,
        ]))

    def changed(self):
        return self in self.commit.get_changed_files()

    def owner_can_execute(self):
        owner_bits = int(self.mode[-3])
        return bool(owner_bits & 1)

    def get_filename(self):
        return self.path.rsplit('/', 1)[-1]

    def get_extension(self):
        if '.' in self.path:
            return self.path.rsplit('.', 1)[1]
        return None

    def _spawn_content_proc(self, stdout=PIPE):
        """Spawn and return git process to get file content"""
        return Popen((
            git_exe_path, 'show', self.commit.commit_id + ':' + self.path
        ), stdout=stdout)

    def _get_first_content_line(self):
        """Save and return the first line of the file content

        We need the first line of the content for the symlinks and the shebang
        of the scripts.  We are saving the first line and the process we have
        used to get the first line to be re-used by the other methods below.
        """
        if self._first_content_line is None:
            assert self._not_consumed_content_proc is None
            proc = self._spawn_content_proc()
            self._first_content_line = proc.stdout.readline()
            check_returncode(proc)
            self._not_consumed_content_proc = proc
        return self._first_content_line

    def get_symlink_target(self):
        """Check if the file is a symlink and return its target"""
        if self.mode[1] == '2':
            return self._get_first_content_line().strip()
        return None

    def get_shebang(self):
        """Get the shebang from the file content"""
        line = self._get_first_content_line()
        if line.startswith(b'#!'):
            return line[len(b'#!'):].decode()
        return ''

    def get_exe(self):
        """Get the executable from the shebang"""
        shebang_split = self.get_shebang().split(None, 2)
        if not shebang_split:
            return ''
        if shebang_split[0] == '/usr/bin/env' and len(shebang_split) > 1:
            return shebang_split[1]
        return shebang_split[0].rsplit('/', 1)[-1]

    def get_content(self):
        """Get the file content as binary

        We have two ways of get the content.  If get_shebang() method is
        called before, we must have a file descriptor which has only the first
        line consumed.  We can consume the rest and append to the first line.
        """
        if self._not_consumed_content_proc is not None:
            assert self._first_content_line is not None
            content = self._first_content_line
            proc = self._not_consumed_content_proc
            self._not_consumed_content_proc = None
        else:
            content = b''
            proc = self._spawn_content_proc()

        content += proc.communicate()[0]
        check_returncode(proc)
        return content

    def pass_content(self, proc_args):
        """Pass the file content to another process

        We have two ways of passing the content.  If get_shebang() method is
        called before, we must have a file descriptor which has only the first
        line consumed.  In this case, we need to read and pass the content
        by ourselves.  If we don't yet have a file descriptor, we can take
        the shortcut and just pipe two processes together.

        It is not very nice to have two different ways of doing the same
        thing, though that is the most efficient method.  We would be wasting
        the Git content process by only reading the first line of it to get
        the shebang, if we wouldn't be using it in here.  Likewise things
        would be slower, if we buffer the content of every file in here
        to pass their content to the target process.  The shebang is only
        read for executable files, so most of the files should benefit from
        the optimization.  This is also an important optimization for
        parallelization.  The less we do on the main process, the more we can
        benefit from multiple cores on the system.  Before doing thing this
        way, I had the cute idea to pass the stdout of the content process
        we have used to get the shebang to the target process directly.  It
        was causing the line numbers on the syntax errors to be 1 off.
        """
        if self._not_consumed_content_proc is not None:
            content_proc = self._not_consumed_content_proc
            stdin = PIPE
        else:
            content_proc = self._spawn_content_proc()
            stdin = content_proc.stdout
        target_proc = Popen(proc_args, stdin=stdin, stdout=PIPE, stderr=STDOUT)
        # Someone has to check the output of the content process later.
        target_proc.content_proc = content_proc

        if self._not_consumed_content_proc is not None:
            stdin = target_proc.stdin
            stdin.write(self.get_content())
        stdin.close()   # Allow it to receive a SIGPIPE

        return target_proc

    def write(self):
        """Write the file contents to the location its supposed to be

        The Git pre-receive hooks can work on bare Git repositories.  Those
        repositories has no actual files, only the .git database.  We need
        to materialize the configuration files on their locations for
        the syntax checking tools to find them.  We are doing it efficiently
        by passing the writable file descriptor to the Git content process.
        """
        with open(self.path, 'wb') as fd:
            proc = self._spawn_content_proc(fd)
        proc.wait()
        check_returncode(proc)


def check_returncode(proc):
    if proc.returncode is None:
        proc.poll()
        if proc.returncode is None:
            return

    if proc.returncode != 0:
        raise CalledProcessError(proc.returncode, proc.args)
