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

"""Add inspection rules

Revision ID: 21c48150dea9
Revises: 66bd9c5604d5
Create Date: 2024-08-14 14:13:24.462303

"""

from alembic import op
from oslo_db.sqlalchemy import types
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '21c48150dea9'
down_revision = '66bd9c5604d5'


def upgrade():
    op.create_table(
        'inspection_rules',
        sa.Column('version', sa.String(length=15), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False,
                  autoincrement=True),
        sa.Column('uuid', sa.String(36), primary_key=True),
        sa.Column('description', sa.Text),
        sa.Column('disabled', sa.Boolean, default=False),
        sa.Column('scope', sa.String(255), nullable=True, default=None),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid', name='uniq_inspection_rules0uuid'),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )

    op.create_table(
        'inspection_rule_conditions',
        sa.Column('version', sa.String(length=15), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False,
                  autoincrement=True),
        sa.Column('inspection_rule_id', sa.Integer(), nullable=False,
                  autoincrement=False),
        sa.Column('op', sa.String(255), nullable=False),
        sa.Column('multiple', sa.String(255), nullable=False),
        sa.Column('invert', sa.Boolean(), nullable=True, default=False),
        sa.Column('field', sa.Text),
        sa.Column('params', types.JsonEncodedDict),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['inspection_rule_id'],
                                ['inspection_rules.id']),
        sa.Index('inspection_rule_id', 'inspection_rule_id'),
        sa.Index('inspection_rule_conditions_condition_idx', 'condition'),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )

    op.create_table(
        'inspection_rule_actions',
        sa.Column('version', sa.String(length=15), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False,
                  autoincrement=True),
        sa.Column('inspection_rule_id', sa.Integer(), nullable=False,
                  autoincrement=False),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('params', types.JsonEncodedDict),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['inspection_rule_id'],
                                ['inspection_rules.id']),
        sa.Index('inspection_rule_id', 'inspection_rule_id'),
        sa.Index('inspection_rule_actions_action_idx', 'action'),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )
