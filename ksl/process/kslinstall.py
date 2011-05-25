import os, sys, shutil, subprocess, logging, string
import ksl.process, logging.handlers
from ksl.process.install.installer import installer
from ksl.process.install.installer import getch
from datetime import datetime

def main():
    (options, args) = get_options()
    setup_installer_log(options)
    installer_variants = parse_install_file(options, args)
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

        except Exception:
            log = logging.getLogger('ksl.installer')
            log.error('error during install of variant %s: %s' % (variant.target_arch+variant.tag, err))
            close_logs(variant_logs)

            if options.errors_fatal:
                raise

def get_options():
    host_arch = os.uname()[4]
    usage_str = "kslinstall %s\nusage: kslinstall [options] install_file\nSee /opt/share/ksl/system/config/%s/kslinstall.py for default arguments" % (ksl.process.__version__,host_arch)

    o = optparse.OptionParser(usage=usage_str)
    c = cfgparse.ConfigParser(allow_py=True)

    og = optparse.OptionGroup(o, "GENERAL")
    og.add_option("--version",
                  action="store_true", default=False,
                  help="print version string and exit")

    og.add_option("-v", "--verbose",
                  action="store_true", 
                  help="print informational messages to stdout")
    c.add_option('verbose')

    og.add_option("-f", "--force",
                  action="store_true", 
                  help="clobber target directories and files")
    c.add_option('force')

    og.add_option("-k", "--keep_going",
                  action="store_false", dest="errors_fatal",
                  help="Do not abort if any variant builds fail")
    c.add_option('errors_fatal')
    
    og.add_option("-z", "--interactive",
                  action="store_true", dest="interactive",
                  help="Pause for confirmation on each job step")
    c.add_option('interactive')
    
    og.add_option('-n', "--no_install",
                 action="store_false", dest="do_install",
                 help="Skip build/install steps (install module files only)")
    c.add_option('do_install')
    
    og.add_option('-m', "--no_module",
                 action="store_false", dest="do_module", 
                 help="Skip installing modulefiles (build/install steps only)")                      
    c.add_option('do_module')

    og.add_option("-c", "--module_cmd",
                 action="store", dest="module_cmd",
                 help="module command")
    c.add_option('module_cmd')

    o.add_option_group(og)
    
    og = optparse.OptionGroup(o, "INPUT PATHS")

    og.add_option("--source_paths",
                      action="store", dest="source_paths",
                      help="source paths to search ")
    c.add_option('source_paths')

    og.add_option("--overlay_paths",
                      action="store", dest="overlay_paths",
                      help="overlay paths to search")
    c.add_option('overlay_paths')
    
    og.add_option("--patch_paths",
                      action="store", dest="patch_paths",
                      help="patch paths to search")
    c.add_option('patch_paths')

    og.add_option("-t", "--module_template",
                  action="store", dest="module_template",
                  help="template module file ")
    c.add_option('module_template')

    o.add_option_group(og)
    
    og = optparse.OptionGroup(o, "OUTPUT PATHS")

    og.add_option("-b", "--build_dir",
                  action="store", dest="build_dir", 
                  help="working directory for builds")
    c.add_option('build_dir')

    og.add_option("--root_install_dir",
                  action="store", dest="root_install_dir",
                  help="root directory to install packages to")
    c.add_option('root_install_dir')
        
    og.add_option("--root_module_dir",
                  action="store", dest="root_module_dir",
                  help="root module directory to install modulefiles to")
    c.add_option('root_module_dir')

    o.add_option_group(og)

    # check /opt/share/ksl/system/config/$arch/kslinstall.py, ~/.kslinstall.py, ./.kslinstall.py, and $KSL_INSTALL_CONFIG
    sysfile = '/opt/share/ksl/system/config/%s/kslinstall.py' % host_arch
    if os.path.isfile(sysfile):
        c.add_file(sysfile)
    homefile = os.path.expanduser('~/.kslinstall.py')
    if os.path.isfile(homefile):
        c.add_file(homefile)
    herefile = '.kslinstall.py'
    if os.path.isfile(herefile):
        c.add_file(herefile)
    if 'KSL_INSTALL_CONFIG' in os.environ:
        if os.path.isfile(os.environ['KSL_INSTALL_CONFIG']):
            c.add_file(os.environ['KSL_INSTALL_CONFIG'])
    
    (options, args) = c.parse(o)

    if options.version:
        print("kslinstall: "+ksl.process.__version__)
        sys.exit(0)

    if options.interactive:
        options.verbose = True

    if not args:
        raise Exception("It appears you forgot to specify an install file!")
    return (options, args)

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

def parse_install_file(options, args):
    log = logging.getLogger('ksl.installer')
    
    installfile = string.join(args)
    if not os.path.exists(installfile):
        raise Exception("couldn't locate install file: %s" % installfile)

    log.info("parsing install file %s" % installfile)

    execfile(installfile,globals())
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