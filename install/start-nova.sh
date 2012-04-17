#!/bin/bash

for svc in api objectstore compute network volume scheduler
do 
    service openstack-nova-$svc start
done



