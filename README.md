ganeti-backup
=============

A utility to export ganeti instances in order to take backups

The utility is meant to be installed on a utility instance that
will be responsible (among other things, possibly) for running
cluster-wide instance exports.

ansible (http://ansible.cc) is used for both the installation of
ganeti-backup on the utility instance as well as for running
ganeti-backup from inside that instance. That means that ansible
must be installed on both the utility instance and on the host
used to install ganeti-backup.

To install run:

\# ansible-playbook -e target=utility-instance.example.org setup.yml

From inside the utility instance, exports can be triggered as:

\# ansible-playbook -e target=cluster-nodes /opt/ganeti-backup/deploy/export.yml

To clean exports, run (from inside the utility instance)

\# ansible-playbook -e target=cluster-nodes /opt/ganeti-backup/deploy/clean.yml

'cluster-nodes' should be a group name that groups all nodes 
of the cluster. It should be defined in the ansible inventory
seen by ansible running on the utility instance.

inventory_vars.yml.example holds ansible inventory variables
as configuration options required for the installation and
running of ganeti-backup. Read conf.py.j2 for documentation
about these configuration options

Known issues and limitations:
* Importing exported instances back to ganeti is not (yet) implemented.
