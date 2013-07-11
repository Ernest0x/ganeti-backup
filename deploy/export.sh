#!/bin/bash

PATH=$PATH;/usr/local/bin

ansible-playbook -e target=cluster-nodes /opt/ganeti-backup/deploy/export.yml
