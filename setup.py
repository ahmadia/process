#!/usr/bin/env python

from distutils.core import setup
import os

setup(name='Process',
      version='0.1.0',
      description='Automation tools for high performance computing environments',
      author='Aron Ahmadia',
      author_email='aron@ahmadia.net',
      url='http://bitbucket.org/ahmadia/process',
      packages=['ksl'],
      scripts=['tools/kslinstall','tools/kslrun'],
      data_files=[('config/ppc64',['config/ppc64/kslinstall.py','config/ppc64/kslrun.py']),
                  ('config/x86_64',['config/x86_64/kslinstall.py','config/x86_64/kslrun.py']),
                  ('examples',os.listdir('examples')),
                  ('patches',os.listdir('patches')),
                  ('templates',['templates/module.ksl']),
                  ('test/sanity',os.listdir('test/sanity')),
                  ('test/system',os.listdir('test/system')),
                  ('test',['test/__init__.py','test/test_sanity.py']),
                  ('system_modules/ppc64/compilers',os.listdir('system_modules/ppc64/compilers')),
                  ('system_modules/x86_64/compilers',os.listdir('system_modules/x86_64/compilers')),
                  ('system_modules/shared/tools',os.listdir('system_modules/shared/tools')),
                  ]
     )
