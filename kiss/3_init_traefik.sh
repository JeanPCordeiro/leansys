#!/bin/bash
set -o xtrace
docker network create --driver=overlay traefik-public
export NODE_ID=$(docker info -f '{{.Swarm.NodeID}}')
docker node update --label-add traefik-public.traefik-public-certificates=true $NODE_ID
export EMAIL=jeanpierre.cordeiro@gmail.com
export DOMAIN=traefik.sys.lean-sys.com
export USERNAME=admin
export HASHED_PASSWORD=$(openssl passwd -apr1)
#curl -L dockerswarm.rocks/traefik-host.yml -o traefik-host.yml
docker stack deploy -c traefik-host.yml traefik
docker stack ps traefik
docker service logs traefik_traefik
