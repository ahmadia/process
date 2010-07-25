import zipfile
import tarfile
import logging
import subprocess
import os
from os.path import exists, join, abspath, splitext, normpath
from os import pathsep, chdir
from string import split
from string import Template
from inspect import getmembers

class installer:
    def __init__(self, data=None):
        if data is not None:
            self = buildFromData(self,data)
        self.log = logging.getLogger('ksl.installer.package')
        self.modulesLoaded = False

    def install(self):
        self.log.info('beginning installation')
        num_steps = len(self.install_steps)
        for step_no, step in zip(range(1,num_steps+1),self.install_steps):
            self.log.info('on step %d, %s' % (step_no, step))
            if callable(step):
                step(self)
            else:
                step_fun = step[0]
                step_fun(self,*step[1:])

        if self.modulesLoaded:
            self.unload_modules()

    def install_module(self):
        self.log.info('beginning module installation')
        template_data = open(self.module_template, 'r')
        template = Template(template_data.read())
        template_data.close()

        add_root = lambda p: normpath(join(self.target_dir,p))

        self.UNAME            = self.name.upper()
        self.binaries_pretty  = ", ".join(b for b in self.binaries)
        self.paths_pretty     = ", ".join(add_root(p) for p in self.paths)
        if not self.paths:
            self.paths_command = "$::env(PATH)"
        else:
            self.paths_command    = "$::env(PATH):" + ":".join(add_root(p) for p in self.paths)

        self.paths_fake       = "\$(PATH):" + ":".join(add_root(p) for p in self.paths)
        
        self.includes_pretty  = ", ".join(add_root(p) for p in self.includes)
        if not self.includes:
            self.includes_command = ""
        else:
            self.includes_command = "-I"+" -I".join(add_root(p) for p in self.includes)
        self.libdirs_pretty   = ", ".join(add_root(p) for p in self.libdirs)
        self.libs_pretty      = ", ".join(l for l in self.libs)

        lib_strip = lambda l: splitext(l)[0].replace('lib','-l')
        self.libpaths_command  = ":".join(add_root(p) for p in self.libdirs)
        if not self.libs:
            self.libs_command  = ""
        else:
            if 'add_rpaths' in dir(self) and self.add_rpaths:
                self.libs_command  = "-L"+" -L".join(add_root(p) for p in self.libdirs) + \
                                     " -R"+" -R".join(add_root(p) for p in self.libdirs) + \
                                     "".join(" %s" % (lib_strip(l)) for l in self.libs)
            else:
                self.libs_command  = "-L"+" -L".join(add_root(p) for p in self.libdirs) + \
                                     "".join(" %s" % (lib_strip(l)) for l in self.libs)
            
        self.modules_pretty   = " ".join(m for m in self.required_modules)
        if not self.required_modules:
            self.modules_command = ""
        else:
            self.modules_command  = "module load " + " ".join(m for m in self.required_modules)

        # oh man is this dirty        
        module_data = template.substitute(dict(getmembers(self)))
        self.log.info("installing module file %s with contents:" % self.module_file)
        self.log.info(module_data)

        handle = open(self.module_file,'w')
        handle.write(module_data)
        handle.close()
        
    def unload_modules(self):
        self.log.info("unloading module: genie")

        self.module('unload genie')

        for module in self.required_modules:
            self.log.info("unloading module: %s" % module)
            self.module("unload %s" % module)
        
        for module in self.compile_modules:
            self.log.info("unloading module: %s" % module)
            self.module("unload %s" % module)

    def load_modules(self):
        # always load genie when using modules to get common environment variables
        self.log.info("loading module: genie")

        self.module('load genie')
        
        for module in self.compile_modules:
            self.log.info("loading module: %s" % module)
            self.module("load %s" % module)

        for module in self.required_modules:
            self.log.info("loading module: %s" % module)
            self.module("load %s" % module)

        self.modulesLoaded = True
    
    def unpack_source(self):
        archive_name = self.source
        build_dir = self.build_dir
        archive = self.find_file(archive_name, self.source_paths)
        self.log.info("unpacking source file %s into %s" % (archive, build_dir))
        
        if 'tar' in archive:
            self.unpack(archive, tarfile.open, build_dir)
        elif 'zip' in archive:
            self.unpack(archive, zipfile.open, build_dir)
        else:
            raise Exception('unrecognized install source archive format: %s' % archive)

    def configure(self, args=''):
        target_dir = self.target_dir
        self.shell_command('./configure --prefix=%s %s' % (target_dir, args), 'configure') 
    
    def apply_patch(self, patch_name):
        patch = self.find_file(patch_name, self.patch_paths)
        self.shell_command('patch --verbose -p1 -i %s' % (patch), 'patch')
    
    def make(self):
        if self.target_arch == 'ppc450d' or self.target_arch == 'x86_64':
            self.shell_command('${CC} -compile-info')
        else:
            self.shell_command('${CC} -v')
        self.shell_command('make', 'make')
    
    def make_install(self):
        self.shell_command('make install', 'make')

    def python(self, command, argtuple):
        log = self.log
        log.info(command)
        command(argtuple)

    def shell_command(self, command, log_file=''):
        if log_file is not '':
            log = logging.getLogger('ksl.installer.package.%s' % log_file)
        else:
            log = self.log
        log.info(command)
        p = subprocess.Popen(command, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)

        while p.returncode is None:
            p.poll()
            out = p.stdout.readline()
            log.info(out)
            
        err_code = p.returncode
        if err_code:
            err_msg = "command %s failed, see log for details" % command
            log.error(err_msg)
            raise Exception(err_msg)

    def module(self, module_args):
        p = subprocess.Popen('%s python %s' % (self.module_cmd,module_args),
                             shell=True, stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
        (commands, ignore) = p.communicate()

        if p.returncode is not None and p.returncode % 256:
            err = "Error issuing module command %s\n" % (module_args)
            self.log.error(commands)
            raise BuildError("unexpected failure issuing module command: %s" % module_args)
        exec commands

    def find_file(self, filename, search_path):
        file_found = False
        paths = search_path.split(pathsep)
        for path in paths:
            if exists(join(path, filename)):
                file_found = True
                return abspath(join(path,filename))
        err_msg = 'unable to locate file: %s on search path: %s' % (filename, search_path)
        self.log.error(err_msg)
        raise Exception(err_msg)

    def unpack(self, archive, unpacker, build_dir):
        try:
            u = unpacker(archive)
            members = u.getmembers()

            tar_subpath = members[0]

            if not tar_subpath.isdir():
                (head, tail) = os.path.split(tar_subpath.name)
                while head:
                    (head,tail) = os.path.split(head)
                if not tail:
                    err_msg = 'archive does not extract into a subdirectory, aborting'
                    self.log.error(err_msg)
                    raise Exception(err_msg)
                subdir = tail
            else:
                subdir = tar_subpath.name
            
            for member in members:
                u.extract(member,build_dir)
            u.close()

            working_dir = join(abspath(build_dir),subdir)
            chdir(working_dir)
            self.log.info('changed directory to %s', working_dir)

        except Exception, err:
            self.log.error('error during unpack: %s', err)
            raise


# DSL-ify this class
load_modules = installer.load_modules
unpack_source = installer.unpack_source
configure = installer.configure
apply_patch = installer.apply_patch
make = installer.make
make_install = installer.make_install
shell_command = installer.shell_command
python = installer.python
