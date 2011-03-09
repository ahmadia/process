#!/usr/bin/env python3

import os, re, sys, select, subprocess, logging, time, string
import tempfile, shutil, inspect
import ksl.process

bgp_interactive_template = string.Template('''#!/usr/bin/env bash
#
# @ job_name            = ${job_name}
# @ job_type            = bluegene
# @ output              = ${job_out_name}
# @ error               = ${job_err_name}
# @ environment         = COPY_ALL; 
# @ wall_clock_limit    = ${wall_time},${wall_time}
# @ notification        = ${notification}
# @ bg_size             = ${partition_size}
# @ cluster_list        = bgp
# @ class               = ${ll_class}
# @ account_no          = ${account}

# @ queue

xterm
''')

bgp_template = string.Template('''#!/usr/bin/env bash
#
# @ job_name            = ${job_name}
# @ job_type            = bluegene
# @ output              = ${job_out_name}
# @ error               = ${job_err_name}
# @ environment         = COPY_ALL; 
# @ wall_clock_limit    = ${wall_time},${wall_time}
# @ notification        = ${notification}
# @ bg_size             = ${partition_size}
# @ cluster_list        = bgp
# @ class               = ${ll_class}
# @ account_no          = ${account}

# @ queue

export LD_LIBRARY_PATH=$${KSL_PPC450D_LD_LIBRARY_PATH}
export PYTHONPATH=$${KSL_PPC450D_PYTHONPATH}
/bgsys/drivers/ppcfloor/bin/mpirun -exp_env LD_LIBRARY_PATH -exp_env PYTHONPATH -env BG_MAPPING=${map} -np ${np} -mode ${mode} ${command}
${done_command}
''')

x86_template = string.Template('''#!/usr/bin/env bash
#
# @ job_name            = ${job_name}
# @ job_type            = parallel
# @ output              = ${job_out_name}
# @ error               = ${job_err_name}
# @ environment         = COPY_ALL; 
# @ wall_clock_limit    = ${wall_time},${wall_time}
# @ notification        = ${notification}
# @ node                = ${partition_size}
# @ tasks_per_node      = ${tasks_per_node}
# @ class               = ${ll_class}
# @ account_no          = ${account}

# @ queue

declare -x LD_LIBRARY_PATH=$$LD_LIBRARY_PATH:/opt/share/chem_tools/openmpi-1.4.1/lib
/opt/share/chem_tools/openmpi-1.4.1/bin/mpiexec -x LD_LIBRARY_PATH=$$LD_LIBRARY_PATH -np ${np} ${command}

${done_command}
''')


 
def main():
    # mode depends on if we are running on neser or shaheen
    host_arch = os.uname()[4]

    parser = build_parser(host_arch)
    config_tuple = get_file_config(host_arch)
    config_strings = ['--'+arg+'='+value for arg,value in config_tuple]
    file_options = parser.parse_args(config_strings)
    options = parser.parse_args(namespace=file_options)

    if options.version:
        print("kslrun: "+ksl.process.__version__)
        return

    if options.configure:
        configure(host_arch, options)
        return

    if options.debug:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s %(message)s')
    elif options.verbose:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING,
                            format='%(asctime)s %(levelname)s %(message)s')

    logger = logging.getLogger('kslrun')

    logger.debug("options")
    logger.debug(options)

    tempdir = tempfile.mkdtemp()

    if options.interactive or options.generate_only:
        options.no_std_redirect = True
    elif options.command is '':
        print("Missing command argument to mpirun, e.g. kslrun ./a.out")
        return
    try:
        llqid = None
        if not options.no_std_redirect:
            job_out_name = os.path.join(tempdir, "job_out")
            job_err_name = os.path.join(tempdir, "job_err")

            time.sleep(1) 
            job_done_name = os.path.join(tempdir, "job_done")
            done_command = 'touch ' + job_done_name
        else:
            job_out_name = options.prefix+'.out'
            job_err_name = options.prefix+'.err'
            done_command = ''
            
        logger.info("setting up LoadLeveler submission script")    

        ll_dict = dict(inspect.getmembers(options))
        ll_dict['command'] = ''.join(options.command)
        ll_dict['job_out_name'] = job_out_name
        ll_dict['job_err_name'] = job_err_name
        ll_dict['done_command'] = done_command

        if options.no_notify:
            ll_dict['notification'] = 'never'
        else:
            ll_dict['notification'] = 'always'

        llfilename = setup_ll_file(options, host_arch, ll_dict, tempdir)

        if options.generate_only:
            logger.info("Generate only -- returning")
            return
        
        logger.info("submitting to LoadLeveler")
        (llout, llerr) = call_command("llsubmit " + llfilename)
        logger.info('llout: ' + str(llout))
        logger.info('llerr: ' + str(llerr))


        if len(llout) == 0:
            llerr = llerr.decode('utf-8')
            logger.info("error from LoadLeveler")
            sys.stderr.write(llerr)
            if llerr.startswith('invalid account'):
                sys.stderr.write("********************************************************************************\n")
                sys.stderr.write("try configuring (kslrun -c) or setting a valid account with kslrun -a account_no\n")
                sys.stderr.write("********************************************************************************\n")
            return
        # silent ignore currently
        #        logger.error(llerr)
        
        longllqid = str(llout).split(' ')[1]

        if host_arch == 'ppc64':
            fen = 'fen1-a'
        else:
            fen = 'cn96'
        assert ('%s.shaheen.kaust.edu.sa' % fen) in longllqid, "Unable to determine llq job id from output, %s" % llout

        llqid = longllqid.replace("shaheen.kaust.edu.sa.","") + ".0"
        logger.info('identified job as ' + llqid)

        if not options.no_std_redirect:
            logger.info("watching for job_done file")
            watch_hangup(job_done_name, llqid)
            handle_output(job_out_name, job_err_name)
        else:
            logger.info("job submitted")
            print(llqid + " submitted to LoadLeveler")
    except:
        cleanup(llqid, options, logger, tempdir)
        raise
    cleanup(None, options, logger, tempdir)

def build_parser(host_arch):
    import argparse
    usage_str = "kslrun [optional arguments] command\nSee /opt/share/ksl/system/config/%s/kslrun.ini for default arguments\nkslrun %s" % (host_arch,ksl.process.__version__)
    parser = argparse.ArgumentParser(usage=usage_str)

    parser.add_argument('command', type=str, nargs='?', help='Command string to forward to mpirun', default='')

    ### Run Options
    og = parser.add_argument_group("General ")
    og.add_argument("--version", action="store_true", default=False,
                  help="print version string and exit")
    og.add_argument("-c", "--configure", action="store_true",
                    help="set up a configure file")

    og.add_argument("-v", "--verbose", action="store_true", 
                 help="print informational status messages to stdout")

    og.add_argument("-d", "--debug", action="store_true",
                 help="enable debug mode (developer use)")

    og.add_argument("-i", "--interactive", action="store_true",
                 help="request interactive xterm session from queue")

    og.add_argument("-r", "--no_std_redirect", action="store_true",
                 help="disable stdout/stderr redirection")

    og.add_argument("-g", "--generate_only", action="store_true",
                    help="only generate a LoadLeveler file, do nothing else")

    ### LoadLeveler Options
    og = parser.add_argument_group("LoadLeveler")
    og.add_argument('--no_notify', action="store_true",
                 help="do not send a notification email when job completes")

    og.add_argument("--prefix", type=str,
                 help='prefix for output files (only meaningful if no_std_redirect is enabled')
    og.add_argument("-j", "--job_name", type=str,
                 help="job_name as passed to LoadLeveler")

    og.add_argument('-t', "--wall_time", type=str,
                 help="job wall_time as passed to LoadLeveler")

    og.add_argument("--ll_class", type=str,
                 help="job class as passed to LoadLeveler")
      
    og.add_argument("-a", "--account", type=str,
                 help="account number to charge")

    og.add_argument("-p", "--partition_size", type=int, 
                  help="number of nodes to request")

    ### MPI Options
    og = parser.add_argument_group("MPI")
    og.add_argument("-n", "--np", type=int,
                 help="number of MPI processes to request")

    ### BGP-specific
    if host_arch == 'ppc64':
        og.add_argument("-m", "--mode", type=str,
                      help="MPI mode to use (e.g. VN, DUAL, SMP)")

        og.add_argument("--map", type=str, dest='map',
                      help="mapping of logical MPI processes to physical nodes/cores (e.g. XYZT, TXYZ, ...)")

    return parser

def get_config_files(host_arch):
    sys_file = '/opt/share/ksl/system/config/%s/kslrun.ini' % host_arch
    
    home_file = os.path.expanduser('~/.kslrun.ini')
    here_file = '.kslrun.ini'
    environ_file = ''
    if 'KSL_RUN_CONFIG' in os.environ:
        if os.path.isfile(os.environ['KSL_RUN_CONFIG']):
            environ_file = os.environ['KSL_RUN_CONFIG']
        else:
            raise Exception("KSL_RUN_CONFIG environment variable specified but does not point to a file")
    return (sys_file, home_file, here_file, environ_file)

def get_file_config(host_arch):
    # check /opt/share/ksl/system/config/$arch/kslrun.py, ~/.kslrun.py, ./.kslrun.py, and KSL_RUN_CONFIG
    import configparser
    config = configparser.ConfigParser()

    (sys_file, home_file, here_file, environ_file) = get_config_files(host_arch)

    with open(sys_file, 'r') as config_file:
        config.read_file(config_file)

    config.read([home_file, here_file, environ_file])

    return config.items('kslrun')

def configure(host_arch, options):
    (sys_file, home_file, here_file, environ_file) = get_config_files(host_arch)

    print("kslrun: configuring")

    found_files = [f for f in [sys_file, home_file, here_file, environ_file] if os.path.isfile(f)]
    print("kslrun found these configuration files: \n"+"\n".join(found_files))

    print("\n~/.kslrun.ini provides global configuration, ./kslrun.ini is directory-level")
    print("\nEnter g to configure ~/.kslrun.ini or l (default) to configure .kslrun.ini g/[l]")

    file_choice = getch()
    
    if file_choice == 'g' or file_choice == 'G':
        new_file = os.path.expanduser('~/.kslrun.ini')
    else:
        new_file = '.kslrun.ini'

    if os.path.isfile(new_file):
        print("Warning: %s already exists, are you sure you want to over-write? [y]/n?" % new_file)
        overwrite = getch()
        if overwrite == 'n' or overwrite == 'N':
            return

    config_keys = ['partition_size', 'account', 'job_name', 'wall_time', 'll_class', 'prefix', 'np', 'mode', 'map']

    config_options = {}

    for name in config_keys:
        old_value = getattr(options,name)
        print("\n%s: %s" % (name, old_value))
        new_value = input("Enter a new value or press return to continue")

        if len(new_value) > 0:
            config_options[name] = new_value
        else:
            config_options[name] = old_value


    print("kslrun: writing configuration file %s" % new_file)
    import configparser
    config = configparser.ConfigParser()
    config['kslrun'] = config_options
    with open(new_file, 'w') as configfile:
        config.write(configfile)

def cleanup(llqid, options, logger, tempdir):
    if options.debug:
        logger.debug("not deleting temporary working directory: " + tempdir)
    else:
        logger.info("deleting temporary files")
        shutil.rmtree(tempdir)
    if options.debug or options.generate_only:
        logger.debug("not deleting %s_submit.ll" % options.job_name)
    else:
        try:
            os.remove('%s_submit.ll' % options.job_name)
        except:
            pass
        
    if llqid is not None:
        if options.debug:
            logger.debug("not cancelling job: " + llqid)
        else:
            print("***\nattempting to cancel job: " + llqid + "\n***")
            (llout, llerr) = call_command("llcancel " + llqid)
            logger.info(llout)
            
def watch_hangup(job_done_name, llqid):
    logger = logging.getLogger('kslrun')
    while True:  # see return condition in hangup check        
        # now check for hangup
        if check_hangup(job_done_name):
            logger.info("Received a Hang-Up")
            # handle any output before returning, but give file system
            # a chance to clear named pipes  
            time.sleep(5)
            return

def handle_output(job_out_file_name, job_err_file_name):
    if os.path.isfile(job_out_file_name):
        with open(job_out_file_name,'r') as job_out_file:
            buf = job_out_file.read()
            sys.stdout.write(buf)
            sys.stdout.flush()
    if os.path.isfile(job_err_file_name):
        with open(job_err_file_name,'r') as job_err_file:
            buf = job_err_file.read()
            sys.stderr.write(buf)        
            sys.stderr.flush()
            
def setup_ll_file(options, host_arch, ll_dict, tempdir):
    logger = logging.getLogger('kslrun')
    logger.debug(ll_dict)
    if options.debug or options.generate_only:
        ll_filename = "./%s_submit.ll" % options.job_name
    else:
        ll_filename = os.path.join(tempdir, "%s_submit.ll" % options.job_name)

    ll_file = open(ll_filename, 'w')
    logger.info(ll_file)

    if host_arch == 'ppc64':
        if options.interactive:
            ll_file_contents = bgp_interactive_template.substitute(ll_dict)
        else:
            ll_file_contents = bgp_template.substitute(ll_dict)
    else:
        tpn = float(ll_dict['np']/ll_dict['partition_size'])
        assert tpn in range(1,9), 'Invalid # tasks per node, %d!' % tpn
        ll_dict['tasks_per_node'] = int(tpn)
        ll_file_contents = x86_template.substitute(ll_dict)
        

    ll_file.write(ll_file_contents)        
    logger.info(ll_file_contents)
    logger.info("written to %s_submit.ll" % options.job_name)
    ll_file.close()

    return ll_filename

def check_hangup(job_done_name):
    logger = logging.getLogger('kslrun')
    logger.debug("checking for hangup file " + job_done_name)
    return os.path.exists(job_done_name)

def call_command(command):
    process = subprocess.Popen(command.split(' '),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    return process.communicate()

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

if __name__ == "__main__":
    run()

def run():
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("""
================================================================================
||                           *Interrupted by user*                            ||
================================================================================
""")
        raise
    except:
        print("""
================================================================================
||           *There was some sort of error running the script*                ||
||       Please report to Aron Ahmadia <aron.ahmadia@kaust.edu.sa>            ||
================================================================================

Error stack follows
""")
        raise 

