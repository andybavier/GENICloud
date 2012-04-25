#!/bin/bash

for svc in api objectstore compute network volume scheduler
do 
    service openstack-nova-$svc start
    sleep 1
    service openstack-nova-$svc status
done



