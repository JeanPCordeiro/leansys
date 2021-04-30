#!/bin/bash
set -o xtrace

#
# Create Virtual disk
#
fallocate -l 150G /disk150G.img
losetup -a
cp losetup.service /etc/systemd/system/losetup.service
systemctl enable --now losetup
losetup -a

