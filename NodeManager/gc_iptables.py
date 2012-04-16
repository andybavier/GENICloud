# $Id$
# $URL$

"""
"""

import logger
import os
import sys
import urllib
import subprocess
import tempfile
import filecmp
import shutil

sys.path.append("/etc/planetlab/genicloud")
import globalinfo
import slices

IPTABLESCONF = "/etc/sysconfig/iptables"
myNodeId = 0

def start():
    logger.log("gc_iptables: plugin starting up...")

def getLnprofNodeId(hostname):
    url = "http://www.lnprof.org/command?action=getnode&ns=genicloud&hostname=%s" % hostname
    (tmpfile, obj) = urllib.urlretrieve(url)
    f = open(tmpfile, 'r')
    nodeId = f.read().strip()
    f.close()
    return nodeId

def pushLnprofEvent(path):
    if not myNodeId:
        logger.log("ERROR: gc_iptables: Can't push event, no node id!")
        return

    url = "http://www.lnprof.org/command?action=pushlog&ns=genicloud&node=%s&log_path=%s" % (myNodeId, path)
    (tmpfile, obj) = urllib.urlretrieve(url)

def GetSlivers(data, config, plc = None):
    """
    """
    global myNodeId

    logger.log("gc_iptables:  Starting.")
    if not myNodeId:
        myNodeId = getLnprofNodeId(data['hostname'])
        logger.log("INFO: gc_iptables: got lnprof node id: %s" % myNodeId)

    try:
        node = plc.GetNodes(data['hostname'])[0]
        site = plc.GetSites(node['site_id'])[0]
    except:
        logger.log("ERROR: gc_iptables: could not lookup site")
        return
    # logger.log("gc_iptables: site is %s" % site['login_base'])

    refreshState()
    mySiteInfo = globalinfo.sites[site['login_base']]

    (fd, tmpfile) = tempfile.mkstemp(suffix='.iptables')
    f = os.fdopen(fd, 'w')
    
    writeHeader(f)
    writeMiscRules(f)
    writeAdminChain(f)
    
    writePortChain(f, data['slivers'])
    writeVMChain(f, data['slivers'])

    writeFooter(f)

    logger.log("gc_iptables: wrote temp file: %s" % tmpfile)
    f.close()

    if filecmp.cmp(tmpfile, IPTABLESCONF) == True:
        logger.log("gc_iptables: no changes to iptables configuration")
    else:
        logger.log("gc_iptables: configuration changed, committing")
        commit(tmpfile)
        pushLnprofEvent("Info/Iptables%20config%20updated")

    os.unlink(tmpfile)

def writeHeader(conf):
    conf.write("""*filter
:INPUT DROP
:FORWARD ACCEPT
:OUTPUT ACCEPT
:BLACKLIST -
:LOGDROP -
:VM -

-A OUTPUT -j BLACKLIST
-A LOGDROP -j LOG
-A LOGDROP -j DROP
-A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT
-A INPUT -i lo -j ACCEPT

""")

def writeMiscRules(conf):
    conf.write("""
# Miscellaneous rules
-A INPUT -d 198.55.32.85 -p tcp -m state --state NEW -m tcp --dport 80 -j ACCEPT
""")

def writeAdminChain(conf):
    conf.write("\n# Admin access is open to nodes and VMs\n")
    for address, name in globalinfo.admins:
        conf.write("# %s\n" % name)
        conf.write("-A INPUT -s %s -j ACCEPT\n" % address)

def writeVMChain(conf, slivers):
    conf.write("\n# VM chain for limiting access to SSH\n")

    for sliver in slivers:
        for attr in sliver['attributes']:
            # logger.log("%s: %s is %s" % (sliver['name'], attr['tagname'], attr['value']))
            if attr['tagname'] == 'fw_ssh_ips':
                ips = attr['value'].split()
                for ip in ips:
                    # Need to check for valid IP address or network here...
                    conf.write("-A VM -s %s -j ACCEPT\n" % ip)
    conf.write("-A VM -j REJECT --reject-with icmp-host-prohibited\n")
        
def writePortChain(conf, slivers):
    conf.write("\n# Open ports that have been requested by slices\n")

    for sliver in slivers:
        for attr in sliver['attributes']:
            if attr['tagname'] == 'fw_open_ports':
                conf.write("# For slice %s\n" % sliver['name'])
                ports = attr['value'].split()
                for port in ports:
                    try:
                        (protocol, num) = port.split('/')
                        logger.log("Open port for slice %s: %s %s" % (sliver['name'], protocol, num))
                        # Need to check that the port is valid.
                        # Also don't let people open some well-known ports like tcp/22, or all ports?
                        if protocol == "tcp":
                            conf.write("-A INPUT -p tcp -m state --state NEW -m tcp --dport %s -j ACCEPT\n" % num)
                        elif protocol == "udp":
                            conf.write("-A INPUT -p udp -m udp --dport %s -j ACCEPT\n" % num)
                        else:
                            logger.log("Unknown protocol for slice %s: %s" % (sliver['name'], protocol))
                    except:
                        logger.log("Invalid port argument for slice %s: %s" % (sliver['name'], port))


def writeFooter(conf):
    conf.write("""
# Limit access to SSH on VMs
-A INPUT -p tcp -m state --state NEW -m tcp --dport 22 -j VM

# respond to ping
-A INPUT -p icmp -m icmp --icmp-type 0 -j ACCEPT
-A INPUT -p icmp -m icmp --icmp-type 3 -j ACCEPT
-A INPUT -p icmp -m icmp --icmp-type 8 -j ACCEPT
-A INPUT -p icmp -m icmp --icmp-type 11 -j ACCEPT
-A INPUT -j REJECT --reject-with icmp-host-prohibited

COMMIT

*mangle
:PREROUTING ACCEPT
:INPUT ACCEPT
:FORWARD ACCEPT
:OUTPUT ACCEPT
:POSTROUTING ACCEPT
# -A POSTROUTING -o eth0 -j ULOG --ulog-cprange 54 --ulog-qthreshold 16
COMMIT
""")

def getInstanceDB(host):
    """
    Fetch the instances database from the local Aggregate Manager
    """
    mydict = {}
    url = "http://" + host + "/euca/instances.txt"
    (tmpfile, obj) = urllib.urlretrieve(url)
    f = open(tmpfile, 'r')
    for line in f:
        (inst, ip, slice) = line.strip().split()
        mydict[inst] = {'ip':ip, 'slice':slice}
    f.close()
    return mydict

def getMyInstances():
    """
    Use virsh to figure out what instances are running on the local machine
    """
    CMD = "virsh list"
    instances = []
    for line in subprocess.Popen(CMD, stdout=subprocess.PIPE, shell=True).stdout:
        fields = line.strip().split()
        if len(fields) > 1 and fields[1].startswith("i-"):
            instances.append(fields[1])
    return instances
    
def refreshState():
    reload(globalinfo)
    reload(slices)

def commit(tmpfile):
    shutil.copyfile(tmpfile, IPTABLESCONF)
    subprocess.call(["/sbin/service", "iptables", "restart"])






