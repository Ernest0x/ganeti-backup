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

from os.path import exists as path_exists
from os import makedirs
import conf

class Error(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class ConfChecker(object):

    def __init__(self, conf_module, check_templates):
        self.conf = conf_module
        self.templates = check_templates
        self.parent_template_names = self.get_parent_template_names()

    def check_bool(self, check_template, attr):
        if attr in check_template and check_template[attr]:
            return True
        else:
            return False

    def check_template(self, template_name, value=None):
        template = self.templates[template_name]
        if value == None:
            try:
                value = getattr(conf, template_name)
            except AttributeError:
                if template['required']:
                    raise Error('Required configuration option \'%s\''
                                ' is missing' % template_name)

        if type(value) != template['value_type']:
            raise Error('Wrong value type for configuration option \'%s\'' % (
                                                           template_name,))

        if 'values' in template and value not in template['values']:
            raise Error('Wrong value for configuration option \'%s\'' % (
                                                       template_name,))

        if self.check_bool(template, 'is_path') and \
                self.check_bool(template, 'create_path'):
            if not path_exists(value):
                try:
                    makedirs(value, 0740)
                except OSError as e:
                    raise Error('%s' % e)

        if template['value_type'] == dict:
            if 'keys' in template:
                for index, key in enumerate(template['keys']):
                    value_template_names = template['templates'][index]
                    if type(value_template_names) not in [list, tuple]:
                        value_template_names = (value_template_names,)
                    value_templates_results = []
                    for value_template_name in value_template_names:
                        if key not in value and \
                              self.templates[value_template_name]['required']:
                            raise Error('Required field \'%s\' is missing' \
                                        ' from \'%s\'' % (key, template_name))
                        try:
                            self.check_template(value_template_name,
                                                value[key])
                            value_templates_results.append('ok')
                        except Error as err:
                            value_templates_results.append(err)
                    if 'ok' not in value_templates_results:
                        errors = '\n'.join(
                            [str(err) for err in value_templates_results])
                        raise Error(errors)
            else:
                for key in value:
                    for value_template_name in template['templates']:
                        if key not in value and \
                              self.templates[value_template_name]['required']:
                            raise Error('Required field \'%s\' is missing' \
                                        ' from \'%s\'' % (key, template_name))

                        self.check_template(value_template_name, value[key])
 
        if template['value_type'] == list:
            found_items = []
            found_field_values = {}
            for item in value:
                if item in found_items and \
                        self.check_bool(template, 'list_unique_items'):
                    raise Error('\'%s\' list must contain unique items' % (
                                                         template_name,))
                found_items.append(item)

                if 'list_item_unique_fields' in template:
                    for field in template['list_item_unique_fields']:
                        if field in found_field_values:
                            if item[field] in found_field_values[field]:
                                raise Error('Values of \'%s\' field in the'
                                            ' \'%s\' list must be unique' % (
                                                    field, template_name))
                            found_field_values[field].append(item[field])
                        else:
                            found_field_values[field] = [item[field]]

                value_templates_results = []
                for value_template_name in template['templates']:
                    try:
                        self.check_template(value_template_name, item)
                        value_templates_results.append('ok')
                    except Error as err:
                        value_templates_results.append(err)
                if 'ok' not in value_templates_results:
                    errors = '\n'.join(
                        [str(err) for err in value_templates_results])
                    raise Error(errors)

    def get_parent_template_names(self):
        parent_template_names = []
        for template_name in self.templates:
            template = self.templates[template_name]
            parent_template_names.append(template_name)

        for template_name in self.templates:
            template = self.templates[template_name]
            if 'templates' in template: 
                for template_names in template['templates']:
                    if type(template_names) not in [list, tuple]:
                        template_names = (template_names,)
                    for child_template_name in template_names:
                        try:
                            parent_template_names.remove(child_template_name)
                        except ValueError:
                            pass
        return parent_template_names

    def run(self):
        for template_name in self.parent_template_names:
            self.check_template(template_name)


# vim: set filetype=python expandtab tabstop=4 shiftwidth=4 autoindent smartindent:
