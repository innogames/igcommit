"""igcommit - Utility functions

Copyright (c) 2021 InnoGames GmbH
Portions Copyright (c) 2021 Emre Hasegeli
"""

from os import X_OK, access, environ


def get_exe_path(exe):
    """Traverse the PATH to find where the executable is

    This should behave similar to the shell built-in "which".
    """
    for dir_path in environ['PATH'].split(':'):
        path = dir_path.strip('"') + '/' + exe
        if access(path, X_OK):
            return path


def iter_buffer(iterable, amount):
    assert amount > 1
    memo = []
    for elem in iterable:
        if elem is not None:
            memo.append(elem)
            if len(memo) < amount:
                continue
        yield memo.pop(0)

    for elem in memo:
        yield elem
