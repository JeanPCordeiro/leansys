#!/bin/bash
export DOMAIN=hostby.link
docker stack deploy -c blog.yml blog
docker stack ps blog
