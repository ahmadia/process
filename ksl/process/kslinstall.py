import os, sys, shutil, subprocess, logging, string
import ksl.process, logging.handlers
import ksl.process.util as util
from ksl.process.install.installer import installer
from ksl.process.install.installer import getch

def main():
    host_arch = os.uname()[4]
    parser = build_parser(host_arch, 'kslinstall')
    config_tuple = util.get_file_config(host_arch, 'kslinstall')
    config_strings = ['--'+arg+'='+value for arg,value in config_tuple]
    file_options = parser.parse_args(config_strings)
    options = parser.parse_args(namespace=file_options)

    setup_installer_log(options)

    if options.version:
        print("kslinstall: "+ksl.process.__version__)
        sys.exit(0)

    if options.interactive:
        options.verbose = True

    if options.install_file is '':
        print ("It appears you forgot to specify an install file!")
        parser.print_usage()
        return
    
    installer_variants = parse_install_file(options)
    for variant in installer_variants:
        try:
            variant_logs = []
            if variant.build_host != os.uname()[4]:
                log = logging.getLogger('ksl.installer')
                log.info('skipping build %s because it requires build arch %s [host arch: %s]' %
                         (variant.target_arch+variant.tag, variant.build_host, os.uname()[4]))
                continue

            variant_logs = setup_package_logs(variant)
            setup_target_dir(variant, options)
            variant.virtual_install = False # assume real install by default
            if options.do_install:
                clobber_dir(variant, variant.target_dir, options)
                variant.install(options)
            if options.do_module:
                setup_module_dir(variant, options)
                variant.install_module()
            close_logs(variant_logs)

        except Exception as err:
            log = logging.getLogger('ksl.installer')
            log.error('error during install of variant %s: %s' % (variant.target_arch+variant.tag, err))
            close_logs(variant_logs)

            if options.errors_fatal:
                raise

def build_parser(host_arch, script_name):
    import argparse
    sys_file = util.get_sys_file(host_arch, script_name)
    usage_str = "kslinstall [options] install_file\nSee %s for default options" % (sys_file)
    parser = argparse.ArgumentParser(usage=usage_str)

    parser.add_argument('install_file', type=str, nargs='?', help='install_file specifying install', default='')

    og = parser.add_argument_group("General ")
    
    og.add_argument("--version",
                  action="store_true", default=False,
                  help="print version string and exit")

    og.add_argument("-v", "--verbose",
                  action="store_true", 
                  help="print informational messages to stdout")

    og.add_argument("--dry_run", action="store_true",
                    help="perform a dry run (don't actually execute commands)")
    
    og.add_argument("-f", "--force",
                    action="store_true", 
                    help="clobber target directories and files")
    
    og.add_argument("-k", "--keep_going",
                  action="store_false", dest="errors_fatal",
                  help="Do not abort if any variant builds fail")
    
    og.add_argument("-z", "--interactive",
                  action="store_true", dest="interactive",
                  help="Pause for confirmation on each job step")
    
    og.add_argument('-n', "--no_install",
                 action="store_false", dest="do_install",
                 help="Skip build/install steps (install module files only)")
    
    og.add_argument('-m', "--no_module",
                 action="store_false", dest="do_module", 
                 help="Skip installing modulefiles (build/install steps only)")                      

    og.add_argument("-c", "--module_cmd",
                 action="store", dest="module_cmd",
                 help="module command")

    og = parser.add_argument_group("Input Paths ")

    og.add_argument("--source_paths",
                      action="store", dest="source_paths", type=str,
                      help="source paths to search ")

    og.add_argument("--overlay_paths",
                      action="store", dest="overlay_paths", type=str,
                      help="overlay paths to search")
    
    og.add_argument("--patch_paths",
                      action="store", dest="patch_paths", type=str,
                      help="patch paths to search")

    og.add_argument("-t", "--module_template",
                  action="store", dest="module_template", type=str,
                  help="template module file ")

    og = parser.add_argument_group("Output Paths ")
    
    og.add_argument("-b", "--build_dir",
                  action="store", dest="build_dir", type=str,
                  help="working directory for builds")

    og.add_argument("--root_install_dir",
                  action="store", dest="root_install_dir", type=str,
                  help="root directory to install packages to")
        
    og.add_argument("--root_module_dir",
                  action="store", dest="root_module_dir", type=str,
                  help="root module directory to install modulefiles to")

    return parser

def setup_installer_log(options):

    if options.verbose:
        logging.basicConfig(level=logging.INFO,
                            format='%(message)s')
    else:
        logging.basicConfig(level=logging.WARNING,
                            format='%(message)s')
    
    # ten backup files at 100MB for a total of ~1GB potential logs 
    syslog = logging.handlers.RotatingFileHandler('/opt/share/ksl/system/logs/ksl_install.log',
                                                  mode='a',
                                                  maxBytes=104857600,
                                                  backupCount=10)
    syslog.setLevel(logging.DEBUG)
    syslogf = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s', '%m-%d %H:%M')
    syslog.setFormatter(syslogf)
    
    logging.getLogger('ksl.installer').addHandler(syslog)


def setup_target_dir(variant, options):
    variant.target_dir = os.path.join(
        variant.root_install_dir,variant.name,variant.version,variant.target_arch+variant.tag)

def setup_module_dir(variant, options):
    log = logging.getLogger('ksl.installer')

    variant_modules_dir = os.path.join(options.root_module_dir, variant.target_arch, variant.name)
    if not os.path.exists(variant_modules_dir):
        log.info("creating empty directory %s" % variant_modules_dir)
        os.makedirs(variant_modules_dir)

    module_name = variant.version+variant.tag
 
    if variant.tag == "":
        version_file = os.path.join(variant_modules_dir,'.version')
        if os.path.exists(version_file):
            if not options.force:
                print("Can I clobber module default version file %s? [y/n]: " % version_file)
                confirmation = getch()
                if confirmation != 'y':
                    raise Exception(
                        "unwilling to clobber version file %s" % version_file)
            log.info("deleting version file %s" % version_file)
            os.remove(version_file)

        log.info("setting default module version for %s on %s to %s " %
                 (variant.name, variant.target_arch, variant.version))
        file_handle = open(version_file, 'w')
        file_handle.write('#%%Module1.0\nset ModulesVersion "%s"\n' % variant.version)
        file_handle.close()
    else:
        log.info("installing non-default variant to module %s" % module_name)
        
    variant.module_file = os.path.join(variant_modules_dir, module_name)

def clobber_dir(variant, clobber_dir, options):
    log = logging.getLogger('ksl.installer')
        
    if os.path.exists(clobber_dir):
        if not options.force:
            print("Can I clobber directory %s? [y/n]: " % clobber_dir)
            confirmation = getch()
            if confirmation != 'y':
                raise Exception(
                    "unwilling to clobber directory %s" % clobber_dir)
        log.info("clobbering directory %s" %  clobber_dir)
        shutil.rmtree(clobber_dir)

    log.info("creating empty directory %s" % clobber_dir)
    os.makedirs(clobber_dir)

def setup_package_logs(variant):
    from datetime import datetime

    root = '/opt/share/ksl/system/logs/installs'
    prefix = variant.name+'-'+variant.version+'-'+variant.release+'-'+str(datetime.date(datetime.today()))+"-"+str(datetime.time(datetime.now()))+'_'+variant.target_arch+variant.tag

    logf = logging.Formatter('%(asctime)s %(name)s:\n%(message)s')

    logname = os.path.join(root,prefix+'_install.log')
    plog = logging.FileHandler(logname,'w')
    plog.setFormatter(logf)
    
    logging.getLogger('ksl.installer.package').addHandler(plog)

    configurelog = logging.FileHandler(os.path.join(root,prefix+'_configure.log'),'w')
    configurelog.setFormatter(logf)
    configurelog.propagate=False
    logging.getLogger('ksl.installer.package.configure').addHandler(configurelog)

    patchlog = logging.FileHandler(os.path.join(root,prefix+'_patch.log'),'w')
    patchlog.setFormatter(logf)
    patchlog.propagate=False
    logging.getLogger('ksl.installer.package.patch').addHandler(patchlog)

    makelog = logging.FileHandler(os.path.join(root,prefix+'_make.log'),'w')
    makelog.setFormatter(logf)
    makelog.propagate=False
    logging.getLogger('ksl.installer.package.make').addHandler(makelog)

    log = logging.getLogger('ksl.installer')
    log.info('logging install for build %s to %s' % (variant.target_arch+variant.tag, logname))

    return [(plog, 'ksl.installer.package'),
            (configurelog, 'ksl.installer.package.configure'),
            (patchlog, 'ksl.installer.package.patch'),
            (makelog, 'ksl.installer.package.make')]

def close_logs(logs):
    for handle, logname in logs:
        handle.flush()
        handle.close()
        logging.getLogger(logname).removeHandler(handle)
    return

def parse_install_file(options):
    log = logging.getLogger('ksl.installer')

    install_file = options.install_file
    if not os.path.exists(install_file):
        raise Exception("couldn't locate install file: %s" % install_file)

    log.info("parsing install file %s" % install_file)

    exec(compile(open(install_file).read(), install_file, 'exec'), globals())

    for variant in variants:
        variant.root_install_dir = options.root_install_dir
        variant.source_paths = options.source_paths
        variant.patch_paths = options.patch_paths
        variant.overlay_paths = options.overlay_paths
        variant_build_path = variant.name+'-'+variant.version+variant.tag
        variant.build_dir = os.path.join(options.build_dir,variant_build_path)
        variant.module_cmd = options.module_cmd
        variant.module_template = options.module_template
        
    return variants

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
