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

    def install(self, options):
        self.log.info('beginning installation')

        self.add_system_install_steps()
        
        num_steps = len(self.install_steps)
        not_going = True
        
        for step_no, step in zip(range(1,num_steps+1),self.install_steps):
            self.log.info('on step %d, %s' % (step_no, step))

            if options.interactive and not_going:
                print "(s)kip, (d)o, (g)o, or (c)ancel?"
                cmd = getch()
                if cmd == 'c':
                    raise Exception('cancelled by user')
                if cmd == 's':
                    continue
                if cmd == 'g':
                    not_going = False
                try:
                    if callable(step):
                        step(self)
                    else:
                        step_fun = step[0]
                        step_fun(self,*step[1:])
                except Exception, err:
                    self.log.error('error on step %d, %s' % (step_no, step))
                    if options.errors_fatal:
                        raise
            else:
                if callable(step):
                    step(self)
                else:
                    step_fun = step[0]
                    step_fun(self,*step[1:])

        self.unbase()
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
            self.mod_paths    = ""
        else:
            self.mod_paths    = ":".join(add_root(p) for p in self.paths)

        self.paths_fake       = "\$(PATH):" + ":".join(add_root(p) for p in self.paths)
        
        self.includes_pretty  = ", ".join(add_root(p) for p in self.includes)
        if not self.includes:
            self.mod_includes = ""
        else:
            self.mod_includes = "-I"+" -I".join(add_root(p) for p in self.includes)
        self.libdirs_pretty   = ", ".join(add_root(p) for p in self.libdirs)
        self.libs_pretty      = ", ".join(l for l in self.libs)

        self.mod_libpaths  = ":".join(add_root(p) for p in self.libdirs)

        lib_strip = lambda l: splitext(l)[0].replace('lib','-l')
        if not self.libs:
            self.mod_libs     = ""
        else:
            self.mod_libs     = "".join(" %s" % (lib_strip(l)) for l in self.libs)
        if not self.libdirs:
            self.mod_ldflags  = ""
        else:
            self.mod_ldflags  = "-L"+" -L".join(add_root(p) for p in self.libdirs)
            
            
        self.modules_pretty   = " ".join(m for m in self.required_modules)
        if not self.required_modules:
            self.load_required_modules = ""
        else:
            self.load_required_modules = "module load " + " ".join(m for m in self.required_modules)
        if 'mod_magic' not in dir(self):
            self.mod_magic = ''

        # oh man is this dirty        
        module_data = template.substitute(dict(getmembers(self)))
        self.log.info("installing module file %s with contents:" % self.module_file)
        self.log.info(module_data)

        handle = open(self.module_file,'w')
        handle.write(module_data)
        handle.close()

    def add_system_install_steps(self):
        self.install_steps = list(self.install_steps)
        if self.install_steps[0] is not load_modules:
            self.install_steps.insert(0, load_modules)
        if self.install_steps[1] is not unpack_source:
            self.install_steps.insert(1, unpack_source)
        if self.install_steps[2] is not self.rebase:
            self.install_steps.insert(2, rebase)
        
    def unload_modules(self):
        self.log.info("clearing modules")
        self.module('purge')
        self.module('load init genie')

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
    
    def unpack_source(self, extract=True):
        archive_name = self.source
        build_dir = self.build_dir
        archive = self.find_file(archive_name, self.source_paths)

        if extract:
            self.log.info("unpacking source file %s into %s" % (archive, build_dir))
        else:
            self.log.info("acquiring working directory information from source file %s" % archive)
        
        if 'tar' in archive:
            self.working_dir = self.unpack(archive, tarfile.open, build_dir, extract)
        elif 'zip' in archive:
            self.working_dir = self.unpack(archive, zipfile.open, build_dir, extract)
        else:
            raise Exception('unrecognized install source archive format: %s' % archive)
        self.log.info("working directory set to %s" % self.working_dir)

    def unpack_overlay(self, archive_name):
        build_dir = self.build_dir
        archive = self.find_file(archive_name, self.overlay_paths)
        self.log.info("unpacking overlay from file %s into %s" % (archive, self.working_dir))
        
        if 'tar' in archive:
            self.unpack(archive, tarfile.open, self.working_dir)
        elif 'zip' in archive:
            self.unpack(archive, zipfile.open, self.working_dir)
        else:
            raise Exception('unrecognized overlay archive format: %s' % archive)

    def install_files(self, source, dest_subpath=''):
        target_dir = self.target_dir
        dest_path = os.path.join(target_dir, dest_subpath)
        self.shell_command('install -D %s %s' % (source, dest_path))

    def install_dir(self, dest_subpath):
        target_dir = self.target_dir
        dest_path = os.path.join(target_dir, dest_subpath)
        self.shell_command('install -d %s' % dest_path)

    def install_source(self):
        self.unpack_source()
        self.log.info("installing files from %s into %s" % (self.source, self.target_dir))
        self.shell_command('cp -R * %s' % (self.target_dir))

    def configure(self, args=''):
        target_dir = self.target_dir
        self.shell_command('./configure --prefix=%s %s' % (target_dir, args), 'configure') 
    
    def apply_patch(self, patch_name):
        patch = self.find_file(patch_name, self.patch_paths)
        self.shell_command('patch --verbose -p1 -i %s' % (patch), 'patch')
    
    def make(self, args=''):
        if self.target_arch == 'ppc450d' or self.target_arch == 'x86_64':
            self.shell_command('${CC} -compile-info')
        else:
            self.shell_command('${CC} -v')
        self.shell_command('make %s' % (args), 'make')
    
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
        
    def templated_shell_command(self, command_template, log_file=''):
        if log_file is not '':
            log = logging.getLogger('ksl.installer.package.%s' % log_file)
        else:
            log = self.log
        log.info('executing templated shell command')
        log.info(command_template.template)
        command = command_template.substitute(vars(self))
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

    def rebase(self):
        self.base_dir = os.getcwd()
        try:
            chdir(self.working_dir)
        except Exception, err:
            self.unpack_source(extract=False)
            chdir(self.working_dir)
        self.log.info('changed directory to %s', self.working_dir)

    def unbase(self):
        chdir(self.base_dir)
        self.log.info('changed directory to %s', self.base_dir)

    def module(self, module_args):
        p = subprocess.Popen('%s python %s' % (self.module_cmd,module_args),
                             shell=True, stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
        (commands, ignore) = p.communicate()

        err_msg = "Error issuing module command: %s\n%s" % (module_args, commands)
        if p.returncode is not None and p.returncode % 256:
            self.log.error(err_msg)
            raise Exception(err_msg)
        try:
            exec commands
        except Exception,err:
            self.log.error(err_msg)
            raise Exception(err_msg)
        
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

    def unpack(self, archive, unpacker, build_dir, extract=True):
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

            if extract:
                for member in members:
                    u.extract(member,build_dir)
                    
            u.close()
            return join(abspath(build_dir),subdir)
        
        except Exception, err:
            self.log.error('error during unpack: %s', err)
            raise

# DSL-ify this class
load_modules = installer.load_modules
unpack_source = installer.unpack_source
unpack_overlay = installer.unpack_overlay
configure = installer.configure
apply_patch = installer.apply_patch
make = installer.make
make_install = installer.make_install
install_files = installer.install_files
install_dir = installer.install_dir
install_source = installer.install_source
shell_command = installer.shell_command
templated_shell_command = installer.templated_shell_command
rebase = installer.rebase
python = installer.python

def getch():
    import sys, tty, termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

