#!/usr/bin/env python

from setuptools import setup
import os

setup(name='process',
      install_requires=['distribute'],
      version='0.2.2',
      description='Automation tools for high performance computing environments',
      author='Aron Ahmadia',
      author_email='aron@ahmadia.net',
      url='http://github.com/ahmadia/process',
      packages=['ksl','ksl.process','ksl.process.install'],
      include_package_data=True,
      scripts=['scripts/kslinstall','scripts/kslrun'],
     )
