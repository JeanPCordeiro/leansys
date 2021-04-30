#!/bin/bash
set -o xtrace

#
# Enable LINSTOR
#
SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
  systemctl enable --now  linstor-controller
  systemctl status  linstor-controller
fi
systemctl enable --now  linstor-satellite

