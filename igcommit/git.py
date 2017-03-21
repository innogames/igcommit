"""igcommit - Git routines

Copyright (c) 2016, InnoGames GmbH
"""

from subprocess import check_output

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
        self.content_fetched = False
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
        content = check_output(
            [git_exe_path, 'cat-file', '-p', self.commit_id]
        )
        self._parents = []
        self._message_lines = []
        # The commit message starts after the empty line.  We iterate until
        # we find one, and then consume the rest as the message.
        lines = iter(content.splitlines())
        for line in lines:
            if not line:
                break
            if line.startswith(b'parent '):
                self._parents.append(Commit(line[len(b'parent '):].rstrip()))
            elif line.startswith(b'author '):
                self._author = Contribution.parse(line[len(b'author '):])
            elif line.startswith(b'committer '):
                self._committer = Contribution.parse(line[len(b'committer '):])
        for line in lines:
            self._message_lines.append(line.decode())
        self.content_fetched = True

    def get_parents(self):
        if not self.content_fetched:
            self._fetch_content()
        return self._parents

    def get_author(self):
        if not self.content_fetched:
            self._fetch_content()
        return self._author

    def get_committer(self):
        if not self.content_fetched:
            self._fetch_content()
        return self._committer

    def get_contributors(self):
        yield self.get_author()
        yield self._committer

    def get_message_lines(self):
        if not self.content_fetched:
            self._fetch_content()
        return self._message_lines

    def get_summary(self):
        return self.get_message_lines()[0]

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
                '--root',               # Get the initial commit as additions
                '--no-commit-id',       # We already know the commit id.
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
        self.content = None

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

    def symlink(self):
        return self.mode[1] == '2'

    def owner_can_execute(self):
        owner_bits = int(self.mode[-3])
        return bool(owner_bits & 1)

    def get_filename(self):
        return self.path.rsplit('/', 1)[-1]

    def get_extension(self):
        if '.' in self.path:
            return self.path.rsplit('.', 1)[1]
        return None

    def get_content(self):
        """Get the file content as binary"""
        if self.content is None:
            self.content = check_output([
                git_exe_path, 'show', self.commit.commit_id + ':' + self.path
            ])
        return self.content

    def get_shebang(self):
        """Get the shebang from the file content"""
        content = self.get_content()
        if content.startswith(b'#!'):
            return content[len(b'#!'):].split(None, 1)[0].decode()
        return None

    def get_shebang_exe(self):
        """Get the executable from the shebang"""
        shebang = self.get_shebang()
        if shebang == '/usr/bin/env':
            rest = self.get_content().splitlines()[0][len(b'#!/usr/bin/env'):]
            rest_split = rest.split(None, 1)
            if rest_split:
                return rest_split[0].decode()
        elif shebang:
            return shebang.rsplit('/', 1)[-1]
        return None

    def write(self):
        """Write the file contents to the location its supposed to be

        The Git pre-receive hooks can work on bare Git repositories.  Those
        repositories has no actual files, only the .git database.  We need
        to materialize the configuration files on their locations for
        the syntax checking tools to find them.
        """
        with open(self.path, 'wb') as fd:
            fd.write(self.get_content())
