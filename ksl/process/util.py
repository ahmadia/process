def get_file_config(host_arch, script_name):
    # check /opt/share/ksl/system/config/$arch/$script_name.py, ~/.$script_name.py, ./.$script_name.py, and KSL_RUN/INSTALL_CONFIG
    import configparser
    config = configparser.ConfigParser()

    (sys_file, home_file, here_file, environ_file) = get_config_files(host_arch, script_name)

    try:
        with open(sys_file, 'r') as config_file:
            config.read_file(config_file)

            config.read([home_file, here_file, environ_file])
        script_config = config.items(script_name)
    except:
        print("***\nError: kslrun was unable to open system file %s\n***" % sys_file)
        raise
    return script_config

def get_config_files(host_arch, script_name):
    import os
    sys_file = '/opt/share/ksl/system/config/%s/%s.ini' % (host_arch, script_name)
    environ_var = 'KSL_' + script_name.upper().split('KSL')[1] + '_CONFIG'
    home_file = os.path.expanduser('~/.%s.ini' % script_name)
    here_file = '.%s.ini' % script_name
    environ_file = ''
    if environ_var in os.environ:
        if os.path.isfile(os.environ[environ_var]):
            environ_file = os.environ[environ_var]
        else:
            raise Exception("%s environment variable specified but does not point to a file" % environ_var)
    return (sys_file, home_file, here_file, environ_file)

def call_command(command, options):
    if options.dry_run:
        print(command)
        return
    else:
        proc = subprocess.Popen(command.split(' '),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        return proc.communicate()

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

def setup_logging(options):
    import logging
    if options.debug:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s %(message)s')
    elif options.verbose:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING,
                            format='%(asctime)s %(levelname)s %(message)s')

def run_script(script_main):
    try:
        script_main()
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

