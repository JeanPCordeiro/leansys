#!/bin/bash
set -o xtrace

#
# Install NFS
#

apt install -y nfs-kernel-server
apt install -y nfs-common
cp exports /etc/exports
mkdir /nfs_data

SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
  mkfs.ext4 /dev/drbd1000
  cat fstab.client >> /etc/fstab
  systemctl enable nfs-server
  systemctl start nfs-server
  mount -a
  mkdir -p /nfs_data/docker/volumes/config
fi
cat fstab.client >> /etc/fstab
mount -a

#
# Install Convoy Plugin
#
wget https://github.com/rancher/convoy/releases/download/v0.5.2/convoy.tar.gz
tar xvzf convoy.tar.gz
cp convoy/convoy convoy/convoy-pdata_tools /usr/local/bin/
bash -c 'echo "unix:///var/run/convoy/convoy.sock" > /etc/docker/plugins/convoy.spec'
cp convoy-plugin /etc/init.d/convoy-plugin
chmod +x /etc/init.d/convoy
systemctl enable convoy
systemctl start convoy
systemctl status convoy

#
# Create test Volume
#
SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
   docker volume create --name initvol --volume-driver=convoy
   docker run -it --rm --name=cont -v initvol:/data --volume-driver=lade/linstor busybox ps aux
fi

