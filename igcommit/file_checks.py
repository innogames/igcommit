"""igcommit - Checks on files committed to Git

Copyright (c) 2016, InnoGames GmbH
"""

from re import compile
from subprocess import CalledProcessError, Popen, PIPE, STDOUT

from igcommit.base_check import CheckState, BaseCheck
from igcommit.git import Commit, CommittedFile
from igcommit.utils import get_exe_path

file_extensions = {
    'pp': compile('^puppet'),
    'py': compile('^python'),
    'rb': compile('^ruby'),
    'sh': compile('sh$'),
    'js': compile('js$'),
    'php': compile('php$'),
}


class CommmittedFileCheck(BaseCheck):
    """Parent class for checks on a single committed file

    To check the files, we have to skip for_commit_list(), for_commit(),
    and clone ourself on for_committed_file().  The subclasses has additional
    logic on those to filter out themselves for some cases.
    """
    committed_file = None

    def prepare(self, obj):
        if not isinstance(obj, CommittedFile):
            return super(CommmittedFileCheck, self).prepare(obj)

        new = self.clone()
        new.committed_file = obj
        return new


class CheckExecutable(CommmittedFileCheck):
    """Special checks for executable files

    Git stores executable bits of the files.  We are running these checks only
    on the files executable bit is set.  It would have been nice to check
    the files which don't have this bit set, but has a shebang, at least
    to warn about it, as it is very common to omit executable bit on Git.
    However, it would be expensive to look at the content of every file.
    """
    def prepare(self, obj):
        if isinstance(obj, CommittedFile) and not obj.owner_can_execute():
            return None
        return super(CheckExecutable, self).prepare(obj)

    def get_problems(self):
        extension = self.committed_file.get_extension()
        if extension == 'sh':
            yield 'warning: executable has file extension .sh'

        shebang = self.committed_file.get_shebang()
        if not shebang:
            yield 'error: no shebang'
            self.set_state(CheckState.failed)
            return

        shebang_split = shebang.split(None, 2)
        if shebang_split[0] == '/usr/bin/env':
            if len(shebang_split) == 1:
                yield 'error: /usr/bin/env must have an argument'
                self.set_state(CheckState.failed)
                return
            exe = shebang_split[1]
        elif shebang_split[0].startswith('/'):
            if shebang_split[0].startswith('/usr'):
                yield 'warning: shebang is not portable (use /usr/bin/env)'
            exe = shebang_split[0].rsplit('/', 1)[1]
        else:
            exe = shebang_split[0]
            yield 'error: shebang executable {} is not full path'.format(exe)
            self.set_state(CheckState.failed)

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
                self.set_state(CheckState.failed)
        if extension:
            for key, pattern in file_extensions.items():
                if pattern.search(exe) and key != extension:
                    yield (
                        'error: shebang executable {} matches pattern of file '
                        'extension ".{}"'
                        .format(exe, key)
                    )
                    self.set_state(CheckState.failed)
        self.set_state(CheckState.done)

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.committed_file)


class CheckCommand(CommmittedFileCheck):
    """Check command to be executed on file contents"""
    args = None
    extension = None
    exe_path = None
    header = 0

    def __init__(self, args=None, extension=None, header=0, **kwargs):
        if args:
            self.args = args
        if extension:
            self.extension = extension
        if header:
            self.header = header
        super(CheckCommand, self).__init__(**kwargs)

    def clone(self):
        new = super(CheckCommand, self).clone()
        if self.args:
            new.args = self.args
        if self.extension:
            new.extension = self.extension
        if self.header:
            new.header = self.header
        if self.exe_path:
            new.exe_path = self.exe_path
        return new

    def get_exe_path(self):
        if not self.exe_path:
            self.exe_path = get_exe_path(self.args[0])
        return self.exe_path

    def prepare(self, obj):
        if not self.get_exe_path():
            return None

        new = super(CheckCommand, self).prepare(obj)
        if not isinstance(obj, CommittedFile):
            return new

        if (
            new.extension and
            obj.get_extension() != new.extension and
            not (
                new.extension in file_extensions and
                obj.exe and
                file_extensions[new.extension].search(obj.exe)
            )
        ):
            return None

        new.content_proc = obj.get_content_proc()
        new.check_proc = Popen(
            [self.get_exe_path()] + self.args[1:],
            stdin=new.content_proc.stdout,
            stdout=PIPE,
            stderr=STDOUT,
        )
        new.content_proc.stdout.close()   # Allow it to receive a SIGPIPE
        return new

    def get_problems(self):
        for line_id, line in enumerate(self.check_proc.stdout):
            if line_id >= self.header:
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
            self.set_state(CheckState.failed)
        else:
            self.set_state(CheckState.done)

    def _format_problem(self, line):
        """We are piping the source from Git to the commands.  We want to
        hide the file path from the users as we show it already on the headers.
        """
        prefix = ''

        line_split = line.split(':', 3)
        if (
            len(line_split) == 4 and
            len(line_split[0]) >= len('stdin') and
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

    def prepare(self, obj):
        new = super(CheckCommandWithConfig, self).prepare(obj)
        if not isinstance(obj, Commit):
            return new

        prev_commit = new.config_file.commit
        assert prev_commit != obj
        new.config_file.commit = obj

        if new.config_file.exists():
            # If the file is not changed on this commit, we can skip
            # downloading.
            if (
                not prev_commit or
                prev_commit.commit_list != obj.commit_list or
                new.config_file.changed()
            ):
                new.config_file.write()
        elif new.config_required:
            return None

        return new
