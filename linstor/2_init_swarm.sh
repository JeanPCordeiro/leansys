#!/bin/bash
docker swarm init
docker node ls
docker swarm join-token manager
