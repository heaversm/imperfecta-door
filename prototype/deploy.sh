#!/bin/bash
SRC=/Users/mheavers/Desktop/imperfecta/_project/prototype
scp $SRC/orchestrator.py $SRC/bg_removal_server.py imperfecta-pi:~/
ssh imperfecta-pi "mkdir -p ~/static ~/captures"
scp $SRC/static/gallery.html imperfecta-pi:~/static/
ssh imperfecta-pi "sudo systemctl restart orchestrator && sudo systemctl status orchestrator"
