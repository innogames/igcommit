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


def iter_buffer(generator, amount):
    """Iterate with buffering

    This is a utility function that's useful for asynchronous processing.
    It buffers the elements of the given generator to earn time for items
    to do their processing.

    The argument is assumed to be a generator (although it would work with
    any iterable) that generates items which start their processing in
    the background at the time they are generated.  And the caller is assumed
    to consume those items when their processing is complete.

    This function is going to maintain a FIFO buffer up to the given size.
    It'd start with an empty buffer (memo), buffer all of the generated items
    until the buffer is full or the generator starts generating None, then
    start adding items to the end yielding from the beginning of the buffer,
    and finally yield the ones that are left in the buffer after the generator
    is consumed.

    The buffering is short-cut when the generator generates None as the next
    item.  This is a useful feature when the caller needs to wait for some
    item in the buffer to complete.  The generated None's are never yielded
    to the caller.

    Note that this procedure does not support out-of-order consumption of
    the items.  The caller would always have to wait for the first yielded
    item to be done with its processing.  While the caller is waiting,
    another item in the buffer may become ready, but we wouldn't even know.
    This is how this function remains very simple.
    """
    assert amount > 1
    memo = []
    for elem in generator:
        if elem is not None:
            memo.append(elem)
            if len(memo) < amount:
                continue
        yield memo.pop(0)

    for elem in memo:
        yield elem
