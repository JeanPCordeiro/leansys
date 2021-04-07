#!/bin/bash
set -o xtrace

#
# Add User onebuck
#
adduser onebuck
usermod -aG sudo onebuck

#
# Install GlusterFS
#
apt install software-properties-common -y
add-apt-repository ppa:gluster/glusterfs-7 -y
apt update -y
apt install glusterfs-server -y
apt install glusterfs-client -y
systemctl start glusterd.service
systemctl enable glusterd.service
systemctl status glusterd.service

#
# Configure GlusterFS
#
SERVER=`hostname -s`
if [ "$SERVER" == vmi536198  ]; then
  gluster peer probe vmi522170.contaboserver.net
  gluster peer status
  gluster volume create volume1 replica 2 vmi536198.contaboserver.net:/gluster-storage vmi522170.contaboserver.net:/gluster-storage force
  gluster volume start dockervols
  gluster volume status
  gluster volume profile dockervols start
  gluster volume profile dockervols info
fi

#
# Install docker
#
sudo apt install apt-transport-https ca-certificates curl software-properties-common -y
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable" -y
sudo apt update -y
sudo apt install docker-ce -y
sudo systemctl status docker
sudo usermod -aG docker onebuck

#
# Reconfigure Docker
#
systemctl stop docker
mount -t glusterfs vmi536198.contaboserver.net:/dockervols /var/lib/docker/volumes
systemctl start docker
echo 'vmi536198.contaboserver.net:/dockervols /var/lib/docker/volumes glusterfs defaults,_netdev,backupvolfile-server=vmi522170.contaboserver.net0 0' >> /etc/fstab

#
# Set Firewall
#
cp iptables.conf /etc/iptables.conf
iptables-restore -n /etc/iptables.conf
cp iptables.service /etc/systemd/system/iptables.service
systemctl enable --now iptables

#
# Install Net Tools
#
apt install net-tools iftop -y

