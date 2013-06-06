#!/bin/bash

ansible-playbook -e target=cluster-nodes /opt/ganeti-backup/deploy/clean.yml
