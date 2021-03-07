#!/bin/bash
export DOMAIN=sys.hostby.link
docker stack deploy -c vscode.yml vscode
docker stack ps vscode
