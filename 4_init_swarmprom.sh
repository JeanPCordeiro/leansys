#!/bin/bash
git clone https://github.com/stefanprodan/swarmprom.git
cd swarmprom
export ADMIN_USER=admin
export HASHED_PASSWORD=$(openssl passwd -apr1 $ADMIN_PASSWORD)
export DOMAIN=lescordeiro.fr
curl -L dockerswarm.rocks/swarmprom.yml -o swarmprom.yml
docker stack deploy -c swarmprom.yml swarmprom
docker stack ps swarmprom
