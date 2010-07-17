from UserDict import UserDict
import zipfile
import tarfile
from os.path import exists, join
from os import pathsep
from string import split

class steps(UserDict):
    def __init__(self, dict={}):
        UserDict.__init__(self, dict)
    
    def load_modules(self):
        for module in self['modules']:
            load_module(module)
    
    def unpack_source(self):
        archivename = self['source']
        builddir = self['builddir']
        archive = find_file(archivename, self['sourcepaths'])
        
        if 'tar' in archive:
            unpack(archive, tarfile.open, builddir)
        else if 'zip' in archive:
            unpack(archive, zipfile.open, builddir)
        else:
            raise Exception('unrecognize install source archive format: %s' % archive)

        shell_command('cd %s', abspath(builddir))
        
    def configure(self, args=None):
        shell_command(
    
    def apply_mod():
        pass
    
    def make():
        pass
    
    def makeinstall():
        pass

def find_file(filename, search_path):
    file_found = False
    paths = split(search_path, paths):
    for path in paths:
        if exists(join(path, filename)):
            file_found = True
            return abspath(join(path,filename))
    raise Exception('unable to locate file: %s on search path: %s' % filename, search_path)

def unpack(archive, open, builddir):
    unpacker = open(archive)
    unpacker.extractall(builddir)
    unpacker.close()

# DSL-ify this class
load_modules = steps.load_modules
unpack_source = steps.unpack_source
configure = steps.configure
apply_mod = steps.apply_mod
make = steps.make
makeinstall = steps.makeinstall
