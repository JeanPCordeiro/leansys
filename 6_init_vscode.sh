#!/bin/bash
export DOMAIN=sys.hostby.link
export USERNAME=admin
export HASHED_PASSWORD=$(openssl passwd -apr1)
docker stack deploy -c vscode.yml vscode
docker stack ps vscode
