ganeti-backup
=============

A utility to export ganeti instances in order to take backups

The utility is meant to be installed on a utility instance on
which cluster instances are to be exported.

ansible (http://ansible.cc) is used for both the installation of
ganeti-backup on the utility instance as well as for running
ganeti-backup from inside that instance to do the exports.
That means that ansible must be installed on both the utility
instance and on the host used to install ganeti-backup.

To install run:

<pre>\# ansible-playbook -e target=utility-instance.example.org setup.yml</pre>

From inside the utility instance, exports can be done with:

<pre>\# ansible-playbook -e target=cluster-nodes /opt/ganeti-backup/deploy/export.yml</pre>

To clean exports after taking backups of them, run (from inside the utility instance):

<pre>\# ansible-playbook -e target=cluster-nodes /opt/ganeti-backup/deploy/clean.yml</pre>

'cluster-nodes' should be a group name that groups all nodes 
of the cluster. It should be defined in the ansible inventory
seen by ansible running on the utility instance.

inventory_vars.yml.example holds documentation of all the configuration
options required for the installation and running of ganeti-backup. These
configuration options should be placed in the ansible inventory used for
the deployment of utility instances.

Known issues and limitations:
* Importing exported instances back to ganeti is not (yet) implemented.
