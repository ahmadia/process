import shutil
import nose
import os
import subprocess
import sys
import string

saved_path = ''

def get_there():
    global saved_path
    saved_path =  os.getcwd()
    test_path = os.path.dirname(os.path.realpath(__file__))
    os.chdir(test_path)
    if not os.path.exists('./build'):
        os.mkdir('./build')
    module_cmd('load ppc64_host')
    module_cmd('load genie')

def clean_it():
    if os.path.exists('./build'):
        shutil.rmtree('./build')
    os.chdir(saved_path)

@nose.with_setup(get_there, clean_it)
def test_compilers():
    for module in ('ibm','gnu'):
        for test, np, expected_output in [('hello_world', 1, 'hello world'),
                                          ('hello_world_mpi', 128, '128.0: hello world')]:
            for ext, compiler in [('c', '${CC}'),
                                  ('cpp', '${CXX}'),
                                  ('f', '${FC}'),
                                  ('f90', '${F90}')]:
                source = test+'.'+ext
                target = test+'_'+ext+'.exe'
                yield check_build_and_verify, module, compiler, source, target, np, expected_output
                      
def check_build_and_verify(module, compiler, source, target, np, expected_output):
    # somebody smarter than me can figure out how to pull the module loads/unloads into fixtures
    module_cmd('load %s' % module)
    try:    
        build_command = "%s -o ./build/%s %s" % (compiler, target, source)
        build_info = "[target: %s, compiler: %s, (module: %s), source: %s]" % (target, compiler, module, source)
        build_it(build_info, build_command)
        run_command = "kslrun -n %d ./build/%s" % (np, target)
        verify_it(run_command, build_info, expected_output)
    finally:
        module_cmd("unload %s" % module)


def module_cmd(module_args):
    p = subprocess.Popen('/opt/share/ksl/tools/Modules/3.2.7/bin/modulecmd python %s' % module_args,
                         shell=True, stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
    (commands, ignore) = p.communicate()
    rc = p.returncode

    if rc is not None and rc % 256:
        err = "Error issuing module command %s\n" % (module_args)
        sys.stderr.write(commands)
        raise BuildError("unexpected failure issuing module command: %s" % module_args)

    exec(commands)

def build_it(build_info, build_command):

    p = subprocess.Popen(build_command, executable='/bin/bash',shell=True, stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
    (stdout_data, ignore) = p.communicate()
    rc = p.returncode
    
    if rc is not None and rc % 256:
        err = "Error building %s\n" % (build_info)
        sys.stderr.write(err)
        sys.stderr.write(build_command)
        sys.stderr.write(stdout_data)
        raise BuildError(err)
 
def verify_it(run_command, build_info, expected_output):
    p = subprocess.Popen(run_command, executable='/bin/bash', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (actual_output, stderr_data) = p.communicate()
    rc = p.returncode
    if rc is not None and rc % 256:
        err = "Error executing %s" % build_info
        sys.stderr.write(err)
        sys.stderr.write(run_command)
        raise RunError(err)

    actual_output = string.strip(actual_output)
    
    if actual_output != expected_output:
        err = "Error verifying %s\n" % build_info
        sys.stderr.write("expected output: %s\n" % expected_output)
        sys.stderr.write("actual output  : %s\n" % actual_output)
        sys.stderr.write("expected length: %d\n" % len(expected_output))
        sys.stderr.write("actual length  : %d\n" % len(actual_output))
        raise VerifyError(err)
    return

class Error(Exception):
    def __init__(self, expr):
        self.expr = expr
    def __str__(self):
        return repr(self.expr)

class BuildError(Exception):
    pass

class RunError(Exception):
    pass

class VerifyError(Exception):
    pass

if __name__=="__main__":
   nose.main()

