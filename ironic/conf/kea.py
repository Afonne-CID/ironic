#
# Copyright 2022 Red Hat, Inc.
#
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

from oslo_config import cfg

from ironic.common.i18n import _

opts = [
    cfg.StrOpt('kea_url',
               default='http://localhost:8000',
               help=_('URL of the Kea DHCP server\'s HTTP API endpoint. '
                      'This endpoint is used for managing DHCP '
                      'configuration, reservations, leases and subnet '
                      'operations through Kea\'s HTTP API interface.')),
    cfg.IntOpt('request_timeout',
               default=10,
               help=_('Timeout in seconds for requests to the Kea API.')),
    cfg.IntOpt('max_retries',
               default=3,
               help=_('Maximum number of retry attempts for failed '
                      'requests.'))
]


def register_opts(conf):
    conf.register_opts(opts, group='kea')
