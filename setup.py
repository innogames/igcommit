#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""igcommit - Setup

Copyright (c) 2017 InnoGames GmbH
"""

from setuptools import setup

from igcommit import VERSION
from igcommit.config import checks


with open('README.rst') as fd:
    readme = fd.read()

setup(
    name='igcommit',
    version='.'.join(str(v) for v in VERSION),
    url='https://github.com/innogames/igcommit',
    packages=['igcommit'],
    author='InnoGames System Administration',
    author_email='it@innogames.com',
    license='MIT',
    platforms='POSIX',
    description='Git pre-receive hook to check commits and code style',
    long_description=readme,
    keywords=(
        'syntax-checker git git-hook python ' +
        ' '.join(c.args[0] for c in checks if hasattr(c, 'args'))
    ),
    entry_points={
        'console_scripts': [
            'igcommit-receive=igcommit.prereceive:main',
        ],
    },
)
