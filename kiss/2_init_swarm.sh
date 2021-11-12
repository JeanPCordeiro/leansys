#!/bin/bash
set -o xtrace

docker swarm init
docker node ls
docker swarm join-token manager
