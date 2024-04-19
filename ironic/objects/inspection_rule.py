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
from oslo_versionedobjects import base as object_base

from ironic.db import api as db_api
from ironic.objects import base
from ironic.objects import fields as object_fields
from ironic.objects import notification


@base.IronicObjectRegistry.register
class InspectionRule(base.IronicObject, object_base.VersionedObjectDictCompat):
    # Version 1.0: Initial version
    VERSION = '1.0'

    dbapi = db_api.get_instance()

    fields = {
        'id': object_fields.IntegerField(),
        'uuid': object_fields.UUIDField(nullable=False),
        'description': object_fields.StringField(nullable=True),
        'scope': object_fields.StringField(nullable=True),
        'disabled': object_fields.BooleanField(nullable=True),
        'actions': object_fields.ListOfFlexibleDictsField(nullable=False),
        'conditions': object_fields.ListOfFlexibleDictsField(nullable=False),
    }

    # NOTE(mgoddard): We don't want to enable RPC on this call just yet.
    # Remotable methods can be used in the future to replace current explicit
    # RPC calls.  Implications of calling new remote procedures should be
    # thought through.
    # @object_base.remotable
    def create(self, context=None):
        """Create a InspectionRule record in the DB.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api.
                        Unfortunately, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: InspectionRule(context).
        :raises: InspectionRuleName if a inspection rule with the same
            name exists.
        :raises: InspectionRuleAlreadyExists if a inspection rule with the same
            UUID exists.
        """
        values = self.do_version_changes_for_db()
        db_rule = self.dbapi.create_inspection_rule(values)
        self._from_db_object(self._context, self, db_rule)

    # NOTE(mgoddard): We don't want to enable RPC on this call just yet.
    # Remotable methods can be used in the future to replace current explicit
    # RPC calls.  Implications of calling new remote procedures should be
    # thought through.
    # @object_base.remotable_classmethod
    @classmethod
    def get_by_uuid(cls, context, uuid):
        """Find a inspection rule based on its UUID.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api.
                        Unfortunately, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: InspectionRule(context).
        :param uuid: The UUID of a inspection rule.
        :raises: InspectionRuleNotFound if the inspection rule no longer
            appears in the database.
        :returns: a :class:`InspectionRule` object.
        """
        db_rule = cls.dbapi.get_inspection_rule_by_uuid(uuid)
        rule = cls._from_db_object(context, cls(), db_rule)
        return rule

    # NOTE(mgoddard): We don't want to enable RPC on this call just yet.
    # Remotable methods can be used in the future to replace current explicit
    # RPC calls.  Implications of calling new remote procedures should be
    # thought through.
    # @object_base.remotable_classmethod
    @classmethod
    def list(cls, context, limit=None, marker=None, sort_key=None,
             sort_dir=None):
        """Return a list of InspectionRule objects.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api.
                        Unfortunately, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: InspectionRule(context).
        :param limit: maximum number of resources to return in a single result.
        :param marker: pagination marker for large data sets.
        :param sort_key: column to sort results by.
        :param sort_dir: direction to sort. "asc" or "desc".
        :returns: a list of :class:`InspectionRule` objects.
        """
        db_rules = cls.dbapi.get_inspection_rule_list(
            limit=limit, marker=marker, sort_key=sort_key, sort_dir=sort_dir)
        return cls._from_db_object_list(context, db_rules)

    def refresh(self, context=None):
        """Loads updates for this inspection rule.

        Loads a inspection rule with the same uuid from the database and
        checks for updated attributes. Updates are applied from
        the loaded rule column by column, if there are any updates.

        :param context: Security context. NOTE: This should only
                        be used internally by the indirection_api.
                        Unfortunately, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: Port(context)
        :raises: InspectionRuleNotFound if the inspection rule no longer
            appears in the database.
        """
        current = self.get_by_uuid(self._context, uuid=self.uuid)
        self.obj_refresh(current)
        self.obj_reset_changes()


@base.IronicObjectRegistry.register
class InspectionRuleCRUDNotification(notification.NotificationBase):
    """Notification emitted on inspection rule API operations."""
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'payload': object_fields.ObjectField('InspectionRuleCRUDPayload')
    }


@base.IronicObjectRegistry.register
class InspectionRuleCRUDPayload(notification.NotificationPayloadBase):
    # Version 1.0: Initial version
    VERSION = '1.0'

    SCHEMA = {
        'created_at': ('inspection_rule', 'created_at'),
        'description': ('inspection_rule', 'description'),
        'scope': ('inspection_rule', 'scope'),
        'disabled': ('inspection_rule', 'disabled'),
        'actions': ('inspection_rule', 'actions'),
        'conditions': ('inspection_rule', 'conditions'),
        'updated_at': ('inspection_rule', 'updated_at'),
        'uuid': ('inspection_rule', 'uuid')
    }

    fields = {
        'actions': object_fields.ListOfFlexibleDictsField(nullable=False),
        'conditions': object_fields.ListOfFlexibleDictsField(nullable=False),
        'created_at': object_fields.DateTimeField(nullable=True),
        'description': object_fields.StringField(nullable=True),
        'id': object_fields.IntegerField(),
        'disabled': object_fields.BooleanField(nullable=True),
        'scope': object_fields.StringField(nullable=True),
        'updated_at': object_fields.DateTimeField(nullable=True),
        'uuid': object_fields.UUIDField()
    }

    def __init__(self, inspection_rule, **kwargs):
        super(InspectionRuleCRUDPayload, self).__init__(**kwargs)
        self.populate_schema(inspection_rule=inspection_rule)
