#!/bin/bash
set -o xtrace

#
# Install NFS
#

apt install -y nfs-kernel-server
apt install -y nfs-common
cp exports /etc/exports
mkdir /nfs_data
cat fstab.server >> /etc/fstab

SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
  mkfs.ext4 /dev/drbd1000
  cat fstab.server >> /etc/fstab
  systemctl enable nfs-server
  systemctl start nfs-server
  mount -a
  mkdir -p /nfs_data/docker/volumes/config
fi
