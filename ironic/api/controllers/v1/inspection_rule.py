# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from http import client as http_client

from ironic_lib import metrics_utils
import jsonschema
from oslo_log import log
from oslo_utils import uuidutils
import pecan
from pecan import rest
from webob import exc as webob_exc

from ironic import api
from ironic.api.controllers import link
from ironic.api.controllers.v1 import collection
from ironic.api.controllers.v1 import notification_utils as notify
from ironic.api.controllers.v1 import utils as api_utils
from ironic.api import method
from ironic.common import args
from ironic.common import exception
from ironic.common.i18n import _
import ironic.conf
from ironic import objects


CONF = ironic.conf.CONF
LOG = log.getLogger(__name__)
METRICS = metrics_utils.get_metrics_logger(__name__)

DEFAULT_RETURN_FIELDS = ['uuid', 'description']


def _parse_path(path):
    """Parse path, extract scheme and path.

     Parse path with 'node' and 'data' scheme, which links on
     introspection data and node info respectively. If scheme is
     missing in path, default is 'data'.

    :param path: data or node path
    :return: tuple (scheme, path)
    """
    try:
        index = path.index('://')
    except ValueError:
        scheme = 'data'
        path = path
    else:
        scheme = path[:index]
        path = path[index + 3:]
    return scheme, path


def conditions_schema():
    global _CONDITIONS_SCHEMA
    if _CONDITIONS_SCHEMA is None:
        condition_plugins = [x.name for x
                             in api_utils.rule_conditions_manager()]
        _CONDITIONS_SCHEMA = {
            "title": "Inspector rule conditions schema",
            "type": "array",
            # we can have rules that always apply
            "minItems": 0,
            "items": {
                "type": "object",
                # field might become optional in the future, but not right now
                "required": ["op", "field"],
                "properties": {
                    "op": {
                        "description": "condition operator",
                        "enum": condition_plugins
                    },
                    "field": {
                        "description": "JSON path to field for matching",
                        "type": "string"
                    },
                    "multiple": {
                        "description": "how to treat multiple values",
                        "enum": ["all", "any", "first"]
                    },
                    "invert": {
                        "description": "whether to invert the result",
                        "type": "boolean"
                    },
                },
                # other properties are validated by plugins
                "additionalProperties": True
            }
        }

    return _CONDITIONS_SCHEMA


def actions_schema():
    global _ACTIONS_SCHEMA
    if _ACTIONS_SCHEMA is None:
        action_plugins = [x.name for x
                          in api_utils.rule_actions_manager()]
        _ACTIONS_SCHEMA = {
            "title": "Inspector rule actions schema",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["action"],
                "properties": {
                    "action": {
                        "description": "action to take",
                        "enum": action_plugins
                    },
                },
                # other properties are validated by plugins
                "additionalProperties": True
            }
        }

    return _ACTIONS_SCHEMA


def _validate_conditions(conditions_json):
    """Validates conditions from jsonschema.

    :returns: a list of conditions.
    """
    try:
        jsonschema.validate(conditions_json, conditions_schema())
    except jsonschema.ValidationError as e:
        msg = _('Validation failed for conditions: %s') % e
        raise exception.ClientSideError(
            msg, status_code=http_client.BAD_REQUEST)

    cond_mgr = api_utils.rule_conditions_manager()
    conditions = []
    reserved_params = {'op', 'field', 'multiple', 'invert'}
    for cond_json in conditions_json:
        field = cond_json['field']

        scheme, path = _parse_path(field)

        if scheme not in ('node', 'data'):
            msg = _('Unsupported scheme for field: %s, valid '
                    'values are node:// or data://') % scheme
            raise exception.Invalid(msg)

        # verify field as JSON path
        try:
            jsonpath.parse(path)
        except Exception as exc:
            msg = _('Unable to parse field JSON path %(field)s: '
                    '%(error)s') % {'field': field, 'error': exc}
            raise exception.Invalid(msg)

        plugin = cond_mgr[cond_json['op']].obj
        params = {k: v for k, v in cond_json.items()
                  if k not in reserved_params}
        try:
            plugin.validate(params)
        except ValueError as exc:
            msg = _('Invalid parameters for operator %(op)s: '
                    '%(error)s') % {'op': cond_json['op'], 'error': exc}
            raise exception.Invalid(msg)

        conditions.append((cond_json['field'],
                           cond_json['op'],
                           cond_json.get('multiple', 'any'),
                           cond_json.get('invert', False),
                           params))
    return conditions


def _validate_actions(actions_json):
    """Validates actions from jsonschema.

    :returns: a list of actions.
    """
    try:
        jsonschema.validate(actions_json, actions_schema())
    except jsonschema.ValidationError as e:
        msg = _('Validation failed for actions: %s') % e
        raise exception.Invalid(msg)

    act_mgr = api_utils.rule_actions_manager()
    actions = []
    for action_json in actions_json:
        plugin = act_mgr[action_json['action']].obj
        params = {k: v for k, v in action_json.items() if k != 'action'}
        try:
            plugin.validate(params)
        except ValueError as exc:
            msg = _('Invalid parameters for action %(act)s: '
                    '%(error)s') % {'act': action_json['action'], 'error': exc}
            raise exception.Invalid(msg)
        actions.append((action_json['action'], params))
    return actions


def rules_sanitize(inspection_rule, fields):
    """Removes sensitive and unrequested data.

    Will only keep the fields specified in the ``fields`` parameter.

    :param fields:
        list of fields to preserve, or ``None`` to preserve them all
    :type fields: list of str
    """
    api_utils.sanitize_dict(inspection_rule, fields)


def convert_with_links(rpc_rule, fields=None, sanitize=True):
    """Add links to the inspection rule."""
    inspection_rule = api_utils.object_to_dict(
        rpc_rule,
        fields=('description', 'scope', 'disabled'),
        link_resource='inspection',
    )
    inspection_rule['actions'] = list(
        api_utils.convert_actions(rpc_rule.actions))
    inspection_rule['conditions'] = list(
        api_utils.convert_conditions(rpc_rule.conditions))

    if fields is not None:
        api_utils.check_for_invalid_fields(fields, inspection_rule)

    if sanitize:
        rules_sanitize(inspection_rule, fields)

    return inspection_rule


def list_convert_with_links(rpc_rules, limit, fields=None, **kwargs):
    return collection.list_convert_with_links(
        items=[convert_with_links(t, fields=fields, sanitize=False)
               for t in rpc_rules],
        item_name='inspection rules',
        url='inspection',
        limit=limit,
        fields=fields,
        sanitize_func=rules_sanitize,
        **kwargs
    )


class InspectionRuleController(rest.RestController):
    """REST controller for inspection rules."""

    invalid_sort_key_list = []

    @pecan.expose()
    def _route(self, args, request=None):
        if not api_utils.allow_inspection_rules():
            msg = _("The API version does not allow inspection rules")
            if api.request.method == "GET":
                raise webob_exc.HTTPNotFound(msg)
            else:
                raise webob_exc.HTTPMethodNotAllowed(msg)
        return super(InspectionRuleController, self)._route(args, request)

    @METRICS.timer('InspectionRuleController.get_all')
    @method.expose()
    @args.validate(marker=args.name, limit=args.integer, sort_key=args.string,
                   sort_dir=args.string, fields=args.string_list,
                   detail=args.boolean)
    def get_all(self, marker=None, limit=None, sort_key='id', sort_dir='asc',
                fields=None, detail=None):
        """Retrieve a list of inspection rules.

        :param marker: pagination marker for large data sets.
        :param limit: maximum number of resources to return in a single result.
                      This value cannot be larger than the value of max_limit
                      in the [api] section of the ironic configuration, or only
                      max_limit resources will be returned.
        :param sort_key: column to sort results by. Default: id.
        :param sort_dir: direction to sort. "asc" or "desc". Default: asc.
        :param fields: Optional, a list with a specified set of fields
                       of the resource to be returned.
        :param detail: Optional, boolean to indicate whether retrieve a list
                       of inspection rules with detail.
        """
        if not api_utils.allow_inspection_rules():
            raise exception.NotFound()

        api_utils.check_allowed_fields(fields)
        api_utils.check_allowed_fields([sort_key])

        fields = api_utils.get_request_return_fields(fields, detail,
                                                     DEFAULT_RETURN_FIELDS)

        limit = api_utils.validate_limit(limit)
        sort_dir = api_utils.validate_sort_dir(sort_dir)

        if sort_key in self.invalid_sort_key_list:
            raise exception.InvalidParameterValue(
                _("The sort_key value %(key)s is an invalid field for "
                  "sorting") % {'key': sort_key})

        marker_obj = None
        if marker:
            marker_obj = objects.InspectionRule.get_by_uuid(
                api.request.context, marker)

        rules = objects.InspectionRule.list(
            api.request.context, limit=limit, marker=marker_obj,
            sort_key=sort_key, sort_dir=sort_dir)

        parameters = {'sort_key': sort_key, 'sort_dir': sort_dir}

        if detail is not None:
            parameters['detail'] = detail

        return list_convert_with_links(
            rules, limit, fields=fields, **parameters)

    @METRICS.timer('InspectionRuleController.get_one')
    @method.expose()
    @args.validate(runbook_ident=args.uuid_or_name, fields=args.string_list)
    def get_one(self, inspection_rule_ident, fields=None):
        """Retrieve information about the given inspection rule.

        :param runbook_ident: UUID or logical name of a inspection rule.
        :param fields: Optional, a list with a specified set of fields
            of the resource to be returned.
        """
        if not api_utils.allow_inspection_rules():
            raise exception.NotFound()

        api_utils.check_policy('baremetal:inspection_rule:get')
        rpc_rule = api_utils.get_inspection_rule(inspection_rule_ident)

        api_utils.check_allowed_fields(fields)
        return convert_with_links(rpc_rule, fields=fields)

    @METRICS.timer('InspectionRuleController.post')
    @method.expose(status_code=http_client.CREATED)
    @method.body('inspection_rule')
    def post(self, inspection_rule):
        """Create a new inspection rule.

        :param inspection_rule: a inspection rule within the request body.
        """
        if not api_utils.allow_inspection_rules():
            raise exception.NotFound()

        context = api.request.context
        api_utils.check_policy('baremetal:inspection_rule:create')

        validated_conditions = _validate_conditions(
            inspection_rule.get('conditions', []))
        validated_actions = _validate_actions(
            inspection_rule.get('actions', []))

        inspection_rule['actions'] = validated_actions
        inspection_rule['conditions'] = validated_conditions

        if not inspection_rule.get('uuid'):
            inspection_rule['uuid'] = uuidutils.generate_uuid()
        new_rule = objects.InspectionRule(context, **inspection_rule)

        notify.emit_start_notification(context, new_rule, 'create')
        with notify.handle_error_notification(context, new_rule, 'create'):
            new_rule.create()

        # Set the HTTP Location Header
        api.response.location = link.build_url('inspection rules',
                                               new_rule.uuid)
        api_rule = convert_with_links(new_rule)
        notify.emit_end_notification(context, new_rule, 'create')
        return api_rule

    @METRICS.timer('InspectionRuleController.delete')
    @method.expose(status_code=http_client.NO_CONTENT)
    @args.validate(inspection_rule_ident=args.uuid_or_name)
    def delete(self, inspection_rule_ident):
        """Delete an inspection rule.

        :param inspection_rule_ident: UUID or logical name of an
            inspection rule.
        """
        if not api_utils.allow_inspection_rules():
            raise exception.NotFound()

        context = api.request.context
        api_utils.check_policy('baremetal:inspection_rule:delete')

        rpc_rule = api_utils.get_inspection_rule(inspection_rule_ident)
        notify.emit_start_notification(context, rpc_rule, 'delete')
        with notify.handle_error_notification(context, rpc_rule, 'delete'):
            rpc_rule.destroy()
        notify.emit_end_notification(context, rpc_rule, 'delete')
