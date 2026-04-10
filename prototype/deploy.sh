#!/bin/bash
scp /Users/mheavers/Desktop/imperfecta/_project/prototype/orchestrator.py imperfecta-pi:~/
ssh imperfecta-pi "sudo systemctl restart orchestrator && sudo systemctl status orchestrator"
