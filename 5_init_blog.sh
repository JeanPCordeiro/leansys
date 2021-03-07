#!/bin/bash
export DOMAIN=sys.hostby.link
docker stack deploy -c blog.yml blog
docker stack ps blog
