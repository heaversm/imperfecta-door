#!/bin/bash
# Override host with: PI_HOST=imperfecta-pi-gallery ./deploy.sh
PI_HOST="${PI_HOST:-imperfecta-pi}"
SRC=/Users/mheavers/Desktop/imperfecta/_project/prototype
scp $SRC/orchestrator.py $SRC/bg_removal_server.py "$PI_HOST":~/
ssh "$PI_HOST" "mkdir -p ~/static ~/captures"
scp $SRC/static/gallery.html "$PI_HOST":~/static/
ssh "$PI_HOST" "sudo systemctl restart orchestrator && sudo systemctl status orchestrator"
