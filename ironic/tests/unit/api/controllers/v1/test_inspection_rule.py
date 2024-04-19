#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Tests for the API /inspection_rules/ methods.
"""

import datetime
from http import client as http_client
from unittest import mock
from urllib import parse as urlparse

from oslo_config import cfg
from oslo_utils import timeutils
from oslo_utils import uuidutils

from ironic.api.controllers import base as api_base
from ironic.api.controllers import v1 as api_v1
from ironic.api.controllers.v1 import notification_utils
from ironic import objects
from ironic.objects import fields as obj_fields
from ironic.tests.unit.api import base as test_api_base
from ironic.tests.unit.api import utils as test_api_utils
from ironic.tests.unit.objects import utils as obj_utils


class BaseInspectionRulesAPITest(test_api_base.BaseApiTest):
    headers = {api_base.Version.string: str(api_v1.max_version())}
    invalid_version_headers = {api_base.Version.string: '1.92'}


class TestListInspectionRules(BaseInspectionRulesAPITest):

    def test_empty(self):
        data = self.get_json('/inspection_rules', headers=self.headers)
        self.assertEqual([], data['inspection rules'])

    def test_one(self):
        inspection_rule = obj_utils.create_test_inspection_rule(self.context)
        data = self.get_json('/inspection_rules', headers=self.headers)
        self.assertEqual(1, len(data['inspection rules']))
        self.assertEqual(inspection_rule.uuid,
                         data['inspection rules'][0]['uuid'])
        self.assertEqual(inspection_rule.description,
                         data['inspection rules'][0]['description'])
        self.assertNotIn('actions', data['inspection rules'][0])
        self.assertNotIn('conditions', data['inspection rules'][0])

