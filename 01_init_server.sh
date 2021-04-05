#!/bin/bash
set -o xtrace

#
# Enable LINSTOR
#
SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
  systemctl enable --now  linstor-controller
fi
systemctl enable --now  linstor-satellite

#
# Create Virtual disk
#
fallocate -l 150G /disk150G.img
losetup -fP /disk150G.img
losetup -a
#vgcreate vg_ssd /dev/loop0
#cp rc.local /etc/rc.local

#
# Create LINSTOR Cluster
#
if [ "$SERVER" = vmi536198  ]; then
  linstor node create vmi536198.contaboserver.net 161.97.170.117 --node-type Combined
  linstor node create vmi522170.contaboserver.net 161.97.92.57
  linstor node list
fi
cp linstor-client.conf /etc/linstor/linstor-client.conf

#
# Create LINSTOR Storage
#
if [ "$SERVER" = vmi536198  ]; then
  linstor physical-storage create-device-pool --pool-name disk150G LVM vmi536198.contaboserver.net /dev/loop0
  linstor physical-storage create-device-pool --pool-name disk150G LVM vmi522170.contaboserver.net /dev/loop0
  linstor storage-pool create lvm vmi536198.contaboserver.net pool_ssd disk150G
  linstor storage-pool create lvm vmi522170.contaboserver.net pool_ssd disk150G
  linstor sp l
fi

#
# Install LINSTOR Docker Plugin
#
docker plugin install linbit/linstor-docker-volume --alias linstor
cp docker-volume.conf /etc/linstor/docker-volume.conf

#
# Create test Volume
#
if [ "$SERVER" = vmi536198  ]; then
   docker volume create -d linstor --opt fs=xfs --opt size=2G testvol 
   docker run -it --rm --name=cont -v testvol:/data --volume-driver=linstor busybox ps aux
fi
