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

from oslo_log import log as logging
import requests

from ironic.common import exception
from ironic.conf import CONF
from ironic.dhcp import base
from ironic import objects


LOG = logging.getLogger(__name__)


class KeaDHCPApi(base.BaseDHCP):
    def __init__(self):
        super(KeaDHCPApi, self).__init__()
        self.max_retries = CONF.dhcp.max_retries

        if not CONF.dhcp.kea_url:
            raise exception.DHCPConfigurationError(
                "Kea URL must be specified in configuration")

    def _make_request(self, command, arguments, services=None):
        payload = {
            "command": command,
            "service": services or ["dhcp4"],
            "arguments": arguments
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    "%s/v1" % CONF.dhcp.kea_url,
                    json=payload,
                    timeout=CONF.dhcp.request_timeout
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                LOG.warning(
                    "Timeout on attempt %d/%d for command %s",
                    attempt + 1, self.max_retries, command
                )
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    LOG.error("Failed to execute command %s: %s", command, e)
                    raise exception.DHCPConfigurationError(
                        "Failed to execute %s: %s" % (command, e)
                    )
                LOG.warning(
                    "Request failed on attempt %d/%d: %s",
                    attempt + 1, self.max_retries, e
                )

    def get_config(self):
        """Retrieve current Kea configuration."""
        return self._make_request("config-get", {})

    def set_config(self, config):
        """Update Kea configuration."""
        return self._make_request("config-set", {"config": config})

    def add_subnet(self, subnet_config, ip_version=4):
        """Add a new subnet to Kea."""
        command = "subnet%d-add" % ip_version
        return self._make_request(command, {"subnet": subnet_config})

    def get_statistics(self):
        """Retrieve DHCP server statistics."""
        return self._make_request("statistic-get-all", {})

    def _update_host_reservation(self, hw_address, options=None, remove=False):
        """Modify a host reservation in the Kea config file or hosts database.

        """
        # TODO(cid) add support/replace with the host database configuration
        # option in a central database managed by Ironic; the commands to have
        # Kea manage it at runtime without restarting the server is a premium
        # offering
        try:
            config = self.get_config()
            dhcp4_config = config['arguments']['Dhcp4']

            reservations = dhcp4_config.get('reservations', [])
            found = False
            for reservation in reservations:
                if reservation.get('hw-address') == hw_address:
                    reservation['option-data'] = options
                    found = True
                    break

            if not found:
                # Add new reservation if not found
                reservations.append({
                    'hw-address': hw_address,
                    'option-data': options
                })
                dhcp4_config['reservations'] = reservations

            self.set_config(config['arguments'])
            return True
        except Exception as e:
            LOG.error("Failed to update reservation for %s: %s", hw_address, e)
            return False

    def update_port_dhcp_opts(self, port_id, dhcp_options, context=None):
        """Update DHCP options for a specific port in Kea."""
        port = objects.Port.get(context, port_id)

        kea_options = []
        for opt in dhcp_options:
            kea_opt = {
                'name': opt['opt_name'],
                'data': opt['opt_value'],
                'always-send': True
            }
            if 'ip_version' in opt:
                kea_opt['space'] = f'dhcp{opt["ip_version"]}'
            kea_options.append(kea_opt)
        return self._update_host_reservation(port.address, kea_options)

    def update_dhcp_opts(self, task, options, vifs=None):
        """Update DHCP options for all ports associated with a node."""
        ports = vifs or task.ports
        success = True

        for port in ports:
            if not self.update_port_dhcp_opts(port.uuid, options):
                success = False
                LOG.error("Failed to update DHCP options for port %s", port.uuid)
        return success

    def clean_dhcp_opts(self, task):
        """Remove DHCP options for all ports associated with a node."""
        success = True
        for port in task.ports:
            if not self._update_host_reservation(port.address, remove=True):
                success = False
                LOG.error("Failed to clean DHCP options for port %s", port.uuid)
        return success

    def get_ip_addresses(self, task):
        """Retrieve IP addresses for all ports associated to a node."""
        addresses = []
        for port in task.ports:
            for command, service in [("lease4-get", "dhcp4"),
                                     ("lease6-get", "dhcp6")]:
                try:
                    response = self._make_request(
                        command,
                        {"hw-address": port.address},
                        services=[service]
                    )
                    leases = response.get("arguments", {}).get("leases", [])
                    if not leases:
                        LOG.warning("No leases found for port %s",
                                    port.address)
                    if service == "dhcp4":
                        addresses.extend([lease["ip-address"]
                                          for lease in leases])
                    else:
                        for lease in leases:
                            addresses.extend(lease.get("ip-addresses", []))
                except exception.DHCPConfigurationError as e:
                    LOG.warning(
                        "Failed to fetch %s addresses for port %s: %s",
                        service, port.address, e
                    )
        return addresses

    def supports_ipxe_tag(self):
        """Indicate whether the provider supports the 'ipxe' tag."""
        return True
