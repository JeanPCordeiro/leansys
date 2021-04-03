#!/bin/sh

"""true" &&
for x in python python3 python2; do
    /usr/bin/env "$x" -V > /dev/null 2>&1 && exec /usr/bin/env "$x" "$0" "$@"
done
>&2 echo "no python interpreter found :-("
exit 1
# """

# Actually, this is python.
# Even both python2 / python3 compatible.
# But on RHEL 8 (and other) platforms,
# we cannot write a generic shebang for python,
# because we don't know which one is installed :-(

import sys
import json
import platform
import collections
import subprocess
import os
import re
import base64
import tempfile
import time

try:
    from urlparse import urljoin
    from urllib2 import urlopen
    from urllib2 import Request
    from urllib2 import URLError
except ImportError:
    from urllib.parse import urljoin
    from urllib.request import urlopen
    from urllib.request import Request
    from urllib.error import URLError

MYLINBIT = "https://my.linbit.com/"
# MYLINBIT = "http://ruby-dev13:3001"

API_URL = urljoin(MYLINBIT, "api/v1/register_node")
LINBIT_PLUGIN_BASE = urljoin(MYLINBIT, "yum-plugin/")
MYNAME = "linbit-manage-node.py"
SELF = urljoin(MYLINBIT, MYNAME)
GPG_KEY = "https://packages.linbit.com/package-signing-pubkey.asc"
LINBIT_PLUGIN = urljoin(LINBIT_PLUGIN_BASE, "linbit.py")
LINBIT_PLUGIN_CONF = urljoin(LINBIT_PLUGIN_BASE, "linbit.conf")
NODE_REG_DATA = "/var/lib/drbd-support/registration.json"

REMOTEVERSION = 1
# VERSION has to be in the form "MAJOR.MINOR"
VERSION = "1.32"

api_retcodes = {
    "ok": 0,
    "need_node": -1,
    "need_contract": -2,
    "need_cluster": -3,
    "no_nodes_left": -4,
}

# script exit codes
E_SUCC = 0
E_FAIL = 1
E_NEED_PARAMS = 2
E_WRONG_CREDS = 3
E_NO_NODES = 4

RESTResponse = collections.namedtuple("RESTResponse",
                                      "retcode options proxy nodehash clusterid")


def get_input(s):
    # py2/3
    global input
    try:
        input = raw_input
    except NameError:
        pass

    return input(s)


class Distribution(object):
    def __init__(self):
        self._supported_dist_IDs = ('amzn', 'centos', 'rhel', 'debian',
                                    'ubuntu', 'xenenterprise', 'ol', 'sles')
        self._osrelease = {}

        self._update_osrelease()

        self._name = self._osrelease.get('ID')
        if self._name not in self._supported_dist_IDs:
            raise Exception("Could not determine distribution info")

        self._update_version()
        self._update_family()

    @property
    def osrelease(self):
        return self._osrelease

    def _update_osrelease(self):
        # gernates a slightly oppinionated osrelease dict that is similar to /etc/os-release
        # for very old distris it just sets the bare minimum to determine version and family
        osrelease = {}
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release') as o:
                for line in o:
                    line = line.strip()
                    if len(line) == 0 or line[0] == '#':
                        continue
                    k, v = line.split('=')

                    if v.startswith('"') or v.startswith("'"):
                        v = v[1:-1]  # assume they are at least symmetric

                    osrelease[k] = v
            if osrelease.get('ID', '') == 'ol':  # sorry, but you really are...
                osrelease['ID_LIKE'] = 'rhel'

        # centos 6, centos first, as centos has centos-release and redhat-release
        elif os.path.exists('/etc/centos-release'):
            osrelease['ID'] = 'centos'
            osrelease['ID_LIKE'] = 'rhel'
        # rhel 6
        elif os.path.exists('/etc/redhat-release'):
            osrelease['ID'] = 'rhel'

        self._osrelease = osrelease

    def _update_version(self):
        version = None

        if self._name == 'debian':
            try:
                v = self._osrelease['VERSION']
            except KeyError:
                raise Exception('No "VERSION" in your Debian /etc/os-release, are you running testing/sid?')

            m = re.search(r'^\d+ \((\w+)\)$', v)
            if not m:
                raise Exception('Could not determine version information for your Debian')
            version = m.group(1)
        elif self._name == 'ubuntu':
            version = self._osrelease['VERSION_CODENAME']
        elif self._name == 'centos':
            line = ''
            with open('/etc/centos-release') as cr:
                line = cr.readline().strip()
            # .* because the nice centos people changed their string between 6 and 7 (added 'Linux')
            # and even in the middle of 8 :-/. (removed the '(Final|Core)'
            m = re.search(r'^CentOS .* ([\d\.]+)', line)
            if not m:
                raise Exception('Could not determine version information for your Centos')
            version = m.group(1)
        elif self._name == 'amzn':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'rhel':
            try:
                version = self._osrelease['VERSION_ID']
            except KeyError:
                line = ''
                with open('/etc/redhat-release') as cr:
                    line = cr.readline().strip()
                m = re.search(r'^Red Hat Enterprise .* ([\d\.]+) \(.*\)$', line)
                if not m:
                    raise Exception('Could not determine version information for your RHEL6')
                version = m.group(1)
        elif self._name == 'xenenterprise':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'ol':
            version = self._osrelease['VERSION_ID']
        elif self._name == 'sles':
            version = self._osrelease['VERSION_ID']

        if version is None:
            raise Exception("Could not determine version information")
        self._version = version

    def _update_family(self):
        family = None

        families = ('rhel', 'sles', 'debian')
        if self._name in families:
            family = self._name
        elif 'ID_LIKE' in self._osrelease:
            for i in self._osrelease['ID_LIKE'].split():
                if i in ('rhel', 'sles', 'debian'):
                    family = i
                    break

        if family is None:
            raise Exception("Could not determine family for unknown distribution")
        self._family = family

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def family(self):
        return self._family


class LinbitDistribution(Distribution):
    def __init__(self):
        super(LinbitDistribution, self).__init__()

    @property
    def name(self):
        # use '{0}' instead of '{}', RHEL 6 does not handle the modern version
        if self._name in ('debian', 'ubuntu'):
            return '{0}-{1}'.format(self._name, self._version)
        elif self._name in ('rhel', 'centos', 'amzn'):
            d = self._name
            if self._name == 'centos':
                d = 'rhel'
            elif self._name == 'amzn':
                d = 'amazonlinux'

            v = self._version
            if '.' in v:
                v = v.split('.')
                v = v[0] + '.' + v[1]
            else:
                v += '.0'
            return '{0}{1}'.format(d, v)
        elif self._name in ('xenenterprise', 'ol'):
            d = self._name
            if self._name == 'xenenterprise':
                d = 'xenserver'
            v = self._version
            if '.' in v:
                v = v.split('.')[0]
            return '{0}{1}'.format(d, v)
        elif self._name == 'sles':
            v = self._version
            if '.' in v:
                v = v.split('.')
                v = v[0] + '-sp' + v[1]
            # else: TODO(rck): actually I don't know how non SPx looks like
            # in the repo it is just like "sles12"
            return '{0}{1}'.format(self._name, v)


# Utility Functions that might need update (e.g., if we add distro-types)
def getHostInfo():
    if platform.system() != "Linux":
        err(E_FAIL, "You have to run this script on a GNU/Linux based system")

    hostname = platform.node().strip().split('.')[0]

    # these defaults are weird, but that is what it was
    distname, distfamily = '', False
    try:
        lbd = LinbitDistribution()
        distname = lbd.name
        distfamily = lbd.family
    except Exception:
        pass  # benignly handled in "main"

    # it seems really hard to get MAC addresses if you want:
    # a python only solution, e.g., no extra C code
    # no extra non-built-in modules
    # support for legacy python versions
    macs = set()
    # we are Linux-only anyways...
    CLASSNET = "/sys/class/net"
    if os.path.isdir(CLASSNET):
        for dev in os.listdir(CLASSNET):
            devpath = os.path.join(CLASSNET, dev)

            if not os.path.islink(devpath):
                continue

            with open(os.path.join(devpath, "type")) as t:
                dev_type = t.readline().strip()
                if dev_type != '1':  # this filters for example ib/lo devs
                    continue

            # try to filter non permanent interfaces
            # very old kernels do not have /sys/class/net/*/addr_assign_type
            addr_assign_path = os.path.join(devpath, "addr_assign_type")
            if os.path.isfile(addr_assign_path):
                with open(addr_assign_path) as a:
                    dev_aatype = a.readline().strip()
                    if dev_aatype != '0' and dev_aatype != '3':  # NET_ADDR_PERM/dev_set_mac_address
                        continue
            else:  # try our best to manually filter them
                if dev.startswith("vir") or \
                   dev.startswith("vnet") or \
                   dev.startswith("bond"):
                    continue

            with open(os.path.join(devpath, "address")) as addr:
                mac = addr.readline().strip()
                macs.add(mac)

    return distname, distfamily, hostname, macs


def setupConfig(urlhandler, dist, family, config, free_running=False):
    # Write repository configuration
    if family == "debian":
        repo_file = "/etc/apt/sources.list.d/linbit.list"
    elif family == "rhel":
        repo_file = "/etc/yum.repos.d/linbit.repo"
    elif family == "sles":
        repo_file = "/etc/zypp/repos.d/linbit.repo"

    if not free_running:
        printcolour("Repository configuration:\n", GREEN)
        print("It is perfectly fine if you do not want to enable any repositories now.")
        print("The configuration for disabled repositories gets written,")
        print("but the repositories are disabled for now.")
        print("You can edit the configuration (e.g., {0}) file later to enable them.\n".format(repo_file))

    repo_content = []
    repo_names = []
    if family == "debian":
        for line in config:
            config_split = line.split()
            for name in config_split[3:]:
                repo_names.append(name)

        enabled = ask_enable(repo_names, free_running)
        for line in config:
            config_split = line.split()
            for name in config_split[3:]:
                line = " ".join(config_split[:3])
                line += " " + name
                if not enabled.get(name):
                    line = "# " + line
                repo_content.append(line + '\n\n')

    elif family == "rhel" or family == "sles":
        lines = []
        for line in config:
            lines.append(line.strip())
            repo_names.append(line.split('/')[-2])

        enabled = ask_enable(repo_names, free_running)
        for line in lines:
            name = line.split('/')[-2]
            repo_content.append("[{0}]\n".format(name))
            repo_content.append("name=LINBIT Packages for {0} - $basearch\n".format(name))
            repo_content.append("{0}\n".format(line))
            if family == "suse":
                repo_content.append("type=rpm-md\n")
            if enabled.get(name):
                repo_content.append("enabled=1\n")
            else:
                repo_content.append("enabled=0\n")
            repo_content.append("gpgkey={0}\n".format(GPG_KEY))
            repo_content.append("gpgcheck=1\n")
            repo_content.append("\n")

    printcolour("Writing repository config:\n", GREEN)
    if len(repo_content) == 0:
        if len(config) == 0:
            repo_content.append("# Could not find any repositories for your distribution\n")
            repo_content.append("# Please contact support@linbit.com\n")
        else:
            repo_content.append("# Repositories found, but none enabled\n")
    success = writeFile(repo_file, repo_content, free_running=free_running)
    if success:
        OK('Repository configuration written')

    # Download yum plugin on yum based systems
    if family == "rhel":
        plugin_dst = '/usr/share/yum-plugins'
        printcolour("Downloading LINBIT yum plugin\n", GREEN)
        FINAL_PLUGIN = LINBIT_PLUGIN
        if dist.startswith('rhel6'):
            FINAL_PLUGIN += '.6'
        elif dist.startswith('rhel7'):
            FINAL_PLUGIN += '.7'
        elif dist.startswith('rhel8'):
            FINAL_PLUGIN += '.8'
            plugin_dst = '/usr/lib/python3.6/site-packages/dnf-plugins'
        f = urlhandler.fileHandle(FINAL_PLUGIN)
        plugin = [pluginline for pluginline in f]
        writeFile(os.path.join(plugin_dst, 'linbit.py'), plugin,
                  showcontent=False, askforwrite=False, free_running=free_running)

        printcolour("Downloading LINBIT yum plugin config\n", GREEN)
        f = urlhandler.fileHandle(LINBIT_PLUGIN_CONF)
        cfg = [cfgline for cfgline in f]
        writeFile("/etc/yum/pluginconf.d/linbit.conf", cfg,
                  showcontent=False, askforwrite=False, free_running=free_running)

    return True


def main():
    py_major, py_minor = sys.version_info[:2]
    if py_major < 2 or (py_major == 2 and py_minor < 6):
        warn('Your Python version ({0}.{1}) is too old, manually add your nodes via https://my.linbit.com'.format(py_major, py_minor))
        warn('If you need further help, contact us:\n')
        contactInfo('', is_issue=False)
        sys.exit(1)
    free_running = False
    proxy_only = False
    non_interactive = False
    exclude_info_only = False

    args = {}
    args["version"] = REMOTEVERSION
    # urlhandler = requestsHandler()
    urlhandler = UrllibHandler()

    if os.path.isfile(NODE_REG_DATA):
        with open(NODE_REG_DATA) as infile:
            jsondata = json.load(infile)
            args["nodehash"] = jsondata["nodehash"]

    opts = sys.argv[1:]
    for opt in opts:
        if opt == "-p":
            proxy_only = True
            sys.argv.remove("-p")
            if not args.get("nodehash"):
                err(E_FAIL, 'Your node is not registered, first run this script without "-p".'
                    "\nMake sure {0} exists!".format(NODE_REG_DATA))
            args["proxy_only"] = True
        elif opt == "exclude-info":
            exclude_info_only = True

    e_user = os.getenv('LB_USERNAME', None)
    e_pwd = os.getenv('LB_PASSWORD', None)
    e_cluster = os.getenv('LB_CLUSTER_ID', None)
    e_contract = os.getenv('LB_CONTRACT_ID', None)
    e_no_version_check = os.getenv('LB_NO_VERSION_CHECK', None)

    e_all = e_user and e_pwd and e_cluster
    e_one = e_user or e_pwd or e_cluster or e_contract

    if e_one and not e_all:
        err(E_NEED_PARAMS, 'You have to set all (or none) of the required environment variables (LB_USERNAME, LB_PASSWORD, and LB_CLUSTER_ID)')
    if e_all and proxy_only:
        err(E_FAIL, 'You are not allowed to mix "-p" and non-interactive mode')

    non_interactive = e_all
    free_running = proxy_only or non_interactive

    if proxy_only:
        token = "N:" + args["nodehash"]
        headers = createHeaders(token)
    elif not exclude_info_only:
        force_user_input = False
        print("{0} (Version: {1})".format(MYNAME, VERSION))
        if not e_no_version_check:
            checkVersion(urlhandler)

        while True:
            if non_interactive:
                token = '{0}:{1}'.format(e_user, e_pwd)
            else:
                token = getToken(force_user_input)

            username = token.split(':')[0]
            token = "C:" + token

            headers = createHeaders(token, username)

            # create a first request to test UN/PWD
            if not free_running:
                print("Connecting to {0}".format(MYLINBIT))
            ret = urlhandler.postRESTRequest(headers, args)
            if ret.retcode == "failed":
                msg = "Username and/or Credential are wrong"
                if non_interactive:
                    err(E_WRONG_CREDS, msg)
                else:
                    warn(msg)
                force_user_input = True
            else:
                OK("Login successful")
                break

    dist, family, hostname, macs = getHostInfo()
    if exclude_info_only:
        print_exclude_info(family, dist)
        sys.exit(0)

    if len(macs) == 0:
        err(E_FAIL, "Could not detect MAC addresses of your node")

    if not dist and not free_running:
        print("Distribution information could not be retrieved")
        contactInfo(executeCommand("uname -a"))
        print("You can still register your node, but the script will not")
        print("write a repository configuration for this node")
        cont_or_exit()
        dist = "Unknown"

    if not isRoot():
        if free_running:
            err(E_FAIL, "You have to execute this script as super user")
        print("You are not running this script as super user")
        print("")
        print("There are two choices:")
        print("-) Abort now and restart the script (please use su/sudo)")
        print("-) Continue:")
        print("  - Registration itself does not require super user permissions")
        print("  - BUT the repository configuration will only be printed")
        print("    and written to /tmp")
        print("")
        cont_or_exit()

    # XXX
    # fake redhat
    # dist = "rhel7.2"
    # family = "rhel"
    #
    # fake suse
    # dist = "sles11-sp3"
    # family = "sles"
    #
    # fake debian
    # dist = "debian-wheezy"
    # family = "debian"
    # XXX

    args["hostname"] = hostname
    args["distribution"] = dist
    args["mac_addresses"] = ','.join(macs)
    if non_interactive:
        args["contract_id"] = e_contract
        args["cluster_id"] = e_cluster

    ret = urlhandler.postRESTRequest(headers, args)
    postsfailed = 0
    while ret.retcode != api_retcodes["ok"]:
        if ret.retcode == "failed":
            postsfailed += 1
            if postsfailed >= 3:
                err(E_FAIL, "Could not post request, giving up")

        if ret.retcode == api_retcodes["need_contract"]:
            if non_interactive:
                err(E_FAIL, 'Not a valid CONTRACT_ID')
            if len(ret.options) == 0:
                err(E_FAIL, "Sorry, but you do not have any valid contract for this credential")

            print("The following contracts are available:")
            selection = getOptions(ret.options, what="contract")
            args["contract_id"] = selection
        elif ret.retcode == api_retcodes["need_cluster"]:
            if non_interactive:
                err(E_FAIL, 'Not a valid CLUSTER_ID')
            selection = getOptions(ret.options, allow_new=True, what="cluster")
            args["cluster_id"] = selection
        elif ret.retcode == api_retcodes["need_node"]:
            warn("The script could not determinde all required information")
            contactInfo(args)
            sys.exit(1)
        elif ret.retcode == api_retcodes["no_nodes_left"]:
            err(E_NO_NODES, "Sorry, but you do not have any nodes left for this contract")

        # print("D*E*B*U*G, press enter")
        # get_input()
        ret = urlhandler.postRESTRequest(headers, args)

    if ret.retcode == api_retcodes["ok"]:
        if not free_running:
            printcolour("Writing registration data:\n", GREEN)
        args_save = {}
        args_save["nodehash"] = ret.nodehash
        args_save['cluster_id'] = ret.clusterid
        for tosave in ["distribution", "hostname", "mac_addresses"]:
            args_save[tosave] = args[tosave]
        writeFile(NODE_REG_DATA, args_save, showcontent=False,
                  free_running=free_running, asjson=True)
        if dist != "Unknown" and family:
            if ret.proxy:
                if not free_running:
                    printcolour("Writing proxy license:\n", GREEN)
                license = [x + '\n' for x in base64.b64decode(ret.proxy).decode('utf-8').split('\n')]
                writeFile("/etc/drbd-proxy.license", license,
                          showcontent=False, free_running=free_running)

            if not free_running or non_interactive:
                setupConfig(urlhandler, dist, family, config=ret.options, free_running=non_interactive)

            add_GPG_key(GPG_KEY, family, urlhandler, free_running)

            if not free_running:  # RCK THINK
                epilogue(family, dist, urlhandler)
    else:
        err(E_FAIL, sys.argv[0] + " exited abnormally")

    if not free_running:
        OK("Congratulations! Your node was successfully configured.")
    sys.exit(0)


# Utility functions that are unlikely to require change
def checkVersion(urlhandler):
    import re
    printcolour("Checking if version is up to date\n", GREEN)
    outdated = False

    # we do not want to fail if anything is wrong here...
    try:
        f = urlhandler.fileHandle(SELF)
        selfpy = [selfline for selfline in f]
        p = re.compile(r'^VERSION.*(\d+)\.(\d+).*')

        upstream_major = sys.maxsize
        upstream_minor = 0

        for line in selfpy:
            m = p.match(line.decode('utf-8').strip())
            if m:
                upstream_major = int(m.group(1))
                upstream_minor = int(m.group(2))
                break

        v = VERSION.split('.')
        my_major = int(v[0])
        my_minor = int(v[1])

        if my_major < upstream_major:
            outdated = True
        elif my_major == upstream_major and my_minor < upstream_minor:
            outdated = True

        if outdated:
            warn("Your version is outdated")
            tmpf = tempfile.mkstemp(suffix='_' + MYNAME)[1]
            writeFile(tmpf, selfpy, showcontent=False, askforwrite=False,
                      hinttocopy=False)
            OK("New version downloaded to {0}".format(tmpf))
        else:
            OK("Your version is up to date")
    except Exception:
        warn("Version check failed, but continuing anyways")

    if outdated:
        sys.exit(0)


def _executeCommand(command):
    pyvers = sys.version_info
    if pyvers[0] == 2 and pyvers[1] == 6:
        output = subprocess.Popen(command, shell=True,
                                  stdout=subprocess.PIPE).communicate()[0]
    else:
        output = subprocess.check_output(command, shell=True)
        output = output.decode('utf-8')
    return output


# only used for commands that should never fail (e.g., uname -a), still there was a case where "lsb_release"
# was not installed on the target system.
def executeCommand(command):
    try:
        return _executeCommand(command)
    except Exception:
        err(E_FAIL, 'Is the according tool installed to execute "{0}"?'.format(command))


# content is a list of of lines
def writeFile(name, content, showcontent=True, askforwrite=True,
              free_running=False, asjson=False, hinttocopy=True):
    origname = name
    if not isRoot():
        name = os.path.join("/tmp", os.path.basename(name))

    if showcontent and not free_running:
        print("Content:")
        for line in content:
            sys.stdout.write(line)
        print("")

    if askforwrite and not free_running:
        if askYesNo("Write to file ({0})?".format(name)):
            if os.path.isfile(name):
                print("File: {0} exists".format(name))
                if not askYesNo("Overwrite file?"):
                    return False
        else:
            return False

    dirname = os.path.dirname(name)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(name, "w") as outfile:
        if asjson:
            json.dump(content, outfile)
        else:
            for line in content:
                try:
                    # py 3, when it is bytes
                    line = line.decode('utf-8')
                except Exception:
                    pass
                outfile.write(line)

    if not isRoot() and hinttocopy:
        printcolour("Important: ", MAGENTA)
        print()
        print("Please review {0} and copy file to {1}".format(name, origname))

    return True


def getToken(force_user_input):
    if len(sys.argv) == 1 or force_user_input:
        import getpass
        while True:
            username = get_input("Username: ")
            if username:
                break

        while True:
            pwd = getpass.getpass("Credential (will not be echoed): ")
            if pwd:
                break
        return "{0}:{1}".format(username.strip(), pwd.strip())
    elif len(sys.argv) == 2:
        return sys.argv[-1]


def err(e, string):
    printcolour("ERR: ", RED)
    print(string)
    sys.exit(e)


def warn(string):
    printcolour("W: ", MAGENTA)
    print(string)


def contactInfo(args, is_issue=True):
    if is_issue:
        print("Please report this issue to:")
    print("\tdrbd-support@linbit.com")
    print("")
    print("Make sure to include the following infomation:")
    print("{0} - Version: {1}".format(os.path.basename(sys.argv[0]), VERSION))

    for fname in ('/etc/os-release', '/etc/centos-release', '/etc/redhat-release'):
        if not os.path.exists(fname):
            continue

        print('--- ' + fname + ' ' + '-' * (61-len(fname)))
        try:
            with open(fname) as o:
                MAX_READ = 1024
                c = o.read(MAX_READ)
                if o.read(1) != '':  # not done
                    print(c)  # at least print what we got
                    raise Exception('Did not reach EOF with a read of {0}'.format(MAX_READ))
                if c[-1] == '\n':  # pretty print without needing print(end=)
                    c = c[:-1]
                print(c)
        except Exception as e:
            print('Could not successfully read all of {0}:\n{1}\nPlease attach file'.format(fname, e))
        print('-' * 66)

    print(args)


def askYesNo(question):
    printcolour("--> ", CYAN)
    ret = get_input(question + " [y/N] ")
    ret = ret.strip().lower()
    if ret == 'y' or ret == "yes":
        return True
    else:
        return False


def cont_or_exit():
    if not askYesNo("Continue?"):
        sys.exit(0)


def createHeaders(token, username=None):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Token token=' + token.strip()
    }
    agent = "ManageNode/{0}".format(VERSION)
    if username:
        agent += " (U:{0})".format(username)
    headers['User-agent'] = agent

    return headers


def isRoot():
    return os.getuid() == 0


def getOptions(options, allow_new=False, what="contract"):
    # dicts have no guaranteed order, so we use an array to keep track of the
    # keys
    lst = []
    new = 0
    e = -1  # set it in case len(options) == 0

    print("Will this node form a cluster with...\n")
    for e, k in enumerate(sorted(options)):
        lst.append(k)
        if what == "contract":
            print("{0}) Contract: {1} (ID: {2})".format(e + 1, options[k], k))
        elif what == "cluster":
            print("{0}) Nodes: {1} (Cluster-ID: {2})".format(e + 1, options[k], k))
        else:
            err(E_FAIL, "Unknown selection option")

    if allow_new:
        printcolour("{0}) *Be first node of a new cluster*\n".format(e + 2), CYAN)
        new = 1
    print("")

    while True:
        printcolour("--> ", CYAN)
        nr = get_input("Please enter a number in range and press return: ")
        try:
            nr = int(nr.strip()) - 1  # we are back to CS/array notion
            if nr >= 0 and nr < len(options) + new:
                if allow_new and nr == e + 1:
                    return -1
                else:
                    return lst[nr]
        except ValueError:
            pass


def print_exclude_info(family, dist):
    # Print excludes information for RHEL/CENTOS users.
    if family != "rhel":
        return

    repos = ["base", "updates", "el repo (if enabled)"]
    excludes = [
        "cluster*",
        "corosync*",
        "drbd",
        "kmod-drbd",
        "libqb*",
        "pacemaker*",
        "resource-agents*",
    ]
    cent6_pluginconf_steps = ""
    if dist.startswith("rhel7"):
        repos.extend(
            ["rhel-ha-for-rhel-7-server-rpms (RHEL only)",
             "rhel-rs-for-rhel-7-server-rpms (RHEL only)"]
            )
    if dist.startswith("rhel6"):
        cent6_pluginconf_steps = (
            "and if you are using RHEL, rhel-x86_64-server-6 under "
            "/etc/yum/pluginconf.d/rhnplugin.conf")

    print("Please add the following line to your")
    print(", ".join(repos))
    print("repositories under /etc/yum.repos.d/")

    if cent6_pluginconf_steps:
        print(cent6_pluginconf_steps)

    print("to ensure you are using LINBIT's packages:")

    print("\nexclude=" + " ".join(excludes) + "\n")


# has to work on ancient python, so no shutil.which()
def which(cmd):
    return any(os.access(os.path.join(path, cmd), os.X_OK) for path in os.environ["PATH"].split(os.pathsep))


def print_yum_dnf_info(family, dist):
    if family != "rhel" or not dist.startswith("rhel7"):
        return

    if which('dnf'):
        printcolour("Please make sure to use 'yum', and *not* 'dnf' on RHEL7-alikes\n", YELLOW)


def add_GPG_key(gpg_key, family, urlhandler, free_running=False):
    if (isRoot() and
       (free_running or askYesNo("Add linbit signing key to keyring now?"))):
        addkey = False
        if family == "rhel" or family == "sles":
            addkey = "rpm --import {0}"
        elif family == "debian":
            addkey = "apt-key add {0}"

        if addkey:
            tmpf = tempfile.mkstemp()[1]
            addkey = addkey.format(tmpf)
            f = urlhandler.fileHandle(gpg_key)
            key = [keyline for keyline in f]
            writeFile(tmpf, key,
                      showcontent=False, askforwrite=False, hinttocopy=False)
            output = executeCommand(addkey)
            if (not free_running) and (output != ""):
                print(output)
    else:
        if not free_running:
            print("Download package signing key from {0} and import it manually!".format(gpg_key))


def epilogue(family, dist, urlhandler):
    printcolour("Final Notes:", GREEN)
    print("")

    print_exclude_info(family, dist)
    print_yum_dnf_info(family, dist)

    print("Now update your package information and install")
    print("LINBIT's kernel module and/or user space utilities")


class UrllibHandler(object):
    def __init__(self):
        pass

    def postRESTRequest(self, headers, payload):
        r = Request(API_URL, data=json.dumps(payload).encode('utf-8'), headers=headers)
        try:
            f = urlopen(r)
        except URLError as e:
            if str(e) == "HTTP Error 403: Forbidden":
                return RESTResponse("failed", False, False, False, False)
            else:
                err(E_FAIL, "urllib returned: " + str(e))

        ret = f.read()
        ret = json.loads(ret)

        return RESTResponse(retcode=int(ret["ret"]), options=ret["options"],
                            proxy=ret["proxy_license_file"], clusterid=ret.get('clusterid', '-1'),
                            nodehash=ret["nodehash"])

    def fileHandle(self, url):
        return urlopen(url)


# following from Python cookbook, #475186
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = list(range(8))


def has_colours(stream):
    if not hasattr(stream, "isatty"):
        return False
    if not stream.isatty():
        return False  # auto color only on TTYs
    try:
        import curses
        curses.setupterm()
        return curses.tigetnum("colors") > 2
    except Exception:
        # guess false in case of error
        return False


def printcolour(text, colour=WHITE):
    if has_colours:
        seq = "\x1b[1;{0}m{1}\x1b[0m".format(30+colour, text)
        sys.stdout.write(seq)
    else:
        sys.stdout.write(text)


def OK(text):
    sys.stdout.write('[')
    printcolour("OK", GREEN)
    sys.stdout.write('] ')
    print(text)


def ask_enable(names, free_running=False):
    """Asks the user which repos they wish to enable.

    Args:
        names: A list of repo names to be enabled/disabled.
        free_running: A blooean indicating if there will be no user input.
    Returns:
        An array of dicts, keys are repo names, values are True if repo is
            enabled.
    """

    enabled_by_default = False

    if free_running:
        enabled_by_default = True

    repos = []
    # Sort reverse to try to show newest versions first.
    for name in sorted(names, reverse=True):
        repos.append([name, enabled_by_default])

    # Skip asking questions in non-interacting mode.
    while not free_running:
        idx_offset = 1  # For converting between zero and one indexed arrays.
        os.system("clear")
        print("\n  Here are the repositories you can enable:\n")
        for index, repo in enumerate(repos):

            name, value = repo

            status = "Disabled"
            display_color = RED

            if value:
                status = "Enabled"
                display_color = GREEN

            printcolour(
                "    {0}) {1}({2})\n".format(index + idx_offset, name, status),
                display_color
            )

        print("\n  Enter the number of the repository you "
              "wish to enable/disable. Hit 0 when you are done.\n")
        choice = get_input("  Enable/Disable: ")

        # Ignore random button mashing.
        if not choice:
            continue

        try:
            choice = int(choice.strip())
        except ValueError:
            print("\n  You must enter a number!\n")
            time.sleep(1)
            continue

        if choice == 0:
            break

        choice_idx = choice - idx_offset
        try:
            # Toggle Enabled/Disabled
            repos[choice_idx][1] = not repos[choice_idx][1]
        except IndexError:
            # User will see if state of the repos change,
            # No need to complain.
            pass

    repo_map = {}
    for repo in repos:
        name, enabled = repo
        repo_map[name] = enabled

    return repo_map


if __name__ == "__main__":
    has_colours = has_colours(sys.stdout)
    try:
        main()
    except KeyboardInterrupt:
        print("")
        warn("Received Keyboard Interrupt signal, exiting...")
    except EOFError:
        print("")
        warn("Reached EOF waiting for input, exiting...")
