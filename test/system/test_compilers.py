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

def clean_it():
    if os.path.exists('./build'):
        shutil.rmtree('./build')
    os.chdir(saved_path)

@nose.with_setup(get_there, clean_it)
def test_compilers():
    for module in ('ibm','gnu'):
        for test, expected_output in [('hello_world', 'hello world')]:
            for ext, compiler in [('c', '${CC}'),
                                  ('cpp', '${CXX}'),
                                  ('f', '${FC}'),
                                  ('f90', '${F90}')]:
                source = test+'.'+ext
                target = test+'_'+ext+'.exe'
                expected_output = 'hello world'
                yield check_build_and_verify, module, compiler, source, target, expected_output
                      
def check_build_and_verify(module, compiler, source, target, expected_output):
    build_command = "module load %s && %s -o ./build/%s %s" % (module, compiler, target, source)
    build_info = "[target: %s, compiler: %s, (module: %s), source: %s]" % (target, compiler, module, source)
    build_it(build_info, build_command)
    run_command = "kslrun -n 1 ./build/%s" % (target)
    verify_it(run_command, build_info, expected_output)
    unload_module(module)

def unload_module(module):
    rc = subprocess.call('module unload %s' % module, shell=True)
    if rc is not None and rc % 256:
        raise BuildError("unexpected failure unloading module")

def build_it(build_info, build_command):

    p = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
    (stdout_data, ignore) = p.communicate()
    rc = p.returncode

    err = "Error building %s\n" % (build_info)
    
    if rc is not None and rc % 256:
        sys.stderr.write(err)
        sys.stderr.write(build_command)
        sys.stderr.write(stdout_data)
        raise BuildError(err)
 
def verify_it(run_command, build_info, expected_output):
    p = subprocess.Popen(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

