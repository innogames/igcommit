"""igcommit - Checks on files committed to Git

Copyright (c) 2016, InnoGames GmbH
"""

import re
from os import environ, access, X_OK
from subprocess import Popen, PIPE, STDOUT

from igcommit.git import Check, CommittedFile

file_extensions = {
    'pp': re.compile('^puppet'),
    'py': re.compile('^python'),
    'rb': re.compile('^ruby'),
    'sh': re.compile('sh$'),
    'js': re.compile('js$'),
}


class CheckExe(Check):
    def possible_on_file(self, committed_file):
        return committed_file.owner_can_execute()

    def get_problems(self, committed_file):
        if not committed_file.get_shebang():
            yield 'no shebang'

        extension = committed_file.get_extension()
        if extension == 'sh':
            yield 'executable has file extension .sh'


class CheckShebang(Check):
    def possible_on_file(self, committed_file):
        # We could check all files with Shebang, but that would be
        # too expensive.
        return (
            (
                committed_file.get_extension() in file_extensions or
                committed_file.owner_can_execute()
            ) and
            bool(committed_file.get_shebang())
        )

    def get_problems(self, committed_file):
        if not committed_file.owner_can_execute:
            yield 'non-executable'

        shebang_split = committed_file.get_shebang().split(None, 2)
        exe = shebang_split[0]
        if not exe.startswith('/'):
            yield 'executable is not full path'

        if exe == '/usr/bin/env':
            if len(shebang_split) == 1:
                yield '/usr/bin/env must have an argument'
            return

        if exe.startswith('/usr/bin'):
            yield 'shebang is not portable (use /usr/bin/env)'


class CheckShebangExe(CheckShebang):
    def possible_on_file(self, committed_file):
        return (
            super(CheckShebangExe, self).possible_on_file(committed_file) and
            bool(committed_file.get_extension())
        )

    def get_problems(self, committed_file):
        extension = committed_file.get_extension()
        exe = committed_file.get_shebang_exe()
        if extension in file_extensions:
            if not file_extensions[extension].match(exe):
                yield (
                    "shebang executable doesn't match pattern {}"
                    .format(file_extensions[extension].pattern)
                )
        for key, pattern in file_extensions.items():
            if pattern.match(exe) and key != extension:
                yield (
                    'shebang matches pattern of file extension {}'
                    .format(key)
                )


class CheckCmd(Check):
    """Check command to be executed on file contents"""
    def __init__(self, args, extension=None):
        assert args
        self.args = args
        self.extension = extension
        self.pattern = file_extensions.get(extension)

    def __str__(self):
        return '{} "{}"'.format(type(self).__name__, self.args[0])

    def get_exe_path(self):
        for dir_path in environ['PATH'].split(':'):
            path = dir_path.strip('"') + '/' + self.args[0]
            if access(path, X_OK):
                return path

    def possible_on_commit(self, commit):
        return bool(self.get_exe_path())

    def possible_on_file(self, committed_file):
        if not self.extension:
            return True

        file_extension = committed_file.get_extension()
        if file_extension == self.extension:
            return True

        if self.pattern:
            exe = committed_file.get_shebang_exe()
            if exe and self.pattern.match(exe):
                return True

        return False

    def get_problems(self, committed_file):
        args = (self.get_exe_path(), ) + self.args[1:]
        process = Popen(args, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
        content = committed_file.get_content()
        output = process.communicate(content)[0].decode()
        if process.returncode != 0:
            for line in output.splitlines():
                if line.startswith('/dev/stdin:'):
                    line = 'line ' + line[len('/dev/stdin:'):]
                yield line


class CheckCmdWithConfig(CheckCmd):
    def __init__(self, args, config_name, **kwargs):
        super(CheckCmdWithConfig, self).__init__(args, **kwargs)
        self.config_file = CommittedFile(None, config_name)

    def possible(self, commit):
        if not super(CheckCmdWithConfig, self).possible(commit):
            return False

        prev_commit = self.config_file.commit
        assert prev_commit != commit
        self.config_file.commit = commit
        if not self.config_file.exists():
            return False

        # If the file is not changed on this commit, we can skip downloading.
        if prev_commit and not self.config_file.changed():
            return True

        self.config_file.write()
        return True
