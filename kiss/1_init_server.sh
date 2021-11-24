#!/bin/bash
set -o xtrace

#
# Install fail2ban
#
apt install fail2ban -y
fail2ban-client status
fail2ban-client status sshd

#
# Add User csrlean
#
adduser leansys
usermod -aG sudo leansys

#
# Install docker
#
sudo apt install apt-transport-https ca-certificates curl software-properties-common -y
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable" -y
sudo apt update -y
sudo apt install docker-ce -y
sudo systemctl status docker
sudo usermod -aG docker csrlean

#
# Set Firewall
#
#cp iptables.conf /etc/iptables.conf
#iptables-restore -n /etc/iptables.conf
#cp iptables.service /etc/systemd/system/iptables.service
#systemctl enable --now iptables

#
# Install Net Tools and XFS
#
apt install net-tools iftop -y
apt install xfsprogs -y

