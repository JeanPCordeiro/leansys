#!/bin/bash
export DOMAIN=sys.hostby.link
docker stack deploy -c scope.yml scope
docker stack ps scope
