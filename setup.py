#!/usr/bin/env python
"""igcommit - InnoGames Commit Validation Script Setup

Copyright (c) 2016, InnoGames GmbH
"""

from distutils.core import setup

setup(
    name='igcommit',
    version='1.0',
    url='https://github.com/innogames/igcommit',
    packages=('igcommit', ),
    scripts=('igcommit-receive', ),
)
