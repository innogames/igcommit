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
    'php': re.compile('php$'),
}


class CommmittedFileCheck(BaseCheck):
    """Parent class for checks on a single committed file

    To check the files, we have to skip for_commit_list(), for_commit(),
    and clone ourself on for_committed_file().  The subclasses has additional
    logic on those to filter out themselves for some cases.
    """
    committed_file = None

    def for_committed_file(self, committed_file):
        new = self.clone()
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
        if not committed_file.owner_can_execute():
            return None
        return super(CheckExecutable, self).for_committed_file(committed_file)

    def get_problems(self):
        extension = self.committed_file.get_extension()
        if extension == 'sh':
            yield 'warning: executable has file extension .sh'

        shebang = self.committed_file.get_shebang()
        if not shebang:
            yield 'error: no shebang'
            self.failed = True
            return

        shebang_split = shebang.split(None, 2)
        if shebang_split[0] == '/usr/bin/env':
            if len(shebang_split) == 1:
                yield 'error: /usr/bin/env must have an argument'
                self.failed = True
                return
            exe = shebang_split[1]
        elif shebang_split[0].startswith('/'):
            if shebang_split[0].startswith('/usr'):
                yield 'warning: shebang is not portable (use /usr/bin/env)'
            exe = shebang_split[0].rsplit('/', 1)[1]
        else:
            exe = shebang_split[0]
            yield 'error: shebang executable {} is not full path'.format(exe)
            self.failed = True

        # We are saving the executable name on the file to let it be used
        # by the following checks.  TODO Make it more robust.
        self.committed_file.exe = exe

        if extension in file_extensions:
            if not file_extensions[extension].search(exe):
                yield (
                    'error: shebang executable "{}" doesn\'t match '
                    'pattern "{}"'
                    .format(exe, file_extensions[extension].pattern)
                )
                self.failed = True
        if extension:
            for key, pattern in file_extensions.items():
                if pattern.search(exe) and key != extension:
                    yield (
                        'error: shebang executable {} matches pattern of file '
                        'extension ".{}"'
                        .format(exe, key)
                    )
                    self.failed = True

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.committed_file)


class CheckCommand(CommmittedFileCheck):
    """Check command to be executed on file contents"""
    args = None
    extension = None
    exe_path = None

    def __init__(self, args=None, extension=None, **kwargs):
        if args:
            self.args = args
        if extension:
            self.extension = extension
        super(CheckCommand, self).__init__(**kwargs)

    def clone(self):
        new = super(CheckCommand, self).clone()
        if self.args:
            new.args = self.args
        if self.extension:
            new.extension = self.extension
        if self.exe_path:
            new.exe_path = self.exe_path
        return new

    def get_exe_path(self):
        if not self.exe_path:
            self.exe_path = get_exe_path(self.args[0])
        return self.exe_path

    def for_commit_list(self, commit_list):
        if not self.get_exe_path():
            return None
        return super(CheckCommand, self).for_commit_list(commit_list)

    def for_committed_file(self, committed_file):
        if (
            self.extension and
            committed_file.get_extension() != self.extension and
            not (
                self.extension in file_extensions and
                committed_file.exe and
                file_extensions[self.extension].search(committed_file.exe)
            )
        ):
            return None
        new = super(CheckCommand, self).for_committed_file(committed_file)
        new.content_proc = committed_file.get_content_proc()
        new.check_proc = Popen(
            [self.get_exe_path()] + self.args[1:],
            stdin=new.content_proc.stdout,
            stdout=PIPE,
            stderr=STDOUT,
        )
        new.content_proc.stdout.close()   # Allow it to receive a SIGPIPE
        return new

    def get_problems(self):
        for line in self.check_proc.stdout:
            yield self._format_problem(line.strip().decode())

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

    def _format_problem(self, line):
        """We are piping the source from Git to the commands.  We want to
        hide the file path from the users as we show it already on the headers.
        """
        prefix = ''

        line_split = line.split(':', 3)
        if (
            len(line_split) == 4 and
            len(line_split[0]) < len('--/dev/stdin--') and
            ('stdin' in line_split[0].lower() or line_split[0] == 'input') and
            line_split[1].isdigit() and
            line_split[2].isdigit()
        ):
            prefix = 'line {} col {}: '.format(*line_split[1:3])
            line = line_split[3].strip()

        for severity in ['info', 'warning', 'error']:
            if line.lower().startswith(severity):
                prefix = severity + ': ' + prefix
                line = line[len(severity):].strip(' :-')
                break

        return prefix + line

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
    config_required = False

    def __init__(self, args=None, config_name=None, config_required=False,
                 **kwargs):
        super(CheckCommandWithConfig, self).__init__(args, **kwargs)
        if config_name:
            self.config_file = CommittedFile(None, config_name)
        if config_required:
            self.config_required = True

    def clone(self):
        new = super(CheckCommandWithConfig, self).clone()
        new.config_file = self.config_file
        if self.config_required:
            new.config_required = self.config_required
        return new

    def for_commit(self, commit):
        prev_commit = self.config_file.commit
        assert prev_commit != commit
        self.config_file.commit = commit

        if self.config_file.exists():
            # If the file is not changed on this commit, we can skip
            # downloading.
            if (
                not prev_commit or
                prev_commit.commit_list != commit.commit_list or
                self.config_file.changed()
            ):
                self.config_file.write()
        elif self.config_required:
            return None

        return self
