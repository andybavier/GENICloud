#!/bin/bash

# Script to set up OpenStack head node
# Copied from https://fedoraproject.org/wiki/Getting_started_with_OpenStack_Nova
# Run this script as root
yum -y install openstack-nova mysql-server unzip polkit

openstack-nova-db-setup -y --rootpw ""

service rabbitmq-server start
chkconfig rabbitmq-server on

# Need to add user "nova" to sudoers file

# Libvirtd is already running on a PlanetLab node
# service libvirtd start
# chkconfig libvirtd on

# Need to fix this...
chmod 777 /var/run/libvirt/libvirt-sock

# Fix up /vservers directories
chmod 755 /vservers
mkdir /vservers/.glance
mkdir /vservers/.nova
mkdir /vservers/.nova/instances
chown -R nova:nova /vservers/.nova
chown -R glance:glance /vservers/.glance

# Use /vservers/.glance for Glance image storage
sed -i.orig -e 's/\/var\/lib\/glance/\/vservers\/.glance/g' /etc/glance/glance-api.conf
for svc in api registry
do 
    service openstack-glance-$svc start
    chkconfig openstack-glance-$svc on
done

# *** This is OK for a start, but eventually FIX ME ***
# The openstack-nova-volume service requires an LVM Volume Group called nova-volumes to exist.
# We simply create this using a loopback sparse disk image.
NOVA_VOLUME=/vservers/.nova/nova-volumes.img
dd if=/dev/zero of=$NOVA_VOLUME bs=1M seek=20k count=0
vgcreate nova-volumes $(losetup --show -f $NOVA_VOLUME)

# Setup Nova to use LXC
echo '--libvirt_type=lxc' | tee -a /etc/nova/nova.conf

# Put Nova-related state in /vservers/.nova
sed -i.orig -e 's/state_path=\/var\/lib\/nova/state_path=\/vservers\/.nova/' /etc/nova/nova.conf

for svc in api objectstore compute network volume scheduler
do 
    service openstack-nova-$svc start
    chkconfig openstack-nova-$svc on
done

### Set up accounts
nova-manage user admin novadmin

# Tell Nova to use CaveWave bridge cw0
# Need to customize the private network for each CaveWave-connected cluster so that
# each has its own subnet
nova-manage network create private 10.0.0.0/24 1 256 --bridge=cw0


