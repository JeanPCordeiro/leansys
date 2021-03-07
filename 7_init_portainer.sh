#!/bin/bash
export DOMAIN=portainer.sys.hostby.link
export NODE_ID=$(docker info -f '{{.Swarm.NodeID}}')
docker node update --label-add portainer.portainer-data=true $NODE_ID
curl -L dockerswarm.rocks/portainer.yml -o portainer.yml
docker stack deploy -c portainer.yml portainer
docker stack ps portainer