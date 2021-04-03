#!/bin/bash
set -o xtrace

#
# Enable LINSTOR
#
SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
  systemctl enable --now  linstor-controller
else
systemctl enable --now  linstor-satellite
fi

#
# Create Virtual disk
#
fallocate -l 150G /disk150G.img
losetup -fP /disk150G.img
losetup -a

#
# Create LINSTOR Cluster
linstor node create vmi536198.contaboserver.net 161.97.170.117 --node-type Combined
linstor node create vmi522170.contaboserver.net 161.97.92.57
linstor node list

