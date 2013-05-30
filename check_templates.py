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

check_templates = {
    'GANETI_RAPI_HOST': {
        'required': True,
        'value_type': str
    },

    'GANETI_RAPI_PORT': {
        'required': True,
        'value_type': int
    },

    'GANETI_RAPI_USERNAME': {
        'required': True,
        'value_type': str
    },

    'GANETI_RAPI_PASSWORD': {
        'required': True,
        'value_type': str
    },

    'REPORT_ACTIONS': {
        'required': True,
        'value_type': list,
        'templates': ['Actions list'],
        'list_unique_items': True
    },

    'Actions list': {
        'required': False,
        'value_type': str,
        'values': ['export', 'clean']
    },

    'SMTP_HOST': {
        'required': True,
        'value_type': str
    },

    'SMTP_PORT': {
        'required': True,
        'value_type': int
    },

    'SMTP_AUTH_USER': {
        'required': True,
        'value_type': str
    },

    'SMTP_AUTH_PASSWORD': {
        'required': True,
        'value_type': str
    },

    'EMAIL_FROM': {
        'required': True,
        'value_type': str
    },

    'EMAIL_TO': {
        'required': True,
        'value_type': list,
        'templates': ['Recipients'],
        'list_unique_items': True
    },

    'Recipients': {
        'required': True,
        'value_type': str
    },

    'EXPORTS_ROOT': {
        'required': True,
        'value_type': str,
        'is_path': True,
        'create_path': True
    },

    'EXPORT_FORMAT': {
        'required': True,
        'value_type': str,
        'values': ['raw', 'partclone']
    },

    'EXPORT_METHOD': {
        'required': True,
        'value_type': str,
        'values': ['files', 'pipes', 'mounts']
    },

    'EXPORTS': {
        'required': True,
        'value_type': dict,
        'templates': ['Disk Export Definitions']
    },
   
    # DISK EXPORT DEFINITION LIST
    'Disk Export Definitions': {
        'required': True,
        'value_type': list,
        'templates': ['Disk Export Definition'],
        'list_unique_items': True,
        'list_item_unique_fields': ['disk'],
    },

    # DISK EXPORT DEFINITION
    'Disk Export Definition': {
        'required': True,
        'keys': ['disk', 'partitions'],
        'value_type': dict,
        'templates': [
            'Disk', ('Partitions list', 'Partitions string')
        ]
    },

    'Disk': {
        'required': True,
        'value_type': int
    },

    'Partitions list': {
        'required': True,
        'value_type': list,
        'templates': ['Partition'],
        'list_unique_items': True
    },

    'Partitions string': {
        'required': True,
        'value_type': str,
        'values': ['all', 'whole_disk']
    },

    'Partition': {
        'required': True,
        'value_type': int
    }

}

# vim: set filetype=python expandtab tabstop=4 shiftwidth=4 autoindent smartindent:
