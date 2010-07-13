import shutil
import subprocess
import sys

@with_setup(ignore_it, clean_it)
def test_compilers():
    test_list = [('ibm', 'mpixlc', 'hello.c', 'hello.exe', 'hello world')]
    for module, compiler, source, target, expected_output in test_list:
        yield check_build_and_verify(module, compiler, source, target, expected_output)

def check_build_and_verify(module, compiler, source, target, expected_output):
    build_command = "module load %s && %s -o $s $s && module unload %s" % (module, compiler, target, source, module)
    build_info = "target: %s compiled with: %s (module: %s) from source: %s" % (target, compiler, module, source)
    build_it(build_info, build_command)
    run_command = "kslrun -np 1 ./%s" % (target)
    verify_it(run_command)

def build_it(build_info, build_command):
    p = Popen(build_command, shell=True, stdout=subprocess.PIPE ,stderr=subprocess.STDOUT)
    (stdout_data, ignore) = p.communicate()
    rc = p.returncode()

    err = "Error building %s", % (build_info)
    
    if rc is not None and rc % 256:
        sys.stderr.write(err)
        sys.stderr.write(build_command)
        sys.stderr.write(stdout_data)
        raise BuildError(err)

def verify_it(run_command, build_info, expected_output):
    p = Popen(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (actual_output, stderr_data) = p.communicate()
    rc = p.returncode()
    if rc is not None and rc % 256:
        err = "Error executing %s", % build_info
        sys.stderr.write(err)
        sys.stderr.write(run_command)
        raise RunError(err)
    
    if actual_output is not expected_output:
        err = "Error verifying %s", % build_info
        sys.stderr.write("expected output: %s", expected_output)
        sys.stderr.write("actual output  : %s", actual_output) 
        raise VerifyError(err)
    return

def ignore_it():
    pass

def clean_it():
    shutil.rmtree('./build')

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
   import nose; nose.main()
