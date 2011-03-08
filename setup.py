#!/usr/bin/env python

from distutils.core import setup
import os

def get_files(dir):
    return [os.path.join(dir,_file) for _file in os.listdir(dir) if os.path.isfile(os.path.join(dir,_file))]

setup(name='process',
      version='0.2.1',
      description='Automation tools for high performance computing environments',
      author='Aron Ahmadia',
      author_email='aron@ahmadia.net',
      url='http://bitbucket.org/ahmadia/process',
      packages=['ksl','ksl.process','ksl.process.install'],
      scripts=['scripts/kslinstall','scripts/kslrun'],
      data_files=[('examples',get_files('examples')),
                  ('examples/patches',get_files('examples/patches')),
                  ('system/config/ppc64',['system/config/ppc64/kslinstall.py','system/config/ppc64/kslrun.ini']),
                  ('system/config/x86_64',['system/config/x86_64/kslinstall.py','system/config/x86_64/kslrun.py']),
                  ('system/modules/ppc64/compilers',get_files('system/modules/ppc64/compilers')),
                  ('system/modules/x86_64/compilers',get_files('system/modules/x86_64/compilers')),
                  ('system/modules/shared/tools',get_files('system/modules/shared/tools')),
                  ('system/templates',['system/templates/module.ksl']),
                  ('test/sanity',get_files('test/sanity')),
                  ('test/system',get_files('test/system')),
                  ('test',['test/__init__.py','test/test_sanity.py']),
                  ]
     )
