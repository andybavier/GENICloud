#!/bin/bash

## Get some credentials and test things out                                                       
nova-manage project create --project=testgc --user=novadmin --desc="Test OpenStack setup"
nova-manage project zipfile --project=testgc --user=novadmin --file=./nova.zip
mkdir novacreds && cd novacreds; unzip ../nova.zip; . ./novarc
euca-add-keypair nova_key > nova_key.priv
chmod go-r nova_key.priv

euca-describe-availability-zones verbose

BUCKET=natty
BASE=natty-server-cloudimg-i386
TARBALL=$BASE.tar.gz
IMAGE=$BASE.img

mkdir images && cd images
wget http://uec-images.ubuntu.com/natty/current/$TARBALL
tar xzf $TARBALL
euca-bundle-image -i images/$IMAGE
euca-upload-bundle -b $BUCKET -m /tmp/$IMAGE.manifest.xml
euca-register $BUCKET/$IMAGE.manifest.xml
