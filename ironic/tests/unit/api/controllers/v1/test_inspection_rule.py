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
Tests for the API /inspection_rules methods.
"""
import datetime
from http import client as http_client
from unittest import mock

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
        self.assertEqual([], data['inspection_rules'])

    def test_one(self):
        inspection_rule = obj_utils.create_test_inspection_rule(self.context)
        data = self.get_json('/inspection_rules', headers=self.headers)
        self.assertEqual(1, len(data['inspection_rules']))
        self.assertEqual(inspection_rule.uuid,
                         data['inspection_rules'][0]['uuid'])
        self.assertEqual(inspection_rule.description,
                         data['inspection_rules'][0]['description'])
        self.assertNotIn('actions', data['inspection_rules'][0])
        self.assertNotIn('conditions', data['inspection_rules'][0])

    def test_get_one(self):
        rule = obj_utils.create_test_inspection_rule(self.context)
        data = self.get_json('/inspection_rules/%s' % rule.uuid,
                             headers=self.headers)
        self.assertEqual(rule.uuid, data['uuid'])
        self.assertIn('conditions', data)
        self.assertIn('actions', data)

    def test_get_all_invalid_api_version(self):
        obj_utils.create_test_inspection_rule(self.context)
        response = self.get_json('/inspection_rules',
                                 headers=self.invalid_version_headers,
                                 expect_errors=True)
        self.assertEqual(http_client.NOT_FOUND, response.status_int)

    def test_get_one_invalid_api_version(self):
        inspection_rule = obj_utils.create_test_inspection_rule(self.context)
        response = self.get_json(
            '/inspection_rules/%s' % (inspection_rule.uuid),
            headers=self.invalid_version_headers,
            expect_errors=True)
        self.assertEqual(http_client.NOT_FOUND, response.status_int)

    def test_get_all(self):
        obj_utils.create_test_inspection_rule(self.context)
        obj_utils.create_test_inspection_rule(self.context)
        data = self.get_json('/inspection_rules', headers=self.headers)
        self.assertEqual(2, len(data['inspection_rules']))


class TestPost(BaseInspectionRulesAPITest):
    @mock.patch.object(timeutils, 'utcnow', autospec=True)
    def test_create_inspection_rule(self, mock_utcnow):
        idict = test_api_utils.post_get_test_inspection_rule()
        test_time = datetime.datetime(2024, 8, 27, 0, 0)
        mock_utcnow.return_value = test_time

        response = self.post_json('/inspection_rules', idict,
                                  headers=self.headers)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(201, response.status_int)
        result = self.get_json('/inspection_rules/%s' % idict['uuid'],
                               headers=self.headers)
        self.assertEqual(idict['uuid'], result['uuid'])
        self.assertFalse(result['updated_at'])
        return_created_at = timeutils.parse_isotime(
            result['created_at']).replace(tzinfo=None)
        self.assertEqual(test_time, return_created_at)
        # Check location header
        self.assertIsNotNone(response.location)
        expected_location = '/v1/inspection_rules/%s' % idict['uuid']
        self.assertEqual(expected_location,
                         response.location[response.location.index('/v1'):])

    def test_create_inspection_rule_generate_uuid(self):
        idict = test_api_utils.post_get_test_inspection_rule()
        del idict['uuid']
        response = self.post_json('/inspection_rules', idict,
                                  headers=self.headers)
        result = self.get_json('/inspection_rules/%s' % response.json['uuid'],
                               headers=self.headers)
        self.assertTrue(uuidutils.is_uuid_like(result['uuid']))
        self.assertNotIn('id', result)


class TestPatch(BaseInspectionRulesAPITest):
    def test_patch_invalid_api_version(self):
        rule = obj_utils.create_test_inspection_rule(self.context)
        patch = [{'op': 'replace', 'path': '/description',
                  'value': 'New description'}]

        response = self.patch_json('/inspection_rules/%s' % rule.uuid,
                                   patch, headers=self.invalid_version_headers,
                                   expect_errors=True)
        self.assertEqual(http_client.METHOD_NOT_ALLOWED, response.status_int)


@mock.patch.object(objects.InspectionRule, 'destroy', autospec=True)
class TestDelete(BaseInspectionRulesAPITest):

    @mock.patch.object(notification_utils, '_emit_api_notification',
                       autospec=True)
    def test_delete_by_uuid(self, mock_notify, mock_destroy):
        rule = obj_utils.create_test_inspection_rule(self.context)
        self.delete('/inspection_rules/%s' % rule.uuid,
                    headers=self.headers)
        mock_destroy.assert_called_once_with(mock.ANY)
        mock_notify.assert_has_calls([mock.call(mock.ANY, mock.ANY, 'delete',
                                      obj_fields.NotificationLevel.INFO,
                                      obj_fields.NotificationStatus.START),
                                      mock.call(mock.ANY, mock.ANY, 'delete',
                                      obj_fields.NotificationLevel.INFO,
                                      obj_fields.NotificationStatus.END)])

    def test_delete_invalid_api_version(self, mock_destroy):
        rule = obj_utils.create_test_inspection_rule(self.context)
        response = self.delete(
            '/inspection_rules/%s' % rule.uuid,
            expect_errors=True,
            headers=self.invalid_version_headers)
        self.assertEqual(http_client.METHOD_NOT_ALLOWED, response.status_int)

    def test_delete_all(self, mock_destroy):
        obj_utils.create_test_inspection_rule(self.context)
        obj_utils.create_test_inspection_rule(self.context,
                                              uuid=uuidutils.generate_uuid())

        data = self.get_json('/inspection_rules', headers=self.headers)
        self.assertEqual(2, len(data['inspection_rules']))

        self.delete('/inspection_rules/all', headers=self.headers)

        data = self.get_json('/inspection_rules', headers=self.headers)
        self.assertEqual([], data['inspection_rules'])
