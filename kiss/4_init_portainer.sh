#!/bin/bash
export DOMAIN=portainer.sys.lean-sys.com
export NODE_ID=$(docker info -f '{{.Swarm.NodeID}}')
docker node update --label-add portainer.portainer-data=true $NODE_ID
#curl -L dockerswarm.rocks/portainer.yml -o portainer.yml
docker stack deploy -c portainer-agent-stack.yml portainer
docker stack ps portainer
docker stack deploy -c swarmcron.yml swarmcron
docker stack ps swarmcron

