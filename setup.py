#!/usr/bin/env python
"""igcommit - Setup

Copyright (c) 2016, InnoGames GmbH
"""

from setuptools import setup

setup(
    name='igcommit',
    version='1.0',
    url='https://github.com/innogames/igcommit',
    packages=['igcommit'],
    entry_points={
        'console_scripts': [
            'igcommit-receive=igcommit.prereceive:Runner',
        ],
    },
)
