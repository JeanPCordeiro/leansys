#!/bin/bash
export DOMAIN=swarmpit.mercatum.fr
export NODE_ID=$(docker info -f '{{.Swarm.NodeID}}')
docker node update --label-add swarmpit.db-data=true $NODE_ID
docker node update --label-add swarmpit.influx-data=true $NODE_ID
curl -L dockerswarm.rocks/swarmpit.yml -o swarmpit.yml
docker stack deploy -c swarmpit.yml swarmpit
docker stack ps swarmpit
