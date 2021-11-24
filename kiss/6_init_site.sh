#!/bin/bash
export DOMAIN=lean-sys.com
export CLIENT_ID=website
docker stack deploy -c init_site.yml $CLIENT_ID
docker stack ps $CLIENT_ID
