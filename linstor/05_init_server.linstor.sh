#!/bin/bash
set -o xtrace

#
#
#
#docker plugin install linbit/linstor-docker-volume --alias linstor --disable
docker plugin install lade/linstor --alias linstor --disable
cp docker-volume.conf /etc/linstor/docker-volume.conf
docker plugin enable linstor

#
# Create test Volume
#
SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
   docker volume create -d linstor --opt fs=ext4 --opt size=2G testvol 
   docker run -it --rm --name=cont -v testvol:/data --volume-driver=linstor busybox ps aux
fi
