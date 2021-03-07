#!/bin/bash
git clone https://github.com/stefanprodan/swarmprom.git
cd swarmprom
export ADMIN_USER=admin
export HASHED_PASSWORD=$(openssl passwd -apr1)
export DOMAIN=sys.hostby.link
curl -L dockerswarm.rocks/swarmprom.yml -o swarmprom.yml
docker stack deploy -c swarmprom.yml swarmprom
docker stack ps swarmprom
