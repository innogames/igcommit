#!/usr/bin/env python
"""igcommit - Checks on files committed to Git

Copyright (c) 2016, InnoGames GmbH
"""

from subprocess import Popen, PIPE, STDOUT
from igcommit.git import CommittedFile


class CheckCmd():
    """Check command to be executed on file contents"""
    def __init__(self, cmd, extension=None):
        self.cmd = cmd
        self.extension = extension

    def __str__(self):
        return '{} "{}"'.format(type(self).__name__, self.get_executable())

    def get_executable(self):
        return self.cmd.split(None, 1)[0]

    def relevant_on_commit(self, commit):
        return True

    def get_problems(self, changed_file):
        if self.extension and self.extension != changed_file.get_extension():
            return
        process = Popen(
            self.cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT
        )
        content = changed_file.get_content()
        output = process.communicate(content)[0]
        if process.returncode != 0:
            for line in output.splitlines():
                yield line.decode().strip()


class CheckCmdWithConfig(CheckCmd):
    def __init__(self, cmd, config_name, **kwargs):
        super(CheckCmdWithConfig, self).__init__(cmd, **kwargs)
        self.config_file = CommittedFile(None, config_name)

    def relevant_on_commit(self, commit):
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
