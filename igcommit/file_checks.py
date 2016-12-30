"""igcommit - Checks on files committed to Git

Copyright (c) 2016, InnoGames GmbH
"""

import re
from subprocess import CalledProcessError, Popen, PIPE, STDOUT

from igcommit.base_check import BaseCheck
from igcommit.git import CommittedFile
from igcommit.utils import get_exe_path

file_extensions = {
    'pp': re.compile('^puppet'),
    'py': re.compile('^python'),
    'rb': re.compile('^ruby'),
    'sh': re.compile('sh$'),
    'js': re.compile('js$'),
}


class CommmittedFileCheck(BaseCheck):
    """Parent class for checks on a single committed file

    To check the files, we have to skip for_commit_list(), for_commit(),
    and clone ourself on for_committed_file().  The subclasses has additional
    logic on those to filter out themselves for some cases.
    """
    committed_file = None

    def for_commit_list(self, commit_list):
        return self

    def for_commit(self, commit):
        return self

    def for_committed_file(self, committed_file):
        new = type(self)()
        new.committed_file = committed_file
        new.ready = True
        return new


class CheckExecutable(CommmittedFileCheck):
    """Special checks for executable files

    Git stores executable bits of the files.  We are running these checks only
    on the files executable bit is set.  It would have been nice to check
    the files which don't have this bit set, but has a shebang, at least
    to warn about it, as it is very common to omit executable bit on Git.
    However, it would be expensive to look at the content of every file.
    """
    def for_committed_file(self, committed_file):
        if committed_file.owner_can_execute():
            return super(CheckExecutable, self).for_committed_file(
                committed_file
            )

    def get_problems(self):
        extension = self.committed_file.get_extension()
        if extension == 'sh':
            yield 'executable has file extension .sh'

        shebang = self.committed_file.get_shebang()
        if not shebang:
            yield 'no shebang'
            self.failed = True
            return

        shebang_split = shebang.split(None, 2)
        if shebang_split[0] == '/usr/bin/env':
            if len(shebang_split) == 1:
                yield '/usr/bin/env must have an argument'
                self.failed = True
                return
            exe = shebang_split[1]
        elif shebang_split[0].startswith('/'):
            if shebang_split[0].startswith('/usr'):
                yield 'shebang is not portable (use /usr/bin/env)'
            exe = shebang_split[0].rsplit('/', 1)[1]
        else:
            exe = shebang_split[0]
            yield 'shebang executable {} is not full path'.format(exe)
            self.failed = True

        # We are saving the executable name on the file to let it be used
        # by the following checks.  TODO Make it more robust.
        self.committed_file.exe = exe

        if extension in file_extensions:
            if not file_extensions[extension].search(exe):
                yield (
                    'shebang executable "{}" doesn\'t match pattern "{}"'
                    .format(exe, file_extensions[extension].pattern)
                )
                self.failed = True
        if extension:
            for key, pattern in file_extensions.items():
                if pattern.search(exe) and key != extension:
                    yield (
                        'shebang executable {} matches pattern of file '
                        'extension ".{}"'
                        .format(exe, key)
                    )
                    self.failed = True

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.committed_file)


class CheckCommand(CommmittedFileCheck):
    """Check command to be executed on file contents"""
    exe_path = None

    def __init__(self, args=None, extension=None):
        self.args = args
        self.extension = extension

    def get_exe_path(self):
        if not self.exe_path:
            self.exe_path = get_exe_path(self.args[0])
        return self.exe_path

    def for_commit_list(self, commit_list):
        if self.get_exe_path():
            return self

    def for_committed_file(self, committed_file):
        if not self.possible_for_committed_file(committed_file):
            return None
        new = super(CheckCommand, self).for_committed_file(committed_file)
        new.args = self.args
        new.extension = self.extension
        new.exe_path = self.get_exe_path()
        new.content_proc = committed_file.get_content_proc()
        new.check_proc = Popen(
            (self.get_exe_path(), ) + self.args[1:],
            stdin=new.content_proc.stdout,
            stdout=PIPE,
            stderr=STDOUT,
        )
        new.content_proc.stdout.close()   # Allow it to receive a SIGPIPE
        return new

    def possible_for_committed_file(self, committed_file):
        return (
            not self.extension or
            committed_file.get_extension() == self.extension or (
                self.extension in file_extensions and
                committed_file.exe and
                file_extensions[self.extension].search(committed_file.exe)
            )
        )

    def get_problems(self):
        for line in self.check_proc.stdout:
            line = line.strip().decode()
            if line.startswith('/dev/stdin:'):
                line = 'line ' + line[len('/dev/stdin:'):]
            yield line

        if self.content_proc.poll() != 0:
            raise CalledProcessError(
                'Git command returned non-zero exit status {}'
                .format(self.content_proc.returncode)
            )
        if (
            self.check_proc.wait() != 0 and
            not self.committed_file.commit.content_can_fail()
        ):
            self.failed = True

    def __str__(self):
        return '{} "{}" on {}'.format(
            type(self).__name__, self.args[0], self.committed_file
        )


class CheckCommandWithConfig(CheckCommand):
    """CheckCommand which requires a configuration file

    We have to download the configuration file to the current workspace
    to let the command find it.  It is not really safe to do that.
    The workspace might not be a good place to write things.  Also, it is
    not safe to update this file, when it is changed on different commits,
    because we run the commands in parallel.  We are ignoring those problems,
    until they start happening on production.
    """
    def __init__(self, args=None, config_name=None, **kwargs):
        super(CheckCommandWithConfig, self).__init__(args, **kwargs)
        self.config_file = CommittedFile(None, config_name)

    def for_commit(self, commit):
        prev_commit = self.config_file.commit
        assert prev_commit != commit
        self.config_file.commit = commit
        if not self.config_file.exists():
            return None

        # If the file is not changed on this commit, we can skip
        # downloading.
        if (
            not prev_commit or
            prev_commit.commit_list != commit.commit_list or
            self.config_file.changed()
        ):
            self.config_file.write()

        return self
