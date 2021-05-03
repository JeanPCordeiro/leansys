#!/bin/bash
set -o xtrace

#
# Create LINSTOR Storage
#
SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
  
  linstor physical-storage create-device-pool --pool-name disk150G LVM vmi536198.contaboserver.net /dev/loop0
  linstor physical-storage create-device-pool --pool-name disk150G LVM vmi522170.contaboserver.net /dev/loop0
  linstor physical-storage create-device-pool --pool-name disk150G LVM vmi576145.contaboserver.net /dev/loop0

  linstor storage-pool create lvm vmi536198.contaboserver.net pool_ssd disk150G
  linstor storage-pool create lvm vmi522170.contaboserver.net pool_ssd disk150G
  linstor storage-pool create lvm vmi576145.contaboserver.net pool_ssd disk150G
  linstor sp l

  linstor resource-definition create nfs_data
  linstor volume-definition create nfs_data 140G
  linstor resource create nfs_data  --auto-place 3
  linstor volume list

fi

