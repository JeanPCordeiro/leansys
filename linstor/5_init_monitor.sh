#!/bin/bash
export ADMIN_USER=admin
export HASHED_PASSWORD=$(openssl passwd -apr1)
export DOMAIN=sys.csrlean.com
docker stack deploy -c monitor.yml monitor
docker stack ps monitor
