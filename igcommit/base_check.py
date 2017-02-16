"""igcommit - The base check class

Copyright (c) 2016, InnoGames GmbH
"""


class CheckState(object):
    new = 0
    cloned = 1
    done = 2
    failed = 3


class BaseCheck(object):
    """The parent class of all checks

    Checks are expanded to different objects by cloning.  The subclasses
    has to extend for_commit_list(), for_commit(), and/or for_committed_file()
    methods to clone the check.
    """
    preferred_checks = []
    state = CheckState.new

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            # We expect all of the arguments to be initialized with defaults
            # on the class.
            assert hasattr(type(self), key)
            if value:
                setattr(self, key, value)

    def clone(self):
        new = type(self)(**vars(self))
        new.state = CheckState.cloned
        return new

    def set_state(self, state):
        assert state > CheckState.cloned
        self.state = max(self.state, state)

    def prepare(self, obj):
        for check in self.preferred_checks:
            if check.prepare(obj):
                return None
        return self

    def print_problems(self):
        header_printed = False
        for problem in self.get_problems():
            if not header_printed:
                print('=== {} ==='.format(self))
                header_printed = True
            print('* ' + problem)
        if header_printed:
            print('')

    def __str__(self):
        return type(self).__name__


def prepare_checks(checks, obj, next_checks=None):
    """Prepare the checks to the object

    It yields the checks prepared and ready.  The checks which are not
    ready yet are going do be appended to the next_checks list.
    """
    for check in checks:
        prepared_check = check.prepare(obj)
        if prepared_check:
            cloned = prepared_check.state >= CheckState.cloned
            assert next_checks is not None or cloned

            if cloned:
                yield prepared_check
            else:
                next_checks.append(prepared_check)
