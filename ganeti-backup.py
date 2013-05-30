#!/usr/bin/env python

# (c) 2013, Petros Moisiadis <ernest0x@yahoo.gr>
#
# ganeti-backup is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ganeti-backup is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ganeti-backup.  If not, see <http://www.gnu.org/licenses/>.


import conf
from os.path import exists as path_exists, dirname, isdir
from os import makedirs, mkfifo, mknod
from ganeti.rapi.client import GanetiRapiClient
from time import sleep
import shutil
import json
import sys
import argparse
import subprocess
import re
import math
import socket
import conf_checker
from check_templates import check_templates
from datetime import datetime, timedelta
from smtplib import SMTP_SSL
from email.MIMEText import MIMEText

class Error(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class GanetiBackup(object):

    def __init__(self):
        self.rapi_client = GanetiRapiClient(host=conf.GANETI_RAPI_HOST,
                                        port=conf.GANETI_RAPI_PORT,
                                        username=conf.GANETI_RAPI_USERNAME,
                                        password=conf.GANETI_RAPI_PASSWORD)
        self.local_node = socket.getfqdn()
        ganeti_conf_file = open('/var/lib/ganeti/config.data', 'r')
        self.ganeti_conf = json.load(ganeti_conf_file)

    def check_conf(self):
        confchecker = conf_checker.ConfChecker(conf, check_templates)
        confchecker.run()

    def get_instance_info(self, instance):
        jobid = self.rapi_client.GetInstanceInfo(instance)
        start = datetime.now()
        delta = timedelta(seconds=10)
        while True:
            sleep(3)
            job_change = self.rapi_client.WaitForJobChange(
                            jobid,['status', 'opresult'], None, None)
            if 'success' in job_change['job_info']:
                return job_change['job_info'][1][0]
            now = datetime.now()
            if now - delta > start:
                raise Error('Could not get information for instance' \
                            ' \'%s\'' % instance)

    def get_local_node_type(self, instance):
        info = self.rapi_client.GetInstance(instance)
        if self.local_node == info['pnode']:
            return 'primary'
        elif self.local_node in info['snodes']:
            return 'secondary'
        else:
            return 'unknown'

    def get_lvm_dev(self, instance_info, disk):
        instance_name = instance_info.keys()[0]
        instance_info = instance_info[instance_name]
        ret = None
        try:
            disk_info = instance_info['disks'][disk]
            for child in disk_info['children']:
                try:
                    child['logical_id'][1].rindex('disk%d_data' % disk)
                    ret = {
                        'devpath': '/dev/%s/%s' % (child['logical_id'][0],
                                                   child['logical_id'][1]),
                        'vg': child['logical_id'][0],
                        'name': child['logical_id'][1],
                        'size': child['size']
                    }
                    break
                except ValueError:
                    pass
        except KeyError, IndexError:
            raise Error('Could not get information for disk %d on' \
                        ' instance \'%s\'' % (disk, instance_name))
        if ret != None:
            return ret
        else:
            raise Error('Could not find LVM device for instance' % (
                                                       instance_name))

    def create_lvm_snapshot(self, lvm_dev, snapshot_name):
        # Here it is assumed that no more than 20% of the blocks will
        # change on the original volume during export.
        snapshot_size = int(math.ceil(lvm_dev['size'] * 0.2))
        try:
            subprocess.check_call(['lvcreate', '-L', str(snapshot_size), '-s',
                                   '-n', snapshot_name, lvm_dev['devpath']])
        except subprocess.CalledProcessError as err:
            raise Error('Could not create snapshot for lvm device \'%s\'' \
                        ' (returncode: %s, output: %s)' % (
                        lvm_dev['devpath'], err.returncode, err.output))

        snapshot_dev = {
            'devpath': '%s-snap' % lvm_dev['devpath'],
            'vg': lvm_dev['vg'],
            'name': snapshot_name,
            'size': snapshot_size
        }
        return snapshot_dev

    def remove_lvm_snapshot(self, snapshot_devpath):
        if snapshot_devpath.find('_data-snap') == -1:
            raise Error('It is not safe to remove lvm device \'%s\'' % (
                                                      snapshot_devpath,))
        try:
            subprocess.check_call(['lvremove', '-f', snapshot_devpath])
        except subprocess.CalledProcessError as err:
            raise Error('Could not remove lvm snapshot device \'%s\'' \
                        ' (returncode: %s, output: %s)' % (
                        snapshot_devpath, err.returncode, err.output))

    def canonical_fstype(self, fstype):
        if fstype in ['linux-swap(v0)', 'linux-swap(v1)', 'swsusp']:
            fstype = 'swap'
        elif fstype in ['fat16', 'fat32']:
            fstype = 'vfat'
        return fstype

    def get_partitions(self, snapshot_dev, export_partitions,
                       with_maps=False):
        try:
            output = subprocess.check_output(['parted', '-s', 
                        snapshot_dev['devpath'], 'unit', 'MB', 'print'])
        except subprocess.CalledProcessError as err:
            raise Error('Could not get partition table for device \'%s\'' \
                        ' (returncode: %s, output: %s)' % (
                        snapshot_dev['devpath'], err.returncode, err.output))

        partition_table = output
        partitions = []
        reg_string = '^\s+(?P<number>\d+)\s+\S+\s+\S+\s+(?P<size>\S+)\s+\S+\s+(?P<fstype>\S+)'
        partition_regexp = re.compile(reg_string)
        for line in output.split('\n'):
            match = partition_regexp.match(line)
            if match:
                partition_number = int(match.group('number'))
                size = int(math.ceil(float(match.group('size')[:-2])))
                fstype = self.canonical_fstype(match.group('fstype'))
                if fstype == 'swap':
                    continue
                if export_partitions == 'all' or \
                        partition_number in export_partitions:
                    partitions.append({
                        'number': partition_number,
                        'size': size,
                        'fstype': fstype
                    })

        if with_maps:
            return (
                partition_table, self.annotate_partition_maps(
                                      snapshot_dev, partitions))
        else:
            return (partition_table, partitions)

    def annotate_partition_maps(self, snapshot_dev, partitions):
        try:
            output = subprocess.check_output(['kpartx',
                                    '-a', '-p-', '-s', '-v',
                                    snapshot_dev['devpath']])
        except subprocess.CalledProcessError as err:
            raise Error('Could not create partition maps for device \'%s\'' \
                        ' (returncode: %s, output: %s)' % (
                        snapshot_dev['devpath'], err.returncode, err.output))

        map_regexp = re.compile('^add map (?P<map>\S+-(?P<partition_number>\d+))')
        for line in output.split('\n'):
            match = map_regexp.match(line)
            if match:
                partition_number = int(match.group('partition_number'))
                for index, partition in enumerate(partitions):
                    if partition['number'] == partition_number:
                        partitions[index]['map'] = match.group('map')
                        partitions[index]['devpath'] = '/dev/mapper/%s' % (
                                                   partitions[index]['map'],)
                        partitions[index]['name'] = '-'.join(
                            partitions[index]['map'].
                            replace('--', '!!').split('-')[1:]
                        ).replace('!!', '-')

        return partitions

    def unmap_partitions(self, snapshot_devpath):
        try:
            output = subprocess.check_output(['kpartx',
                                        '-d', '-p-', '-s', '-v',
                                         snapshot_devpath])
        except subprocess.CalledProcessError as err:
            raise Error('Could not unmap partitions for device \'%s\'' \
                        ' (returncode: %s, output: %s)' % (
                        snapshot_devpath, err.returncode, err.output))

    def create_instance_dir(self, instance):
        instance_dir = '%s/%s' % (conf.EXPORTS_ROOT, instance)
        if not path_exists(instance_dir):
            try:
                makedirs(instance_dir, 0740)
            except OSError as err:
                raise Error('Could not create instance export directory' \
                            ' \'%s\': %s' % (instance_dir, err))
        return instance_dir

    def remove_instance_dir(self, instance):
        instance_dir = '%s/%s' % (conf.EXPORTS_ROOT, instance)
        if path_exists(instance_dir):
            try:
                shutil.rmtree(instance_dir)
            except OSError as err:
                raise Error('Could not remove instance export directory' \
                            ' \'%s\': %s' % (instance_dir, err))

    def create_target(self, target_path, pipe=False):
        if not path_exists(target_path):
            if pipe:
                try:
                    mkfifo(target_path, 0640)
                except OSError as err:
                    raise Error('Could not create named pipe \'%s\': %s' % (
                                                        target_path, err))
            else:
                try:
                    mknod(target_path, 0640)
                except OSError as err:
                    raise Error('Could not create target file \'%s\': %s' % (
                                                        target_path, err))

    def fscheck(self, dev):
        if dev['fstype'] in ['ext2', 'ext3', 'ext4']:
            fsck_cmd = 'fsck.%s' % dev['fstype']
            try:
                subprocess.check_call([fsck_cmd, '-p', '-f', dev['devpath']])
            except subprocess.CalledProcessError as err:
                if err.returncode != 1:
                    raise Error('Could not check filesytem on \'%s\'' \
                                ' (returncode: %s, output: %s)' % (
                                dev['devpath'], err.returncode, err.output))
            sleep(1)

    def get_mounts(self):
        mounts = {}
        mounts_file = open('/proc/mounts', 'r')
        mounts_text = mounts_file.read()
        reg_string = '^(?P<devpath>\S+)\s(?P<mount_point>\S+)\s.*$'
        mount_regexp = re.compile(reg_string)
        for line in mounts_text.split('\n'):
            match = mount_regexp.match(line)
            if match:
                mounts[match.group('devpath')] = match.group('mount_point')
        mounts_file.close()
        return mounts

    def mount(self, dev, mount_path):
        mounts = self.get_mounts()
        if dev['devpath'] not in mounts:
            if not isdir(mount_path):
                if path_exists(mount_path):
                   raise Error('A non-directory filesystem entry with pathname'
                               ' \'%s\' already exists' % mount_path)
                try:
                    makedirs(mount_path)
                except OSError as err:
                    raise Error('Could not create mount point directory' \
                                ' \'%s\': %s' % (mount_path, err))
            try:
                subprocess.check_call(['mount', '-t', dev['fstype'], '-r',
                                       dev['devpath'], mount_path])
            except subprocess.CalledProcessError as err:
                raise Error('Could not mount filesytem on \'%s\'' \
                            ' to mount point at \'%s\'' \
                            ' (returncode: %s, output: %s)' % (
                             dev['devpath'], mount_path,
                             err.returncode, err.output))

    def unmount(self, dev):
        mounts = self.get_mounts()
        if dev['devpath'] in mounts:
            try:
                subprocess.check_call(['umount', dev['devpath']])
            except subprocess.CalledProcessError as err:
                raise Error('Could not unmount filesytem on \'%s\'' \
                            ' (returncode: %s, output: %s)' % (
                             dev['devpath'], err.returncode, err.output))

    def partclone(self, dev, target_path, format):
        if format == 'raw':
            partclone_cmd = 'partclone.dd'
        else:
            partclone_cmd = 'partclone.%s' % dev['fstype']

        args = (dev, target_path)
        logfile = '/var/log/%s.partclone.log' % dev['name']
        proc = subprocess.Popen([partclone_cmd, '-c', '-L', logfile,
                                '-s', dev['devpath'], '-O', target_path],
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)

        if conf.EXPORT_METHOD == 'files':
            returncode = proc.wait()
            if returncode != None and returncode != 0:
                raise Error('Could not clone from source \'%s\' to' \
                            ' target \'%s\' (returncode: %s)' % (
                            dev['devpath'], target_path, returncode))

        return (args, proc)

    def can_handle_instance(self, instance):
        instances = self.rapi_client.GetInstances()
        if instance not in instances:
            raise Error('There is no instance with name \'%s\'' % instance)
        local_node_type = self.get_local_node_type(instance)
        if local_node_type == 'primary':
            return True
        elif local_node_type == 'secondary':
            print ('Local node is not configured as primary for instance' \
                   ' \'%s\'\n  Skipping that instance...' % instance)
            return False
        elif local_node_type == 'unknown':
            print ('Local node does not host instance \'%s\'\n' \
                   '  Skipping that instance...' % instance)
            return False

    def send_error_report(self, action, error):
        subject = 'ganeti-backup.py: \'%s\': \'%s\' error' % (
                                        self.local_node, action)
        content = 'An error occured while running \'%s\' action on' \
                  ' node \'%s\':\n\n%s' % (action, self.local_node, error)
        msg = MIMEText(content, 'plain')
        msg['Subject'] = subject
        msg['From'] = conf.EMAIL_FROM
        try:
            conn = SMTP_SSL(conf.SMTP_HOST, conf.SMTP_PORT)
            conn.set_debuglevel(False)
            conn.login(conf.SMTP_AUTH_USER, conf.SMTP_AUTH_PASSWORD)
            try:
                conn.sendmail(conf.EMAIL_FROM, conf.EMAIL_TO, msg.as_string())
            except:
                conn.close()
        except Exception as err:
            raise Error('Sending error report failed: \'%s\'' % err)

    def clean(self):
        # TODO: send SIGTERM signal to partclone processes
        for instance in conf.EXPORTS:
            if not self.can_handle_instance(instance):
                continue

            instance_info = self.get_instance_info(instance)
            for ded in conf.EXPORTS[instance]:
                lvm_dev = self.get_lvm_dev(instance_info, ded['disk'])
                snapshot_dev = {
                    'devpath': '/dev/%s/%s-snap' % (
                        lvm_dev['vg'], lvm_dev['name'])
                }
                if conf.EXPORT_METHOD == 'mounts':
                    partition_table, partitions = self.get_partitions(
                                    snapshot_dev, 'all', with_maps=True)
                    for partition in partitions:
                        self.unmount(partition)
                sleep(2)
                self.unmap_partitions(snapshot_dev['devpath'])
                sleep(5)
                self.remove_lvm_snapshot(snapshot_dev['devpath'])
            self.remove_instance_dir(instance)

    def export_instance_conf(self, instance_info):
        instance_name = instance_info.keys()[0]
        instance_conf_path = '%s/%s/instance_conf' % (
                               conf.EXPORTS_ROOT, instance_name)
        try:
            instance_conf_file = open(instance_conf_path, 'w')
            instance_conf_file.write(json.dumps(instance_info))
            instance_conf_file.close()
        except Exception as err:
            raise Error('Could not export instance configuration for' \
                        ' instance \'%s\' (%s)' % (instance_name, str(err)))

    def export(self):
        partclone_tasks = []
        for instance in conf.EXPORTS:
            if not self.can_handle_instance(instance):
                continue

            instance_dir = self.create_instance_dir(instance)
            instance_info = self.get_instance_info(instance)
            self.export_instance_conf(instance_info)

            for ded in conf.EXPORTS[instance]: # ded: 'disk export definition'
                lvm_dev = self.get_lvm_dev(instance_info, ded['disk'])
                snapshot_name = '%s-snap' % lvm_dev['name']
                snapshot_dev = self.create_lvm_snapshot(
                                          lvm_dev, snapshot_name)
                partitions = ded['partitions']
                if partitions == 'all' or type(partitions) == list:
                    partition_table, partitions = self.get_partitions(
                              snapshot_dev, partitions, with_maps=True)
                    partition_table_path = '%s/disk%s_partition_table' % (
                                                 instance_dir, ded['disk'])
                    partition_table_file = open(partition_table_path, 'w')
                    partition_table_file.write(partition_table)
                    partition_table_file.close()
                    for partition in partitions:
                        self.fscheck(partition)
                        if conf.EXPORT_METHOD == 'mounts':
                            mount_path = '%s/%s' % (
                                        instance_dir, partition['name'])
                        else:
                            target_path = '%s/%s.img' % (
                                        instance_dir, partition['name'])
                        if conf.EXPORT_METHOD == 'pipes':
                            self.create_target(target_path, pipe=True)
                        elif conf.EXPORT_METHOD == 'files':
                            self.create_target(target_path)

                        if conf.EXPORT_METHOD == 'mounts':
                            self.mount(partition, mount_path)
                        else:
                            partclone_tasks.append(
                                self.partclone(partition, target_path,
                                               conf.EXPORT_FORMAT))
                elif partitions == 'whole_disk':
                    target_path = '%s/%s.img' % (instance_dir, snapshot_name)
                    if conf.EXPORT_METHOD == 'pipes':
                        self.create_target(target_path, pipe=True)
                    elif conf.EXPORT_METHOD in ['files', 'mounts']:
                        self.create_target(target_path)
                    partclone_tasks.append(
                        self.partclone(snapshot_dev, target_path, 'raw'))

        if conf.EXPORT_METHOD == 'pipes':
            # Sleep 1 sec for the last partclone task to attach to 
            # the pipe target
            sleep(1)
            # and check for early errors:
            for task in partclone_tasks:
                args, proc = task
                dev, target_path = args
                returncode = proc.poll()
                if returncode != None and returncode != 0:
                    raise Error('Could not clone from source \'%s\' to' \
                                ' target \'%s\' (returncode: %s)' % (
                                 dev['devpath'], target_path, returncode))
 
def main():
    parser = argparse.ArgumentParser(description='ganeti backup tool',
                                     add_help=False)
    parser.add_argument('action', choices=['export', 'clean'])
    args = parser.parse_args()
    gnt_bkp = GanetiBackup()
    try:
        gnt_bkp.check_conf()
    except conf_checker.Error as err:
        raise Error(err.msg)

    try:
        if args.action == 'export':
            gnt_bkp.export()
        elif args.action == 'clean':
            gnt_bkp.clean()
    except Exception as err:
        if args.action in conf.REPORT_ACTIONS:
            gnt_bkp.send_error_report(args.action, err)
            exit(1)
        else:
            raise err


if __name__ == "__main__":
    try:
        main()
    except Error as error:
        print >> sys.stderr, '%s: error: %s' % (sys.argv[0], error.msg)
        exit(1)

# vim: set filetype=python expandtab tabstop=4 shiftwidth=4 autoindent smartindent:
