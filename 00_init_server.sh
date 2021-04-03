#!/bin/bash
set -o xtrace

#
# Add User onebuck
#
adduser onebuck
usermod -aG sudo onebuck

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
# Set Firewall
#
cp iptables.conf /etc/iptables.conf
iptables-restore -n /etc/iptables.conf
cp iptables.service /etc/systemd/system/iptables.service
systemctl enable --now iptables

#
# Install Net Tools and XFS
#
apt install net-tools iftop -y
apt install xfsprogs -y

#
# Install LINSTOR & XFS
#
add-apt-repository -y ppa:linbit/linbit-drbd9-stack
apt-get update -y
apt-get install -y --no-install-recommends drbd-dkms drbd-utils lvm2 linstor-satellite linstor-client linstor-controller
apt install xfsprogs -y
cp linstor-client.conf /etc/linstor/linstor-client.conf
