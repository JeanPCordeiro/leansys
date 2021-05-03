#!/bin/bash
set -o xtrace

#
# Create LINSTOR Cluster
#
SERVER=`hostname -s`
cp linstor-client.conf /etc/linstor/linstor-client.conf
if [ "$SERVER" = vmi536198  ]; then
  linstor node create vmi536198.contaboserver.net 161.97.170.117 --node-type Combined
  linstor node create vmi576145.contaboserver.net 178.18.248.191
  linstor node list
fi
