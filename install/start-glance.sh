#!/bin/bash

for svc in api registry
do
    service openstack-glance-$svc start
    sleep 1
    service openstack-glance-$svc status
done
