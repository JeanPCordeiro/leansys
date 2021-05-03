#!/bin/bash
set -o xtrace

cat fstab.client >> /etc/fstab
mount -a

#
# Install Convoy Plugin
#
wget https://github.com/rancher/convoy/releases/download/v0.5.2/convoy.tar.gz
tar xvzf convoy.tar.gz
cp convoy/convoy convoy/convoy-pdata_tools /usr/local/bin/
mkdir -p /etc/docker/plugins/
bash -c 'echo "unix:///var/run/convoy/convoy.sock" > /etc/docker/plugins/convoy.spec'
cp convoy-plugin /etc/init.d/convoy-plugin
chmod +x /etc/init.d/convoy-plugin
systemctl enable convoy-plugin
systemctl start convoy-plugin
systemctl status convoy-plugin

#
# Create test Volume
#
SERVER=`hostname -s`
if [ "$SERVER" = vmi536198  ]; then
   docker volume create --name initvol -d convoy
   docker run -it --rm --name=cont -v initvol:/data --volume-driver=lade/linstor busybox ps aux
fi

