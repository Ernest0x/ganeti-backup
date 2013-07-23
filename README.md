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

<pre># ansible-playbook -e target=utility-instance.example.org setup.yml</pre>

From inside the utility instance, exports can be done with:

<pre># ansible-playbook -e target=cluster-nodes /opt/ganeti-backup/deploy/export.yml</pre>

To clean exports after taking backups of them, run (from inside the utility instance):

<pre># ansible-playbook -e target=cluster-nodes /opt/ganeti-backup/deploy/clean.yml</pre>

'cluster-nodes' should be the name of a group that must be defined
to group all nodes of the cluster. This group must be defined in 
the ansible inventory accessed by ansible when called from inside
the utility instance.

A backup utility could be configured to:
1) run the export script at pre-backup stage
2) add the path for the exported instances in the list of the paths
   to include in the backup archive, and
3) run the clean script at post-backup stage

The 'inventory_vars.yml.example' file inside 'deploy' directory holds
documentation of all the configuration options required for the
installation and running of ganeti-backup. These configuration options
should be placed in the ansible inventory used for the deployment of
utility instances.

Known issues and limitations:
* Importing exported instances back to ganeti is not (yet) implemented.
