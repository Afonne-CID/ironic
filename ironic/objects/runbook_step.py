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
class RunbookStep(base.IronicObject, object_base.VersionedObjectDictCompat):
    # Version 1.0: Initial version
    VERSION = '1.0'

    dbapi = db_api.get_instance()

    fields = {
        'id': object_fields.IntegerField(),
        'uuid': object_fields.UUIDField(nullable=False),
        'runbook_id': object_fields.IntegerField(nullable=True),
        'step': object_fields.StringField(nullable=False),
        'args': object_fields.FlexibleDictField(),
        'order': object_fields.IntegerField()
    }

    def create(self, context=None):
        """Create a RunbookStep record in the DB.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: RunbookStep(context).
        :raises: RunbookStepDuplicateName if a runbook step with the same
            name exists.
        :raises: RunbookStepAlreadyExists if a runbook step with the same
            UUID exists.
        """
        values = self.do_version_changes_for_db()
        db_template = self.dbapi.create_runbook_step(values)
        self._from_db_object(self._context, self, db_template)

    def save(self, context=None):
        """Save updates to this RunbookStep.

        Column-wise updates will be made based on the result of
        self.what_changed().

        :param context: Security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: RunbookStep(context)
        :raises: RunbookStepDuplicateName if a runbook step with the same
            name exists.
        :raises: RunbookStepNotFound if the runbook step does not exist.
        """
        updates = self.do_version_changes_for_db()
        db_template = self.dbapi.update_runbook_step(self.uuid, updates)
        self._from_db_object(self._context, self, db_template)

    def destroy(self):
        """Delete the RunbookStep from the DB.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: RunbookStep(context).
        :raises: RunbookStepNotFound if the runbook step no longer
            appears in the database.
        """
        self.dbapi.destroy_runbook_step(self.id)
        self.obj_reset_changes()

    @classmethod
    def get_by_id(cls, context, runbook_step_id):
        """Find a runbook step based on its integer ID.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: RunbookStep(context).
        :param runbook_step_id: The ID of a runbook step.
        :raises: RunbookStepNotFound if the runbook step no longer
            appears in the database.
        :returns: a :class:`RunbookStep` object.
        """
        db_template = cls.dbapi.get_runbook_step_by_id(runbook_step_id)
        template = cls._from_db_object(context, cls(), db_template)
        return template

    @classmethod
    def get_by_uuid(cls, context, uuid):
        """Find a runbook step based on its UUID.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: RunbookStep(context).
        :param uuid: The UUID of a runbook step.
        :raises: RunbookStepNotFound if the runbook step no longer
            appears in the database.
        :returns: a :class:`RunbookStep` object.
        """
        db_template = cls.dbapi.get_runbook_step_by_uuid(uuid)
        template = cls._from_db_object(context, cls(), db_template)
        return template

    @classmethod
    def get_by_name(cls, context, name):
        """Find a runbook step based on its name.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: RunbookStep(context).
        :param name: The name of a runbook step.
        :raises: RunbookStepNotFound if the runbook step no longer
            appears in the database.
        :returns: a :class:`RunbookStep` object.
        """
        db_template = cls.dbapi.get_runbook_step_by_name(name)
        template = cls._from_db_object(context, cls(), db_template)
        return template

    @classmethod
    def list(cls, context, limit=None, marker=None, sort_key=None,
             sort_dir=None):
        """Return a list of RunbookStep objects.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: RunbookStep(context).
        :param limit: maximum number of resources to return in a single result.
        :param marker: pagination marker for large data sets.
        :param sort_key: column to sort results by.
        :param sort_dir: direction to sort. "asc" or "desc".
        :returns: a list of :class:`RunbookStep` objects.
        """
        db_templates = cls.dbapi.get_runbook_step_list(
            limit=limit, marker=marker, sort_key=sort_key, sort_dir=sort_dir)
        return cls._from_db_object_list(context, db_templates)

    @classmethod
    def list_by_names(cls, context, names):
        """Return a list of RunbookStep objects matching a set of names.

        :param context: security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: RunbookStep(context).
        :param names: a list of names to filter by.
        :returns: a list of :class:`RunbookStep` objects.
        """
        db_templates = cls.dbapi.get_runbook_step_list_by_names(names)
        return cls._from_db_object_list(context, db_templates)

    def refresh(self, context=None):
        """Loads updates for this runbook step.

        Loads a runbook step with the same uuid from the database and
        checks for updated attributes. Updates are applied from
        the loaded template column by column, if there are any updates.

        :param context: Security context. NOTE: This should only
                        be used internally by the indirection_api,
                        but, RPC requires context as the first
                        argument, even though we don't use it.
                        A context should be set when instantiating the
                        object, e.g.: Port(context)
        :raises: RunbookStepNotFound if the runbook step no longer
            appears in the database.
        """
        current = self.get_by_uuid(self._context, uuid=self.uuid)
        self.obj_refresh(current)
        self.obj_reset_changes()


@base.IronicObjectRegistry.register
class RunbookStepCRUDNotification(notification.NotificationBase):
    """Notification emitted on runbook step API operations."""
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'payload': object_fields.ObjectField('RunbookStepCRUDPayload')
    }


@base.IronicObjectRegistry.register
class RunbookStepCRUDPayload(notification.NotificationPayloadBase):
    # Version 1.0: Initial version
    VERSION = '1.0'

    SCHEMA = {
        'created_at': ('runbook_step', 'created_at'),
        'step': ('runbook_step', 'step'),
        'updated_at': ('runbook_step', 'updated_at'),
        'uuid': ('runbook_step', 'uuid')
    }

    fields = {
        'created_at': object_fields.DateTimeField(nullable=True),
        'extra': object_fields.FlexibleDictField(nullable=True),
        'name': object_fields.StringField(nullable=False),
        'disable_ramdisk': object_fields.BooleanField(default=False),
        'steps': object_fields.ListOfFlexibleDictsField(nullable=False),
        'updated_at': object_fields.DateTimeField(nullable=True),
        'uuid': object_fields.UUIDField(),
        'public': object_fields.BooleanField(default=False),
        'owner': object_fields.StringField(nullable=True)
    }

    def __init__(self, runbook_step, **kwargs):
        super(RunbookStepCRUDPayload, self).__init__(**kwargs)
        self.populate_schema(runbook_step=runbook_step)
