#!/bin/bash

for svc in api registry
do
    service openstack-glance-$svc start
done
