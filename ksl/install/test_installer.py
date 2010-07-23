from installer import *
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='/opt/share/ksl/system/logs/ksl_installer.log',
                    filemode='a')
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)

fh = logging.FileHandler('/opt/share/ksl/system/logs/ksl_installer.log','a')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')

logging.getLogger('ksl.installer').addHandler(console)
logging.getLogger('ksl.installer').addHandler(fh)

