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

    url = "http://www.lnprof.org/command?action=pushlog&ns=genicloud&node=%s&path=%s" % (myNodeId, path)
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
    
    srcrange = mySiteInfo['node-srcrange']

    # Iterate over sliver data twice to make it deterministic
    for sliver in data['slivers']:
        if sliver['name'] == 'myplc_sfaam':
            writeSFAChain(f)

    for sliver in data['slivers']:
        if sliver['name'] == 'gc_eucacc':
            writeCloudControllerChain(f, srcrange, mySiteInfo['vm-network'])

    writeNodeChain(f, mySiteInfo['gc_eucacc'])
    writeVMChain(f, mySiteInfo['myplc_sfaam'])
    writeFooter(f)

    logger.log("gc_iptables: wrote temp file: %s" % tmpfile)
    f.close()

    if filecmp.cmp(tmpfile, IPTABLESCONF) == True:
        logger.log("gc_iptables: no changes to iptables configuration")
    else:
        logger.log("gc_iptables: configuration changed, committing")
        commit(tmpfile)
        pushLnprofEvent("Info/Iptables config updated")

    os.unlink(tmpfile)

def writeHeader(conf):
    conf.write("""*filter
:INPUT DROP
:FORWARD ACCEPT
:OUTPUT ACCEPT
:BLACKLIST -
:LOGDROP -
:EUCACC -
:EUCANODE -
:SFA -
:VM -

-A OUTPUT -j BLACKLIST
-A LOGDROP -j LOG
-A LOGDROP -j DROP
-A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT
-A INPUT -i lo -j ACCEPT

""")

def writeMiscRules(conf):
    conf.write("""
# Open ports for Hadoop and Ganglia
-A INPUT -p tcp -m state --state NEW -m tcp --dport 50000:55000 -j ACCEPT
-A INPUT -p tcp -m state --state NEW -m tcp --dport 8649 -j ACCEPT
-A INPUT -p udp --dport 8649 -j ACCEPT

""")

def writeSFAChain(conf):
    conf.write("""
# Open ports on hosts running SFA
-A SFA -p tcp -m state --state NEW -m tcp --dport 12345 -j ACCEPT
-A SFA -p tcp -m state --state NEW -m tcp --dport 12346 -j ACCEPT
-A SFA -p tcp -m state --state NEW -m tcp --dport 12347 -j ACCEPT

""")
    conf.write("# SFA access\n")
    for ip in globalinfo.sfa_access:
        conf.write("-A INPUT -s %s -j SFA\n" % ip)

def writeAdminChain(conf):
    conf.write("\n# Admin access is open to nodes and VMs\n")
    for address, name in globalinfo.admins:
        conf.write("# %s\n" % name)
        conf.write("-A INPUT -s %s -j ACCEPT\n" % address)
        conf.write("-A FORWARD -s %s -j ACCEPT\n" % address)

def writeCloudControllerChain(conf, srcrange, vmnet):
    conf.write("""
# Open ports for the Eucalyptus Cloud Controller (in slice gc_eucacc)
-A EUCACC -p tcp -m state --state NEW -m tcp --dport 8443 -j ACCEPT
-A EUCACC -p tcp -m state --state NEW -m tcp --dport 8773 -j ACCEPT
-A EUCACC -p tcp -m state --state NEW -m tcp --dport 8774 -j ACCEPT
-A EUCACC -p tcp -m state --state NEW -m tcp --dport 9001 -j ACCEPT
-A EUCACC -p tcp -m state --state NEW -m tcp --dport 80 -j ACCEPT

""")

    conf.write("# Connections from nodes to Cloud Controller\n")
    conf.write("-A INPUT -m iprange --src-range %s -j EUCACC\n" % srcrange)
    conf.write("# Connections from VMs to Cloud Controller\n")
    conf.write("-A INPUT -s %s -j EUCACC\n" % vmnet)

def writeNodeChain(conf, cchost):
    conf.write("""
# Open ports on Eucalyptus nodes
-A EUCANODE -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT
-A EUCANODE -p tcp -m state --state NEW -m tcp --dport 8775 -j ACCEPT

""")
    conf.write("# Connections from Cloud Controller to node\n")
    conf.write("-A INPUT -s %s -j EUCANODE\n" % cchost)

def writeVMChain(conf, sfahost):
    instances = getInstanceDB(sfahost)
    my_instances = getMyInstances()

    conf.write("\n# VM chain for limiting access to SSH\n")

    for name in my_instances:
        inst = instances[name]
        ips = slices.approved_ips[inst['slice']]
        for ip in ips:
            conf.write("-A VM -s %s -d %s -j ACCEPT\n" % (ip, inst['ip']))
    conf.write("-A VM -j REJECT --reject-with icmp-host-prohibited\n")
        
def writeFooter(conf):
    conf.write("""
# Limit access to SSH on VMs
-A FORWARD -p tcp -m state --state NEW -m tcp --dport 22 -j VM

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






