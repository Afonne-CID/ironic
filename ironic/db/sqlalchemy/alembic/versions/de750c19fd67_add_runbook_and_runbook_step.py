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
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'runbooks',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('uuid', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('public', sa.Boolean, default=False),
        sa.Column('owner', sa.String(255), nullable=True),
        sa.Column('disable_ramdisk', sa.Boolean, default=False),
        sa.Column('extra', sa.JSONEncodedDict),
    )
    op.create_table(
        'runbook_steps',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('runbook_id', sa.Integer, sa.ForeignKey('runbooks.id')),
        sa.Column('interface', sa.String(255), nullable=False),
        sa.Column('step', sa.String(255), nullable=False),
        sa.Column('args', sa.JSONEncodedDict),
        sa.Column('order', sa.Integer),
    )
