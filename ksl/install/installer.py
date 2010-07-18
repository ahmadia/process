import zipfile
import tarfile
import logging
from os.path import exists, join
from os import pathsep
from string import split

class installer:
    def __init__(self, data=None):
        if data is not None:
            self = buildFromData(self,data)
        self.log = logging.getLogger('ksl.installer.package')

    def load_modules(self):
        # always load genie when using modules to get common environment variables
        self.logger.info("loading module: genie")
        module_cmd("load genie")
        
        for module in self['modules']:
            self.logger.info("loading module: %s" % module)
            module_cmd("load %s", module)
    
    def unpack_source(self):
        archive_name = self.source
        build_dir = self.build_dir
        archive = find_file(archive_name, self.source_paths)
        self.log.info("unpacking source file %s into %s" % archive, build_dir)
        
        if 'tar' in archive:
            unpack(archive, tarfile.open, build_dir)
        elif 'zip' in archive:
            unpack(archive, zipfile.open, build_dir)
        else:
            raise Exception('unrecognized install source archive format: %s' % archive)

        shell_command('cd %s' % abspath(build_dir))
        
    def configure(self, args=''):
        target_dir = self.target_dir
        shell_command('./configure --prefix=%s %s' % (target_dir, args), 'configure') 
    
    def apply_patch(self, patch_name):
        patch = find_file(patch_name, self.patch_paths)
        shell_command('patch -p1 -i %s' % (patch), 'patch')
    
    def make(self):
        shell_command('make', 'make')
    
    def make_install(self):
        shell_command('make install', 'make')

    def shell_command(self, command, log_file=''):
        if log_file is not '':
            log = logging.getLogger('ksl.installer.package.%s', log_file)
        else:
            log = self.log
        log.info(command)
        p = subprocess.Popen(command, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        err_code = p.wait()
        return_data = p.stdout.read()
        log.info(return_data) 
        if err_code:
            err_msg = "command %s failed, see log for details" % command
            log.error(err_msg)
            raise Exception(err_msg)
                          
def find_file(filename, search_path):
    file_found = False
    paths = split(search_path, paths)
    for path in paths:
        if exists(join(path, filename)):
            file_found = True
            return abspath(join(path,filename))
    err_msg = 'unable to locate file: %s on search path: %s' % filename, search_path
    self.log.error(err_msg)
    raise Exception(err_msg)

def unpack(archive, unpacker, build_dir):
    try:
        u = unpacker(archive)
        u.extractall(build_dir)
        u.close()
    except Exception, err:
        self.log.error('error during unpack: %s', err)
        raise

def module_cmd(module_args):
    p = subprocess.Popen('%s python %s' % (self.module_cmd,module_args),
                         shell=True, stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
    (commands, ignore) = p.communicate()

    if p.returncode is not None and p.returncode % 256:
        err = "Error issuing module command %s\n" % (module_args)
        self.log.error(commands)
        raise BuildError("unexpected failure issuing module command: %s" % module_args)
    exec commands

# DSL-ify this class
load_modules = installer.load_modules
unpack_source = installer.unpack_source
configure = installer.configure
apply_patch = installer.apply_patch
make = installer.make
make_install = installer.make_install
