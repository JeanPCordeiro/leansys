#!/bin/bash
export DOMAIN=nidec.lean-sys.com
export CLIENT_ID=polico
docker stack deploy -c sigmasix.yml $CLIENT_ID
docker stack ps $CLIENT_ID
