"""igcommit - Checks on files committed to Git

Copyright (c) 2021 InnoGames GmbH
Portions Copyright (c) 2021 Emre Hasegeli
"""

from os import remove
from os.path import exists
from subprocess import PIPE, Popen, STDOUT

from igcommit.base_check import BaseCheck, CheckState, Severity
from igcommit.git import Commit, CommittedFile
from igcommit.utils import get_exe_path


class CommittedFileCheck(BaseCheck):
    """Parent class for checks on a single committed file

    To check the files, we have to clone ourself when we are being prepared
    for the CommittedFile.  The subclasses has additional logic on those
    to filter out themselves for some cases.
    """
    committed_file = None

    def prepare(self, obj):
        new = super(CommittedFileCheck, self).prepare(obj)
        if not new or not isinstance(obj, CommittedFile):
            return new

        new = new.clone()
        new.committed_file = obj
        return new

    def __str__(self):
        return '{} on {}'.format(type(self).__name__, self.committed_file)


class CheckExecutable(CommittedFileCheck):
    """Special checks for executable files

    Git stores executable bits of the files.  We are checking them together
    with the shebangs from the file contents.
    """
    file_extensions = {}
    general_names = []

    def get_problems(self):
        if self.committed_file.owner_can_execute():
            shebang = self.committed_file.get_shebang()
            if shebang:
                for problem in self.get_shebang_problems(shebang):
                    yield problem

                for problem in self.get_exe_problems():
                    yield problem
            else:
                yield Severity.ERROR, 'executable file without shebang'
        else:
            # We are not bothering to check the shebang for unknown file
            # extensions, because it's expensive to get the file contents.
            extension = self.committed_file.get_extension()
            if not extension or extension in self.file_extensions:
                if self.committed_file.get_shebang():
                    yield Severity.WARNING, 'non-executable file with shebang'

    def get_shebang_problems(self, shebang):
        if not shebang.startswith('/'):
            yield (
                Severity.ERROR,
                'shebang executable {} is not full path'.format(shebang)
            )
        elif shebang.startswith('/usr') and shebang != '/usr/bin/env':
            yield (
                Severity.WARNING, 'shebang is not portable (use /usr/bin/env)'
            )

    def get_exe_problems(self):
        extension = self.committed_file.get_extension()
        if not extension:
            name = self.committed_file.get_filename()
            if name in self.file_extensions:
                yield Severity.ERROR, 'file extension without a name'
            if name in self.general_names:
                yield Severity.WARNING, 'general executable name'
            return

        exe = self.committed_file.get_shebang_exe()
        if not exe:
            yield Severity.ERROR, 'no shebang executable'

        if extension in self.file_extensions:
            if not self.file_extensions[extension].search(exe):
                yield (
                    Severity.ERROR,
                    'shebang executable "{}" doesn\'t match pattern "{}"'
                    .format(exe, self.file_extensions[extension].pattern)
                )
                return

            # We are white-listing general names to have a file extension.
            name = self.committed_file.get_filename()[:-(len(extension) + 1)]
            if name not in self.general_names:
                yield Severity.WARNING, 'redundant file extension'
            return


class CheckSymlink(CommittedFileCheck):
    """Special check for symlinks"""
    def prepare(self, obj):
        new = super(CheckSymlink, self).prepare(obj)
        if not new or (
            isinstance(obj, CommittedFile) and not obj.symlink()
        ):
            return None
        return new

    def get_problems(self):
        target = self.committed_file.get_symlink_target()
        if not target or not target.exists():
            yield (
                Severity.WARNING,
                'symlink target {} doesn\'t exist on repository'
                .format(target)
            )


class CommittedFileByExtensionCheck(CommittedFileCheck):
    extension = None
    exe_pattern = None

    def prepare(self, obj):
        new = super(CommittedFileByExtensionCheck, self).prepare(obj)
        if not new or not isinstance(obj, CommittedFile):
            return new

        # All instances of this must specify a file extension.
        assert new.extension

        # We cannot rely on the file type, if it's under templates/.
        if 'templates/' in obj.path:
            return None

        # First, we try to match with the file extension.  We should not
        # continue for symlinks, because we cannot and should not validate
        # the file contents of them.
        if obj.get_extension() == new.extension and not obj.symlink():
            return new

        # Then, we try to match with the shebang from the file content,
        # if we know the executable pattern.
        if self.exe_pattern:
            exe = obj.get_shebang_exe()
            if exe and self.exe_pattern.search(exe):
                return new

        return None

    def __str__(self):
        return '{} "{}" on {}'.format(
            type(self).__name__, self.extension, self.committed_file
        )


class CheckCommand(CommittedFileByExtensionCheck):
    """Check command to be executed on file contents"""
    args = None
    exe_path = None
    header = 0
    footer = 0
    config_files = []
    config_required = False
    bogus_return_code = False

    def get_exe_path(self):
        if not self.exe_path:
            self.exe_path = get_exe_path(self.args[0])
        return self.exe_path

    def prepare(self, obj):
        new = super(CheckCommand, self).prepare(obj)
        if not new or not self.get_exe_path():
            return None

        if isinstance(obj, Commit):
            config_exists = new._prepare_configs(obj)
            if not config_exists and new.config_required:
                return None

        if isinstance(obj, CommittedFile):
            new._prepare_proc()

        return new

    def _prepare_configs(self, commit):
        """Update the configuration files, return true if any exist

        Git pre-receive hooks can work on bare Git repositories.  Those
        repositories has no actual files, only the .git database.  We
        need to materialize the configuration files on their locations
        for the check commands to find them.
        """
        # XXX: It is not really safe to manage those configuration files
        # like this.  The workspace might not be a good place to write
        # things.  Also, it is not safe to update these files, when they
        # are changed on different commits, because we run the commands
        # in parallel.  We are ignoring all those problems, until they
        # start happening on production.

        config_exists = False
        for config_file in self.config_files:
            prev_commit = config_file.commit
            config_file.commit = commit

            if config_file.exists():
                config_exists = True

                # If the file is not changed on this commit, we can skip
                # downloading.
                if (prev_commit and (
                    prev_commit == commit or not config_file.changed()
                )):
                    with open(config_file.path, 'wb') as fd:
                        fd.write(config_file.get_content())

            elif exists(config_file.path):
                remove(config_file.path)

        return config_exists

    def _prepare_proc(self):
        self._proc = Popen(
            [self.get_exe_path()] + self.args[1:],
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,
        )
        try:
            with self._proc.stdin as fd:
                fd.write(self.committed_file.get_content())
        except BrokenPipeError:
            pass

    def get_problems(self):
        line_buffer = []
        with self._proc.stdout as fd:
            for line_id, line in enumerate(fd):
                if line_id < self.header:
                    continue
                line_buffer.append(line)
                if len(line_buffer) <= self.footer:
                    continue
                yield self._format_problem(line_buffer.pop(0))

    def evaluate_problems(self):
        can_fail = self.committed_file.commit.content_can_fail()
        if can_fail and self.bogus_return_code:
            for item in super(CheckCommand, self).evaluate_problems():
                yield item
        else:
            for item in self.get_problems():
                yield item

        return_code = self._proc.wait()
        if can_fail and not self.bogus_return_code and return_code != 0:
            self.set_state(CheckState.FAILED)

    def _format_problem(self, line):
        """We are piping the source from Git to the commands.  We want to
        hide the file path from the users as we show it already on the headers.
        """
        prefix = ''
        rest = line.strip().decode('utf-8')

        rest_split = rest.split(':', 3)
        if (
            len(rest_split) == 4 and
            len(rest_split[0]) >= len('stdin') and
            rest_split[1].isdigit() and
            rest_split[2].isdigit()
        ):
            prefix = 'line {}: col {}: '.format(*rest_split[1:3])
            rest = rest_split[3].strip()
        else:
            if len(rest_split) >= 2 and 'stdin' in rest_split[0].lower():
                rest = ':'.join(rest_split[1:]).strip()
            if rest.startswith('line '):
                rest_split = rest.split(' ', 2)
                line_num = rest_split[1].strip(':,')
                if line_num.isdigit():
                    prefix += 'line ' + line_num + ': '
                    rest = ' '.join(rest_split[2:]).strip(':,')
            if rest.startswith('col '):
                rest_split = rest.split(' ', 2)
                col_num = rest_split[1].strip(':,')
                if col_num.isdigit():
                    prefix += 'col ' + col_num + ': '
                    rest = ' '.join(rest_split[2:]).strip(':,')

        severity, rest = Severity.split(rest)
        return severity, prefix + rest

    def __str__(self):
        return '{} "{}" on {}'.format(
            type(self).__name__, self.args[0], self.committed_file
        )


class CheckLoading(CommittedFileByExtensionCheck):
    load_func = None
    exception_cls = ValueError

    def get_problems(self):
        try:
            self.load_func(self.committed_file.get_content())
        except self.exception_cls as error:
            yield Severity.ERROR, str(error)
