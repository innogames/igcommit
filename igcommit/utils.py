"""igcommit - Utility functions

Copyright (c) 2016, InnoGames GmbH
"""

from os import environ, access, X_OK


def get_exe_path(exe):
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
