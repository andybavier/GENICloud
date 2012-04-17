#!/bin/bash

# Script to set up OpenStack head node
# Copied from https://fedoraproject.org/wiki/Getting_started_with_OpenStack_Nova
# Run this script as root
yum -y install openstack-nova mysql-server unzip polkit expect

openstack-nova-db-setup -y --rootpw g3n1cl0ud

service rabbitmq-server start
chkconfig rabbitmq-server on

# Need to add user "nova" to sudoers file

# Libvirtd is already running on a PlanetLab node
# service libvirtd start
# chkconfig libvirtd on

# Need to fix this...
chmod 777 /var/run/libvirt/libvirt-sock

# Glance should use /vservers/.glance or something for image storage
# But may not be necessary since root fs is up to 70G
# sed -i.orig -e 's/\/var\/lib\/glance/\/vservers\/.glance/g' /etc/glance/glance-api.conf
for svc in api registry
do 
    service openstack-glance-$svc start
    chkconfig openstack-glance-$svc on
done

# *** This is OK for a start, but eventually FIX ME ***
# The openstack-nova-volume service requires an LVM Volume Group called nova-volumes to exist.
# We simply create this using a loopback sparse disk image.
mkdir /vservers/.nova
NOVA_VOLUME=/vservers/.nova/nova-volumes.img
dd if=/dev/zero of=$NOVA_VOLUME bs=1M seek=20k count=0
vgcreate nova-volumes $(losetup --show -f $NOVA_VOLUME)

# If you are testing OpenStack in a virtual machine, you need to configure nova to use 
# qemu without KVM and hardware virtualization:
# echo '--libvirt_type=qemu' | tee -a /etc/nova/nova.conf
#
# Setup for using LXC
echo '--libvirt_type=lxc' | tee -a /etc/nova/nova.conf

for svc in api objectstore compute network volume scheduler
do 
    service openstack-nova-$svc start
    chkconfig openstack-nova-$svc on
done

### Set up accounts
nova-manage user admin novadmin

# Should we use bridge cw0 (CaveWave) here?
nova-manage network create private 10.0.0.0/24 1 256 --bridge=br0


