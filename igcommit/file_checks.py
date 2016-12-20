#!/usr/bin/env python
"""igcommit - Checks on files committed to Git

Copyright (c) 2016, InnoGames GmbH
"""

from os import environ, access, X_OK
from subprocess import Popen, PIPE, STDOUT
from igcommit.git import CommittedFile


class CheckCmd():
    """Check command to be executed on file contents"""
    def __init__(self, args, extension=None):
        assert args
        self.args = args
        self.extension = extension

    def __str__(self):
        return '{} "{}"'.format(type(self).__name__, self.args[0])

    def get_executable_path(self):
        for dir_path in environ['PATH'].split(':'):
            path = dir_path.strip('"') + '/' + self.args[0]
            if access(path, X_OK):
                return path

    def possible(self, commit):
        return bool(self.get_executable_path())

    def get_problems(self, changed_file):
        if self.extension and self.extension != changed_file.get_extension():
            return
        args = (self.get_executable_path(), ) + self.args[1:]
        process = Popen(args, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
        content = changed_file.get_content()
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
