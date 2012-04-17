#!/bin/bash

if ifconfig cw0
then
    echo "*** Bridge cw0 exists ***"
else
    echo "Loading 8021q module ..."
    modprobe 8021q

    echo "Creating an interface on VLAN 3792 ..."
    vconfig add eth0 3792
    ifconfig eth0.3792 up

    echo "Adding bridge cw0 ..."
    brctl addbr cw0

    echo "Adding interface to cw0 ..."
    brctl addif cw0 eth0.3792
    ifconfig cw0 up
    
    lastOctet=`ifconfig eth0 | grep 'inet addr' | cut -d: -f2 | awk '{ print $1 }' | cut -d. -f4`
    ip=192.26.85.${lastOctet}
    echo "Assigning IP ${ip}"
    ifconfig cw0 ${ip} netmask 255.255.255.0
    echo "Sleeping 5 secs ..."
    sleep 5
fi
ping -c 5 192.26.85.160

