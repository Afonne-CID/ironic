# Copyright 2018 Red Hat, Inc.
# All Rights Reserved.
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

import socket
import urllib

from oslo_log import log as logging
from oslo_utils import netutils

from ironic.common import exception
from ironic.common import states
from ironic.common import swift
from ironic.common import utils
from ironic.conf import CONF
from ironic.drivers.modules import ipmitool
from ironic import objects
from ironic.objects import node_inventory

LOG = logging.getLogger(__name__)
_OBJECT_NAME_PREFIX = 'inspector_data'


def create_ports_if_not_exist(task, macs=None):
    """Create ironic ports from MAC addresses data dict.

    Creates ironic ports from MAC addresses data returned with inspection or
    as requested by operator. Helper argument to detect the MAC address
    ``get_mac_address`` defaults to 'value' part of MAC address dict key-value
    pair.

    :param task: A TaskManager instance.
    :param macs: A sequence of MAC addresses. If ``None``, fetched from
        the task's management interface.
    """
    if macs is None:
        macs = task.driver.management.get_mac_addresses(task)
        if not macs:
            LOG.warning("Not attempting to create any port as no NICs "
                        "were discovered in 'enabled' state for node %s",
                        task.node.uuid)
            return

    node = task.node
    for mac in macs:
        if not netutils.is_valid_mac(mac):
            LOG.warning("Ignoring NIC address %(address)s for node %(node)s "
                        "because it is not a valid MAC",
                        {'address': mac, 'node': node.uuid})
            continue

        port_dict = {'address': mac, 'node_id': node.id}
        port = objects.Port(task.context, **port_dict)

        try:
            port.create()
            LOG.info("Port created for MAC address %(address)s for node "
                     "%(node)s", {'address': mac, 'node': node.uuid})
        except exception.MACAlreadyExists:
            LOG.info("Port already exists for MAC address %(address)s "
                     "for node %(node)s", {'address': mac, 'node': node.uuid})


def clean_up_swift_entries(task):
    """Delete swift entries containing inspection data.

    Delete swift entries related to the node in task.node containing
    inspection data. The entries are
    ``inspector_data-<task.node.uuid>-inventory`` for hardware inventory and
    similar for ``-plugin`` containing the rest of the inspection data.

    :param task: A TaskManager instance.
    """
    if CONF.inventory.data_backend != 'swift':
        return
    swift_api = swift.SwiftAPI()
    container = CONF.inventory.swift_data_container
    inventory_obj_name = f'{_OBJECT_NAME_PREFIX}-{task.node.uuid}-inventory'
    plugin_obj_name = f'{_OBJECT_NAME_PREFIX}-{task.node.uuid}-plugin'
    try:
        swift_api.delete_object(inventory_obj_name, container)
    except exception.SwiftOperationError as e:
        if not isinstance(e, exception.SwiftObjectNotFoundError):
            LOG.error("Object %(obj)s in container %(cont)s with inventory "
                      "for node %(node)s failed to be deleted: %(e)s",
                      {'obj': inventory_obj_name, 'node': task.node.uuid,
                       'e': e, 'cont': container})
            raise exception.SwiftObjectStillExists(obj=inventory_obj_name,
                                                   node=task.node.uuid)
    try:
        swift_api.delete_object(plugin_obj_name, container)
    except exception.SwiftOperationError as e:
        if not isinstance(e, exception.SwiftObjectNotFoundError):
            LOG.error("Object %(obj)s in container %(cont)s with plugin data "
                      "for node %(node)s failed to be deleted: %(e)s",
                      {'obj': plugin_obj_name, 'node': task.node.uuid,
                       'e': e, 'cont': container})
            raise exception.SwiftObjectStillExists(obj=plugin_obj_name,
                                                   node=task.node.uuid)


def store_inspection_data(node, inventory, plugin_data, context):
    """Store inspection data.

    Store the inspection data for a node. The storage is either the database
    or the Object Storage API (swift/radosgw) as configured.

    :param node: the Ironic node that the inspection data is about
    :param inventory: the inventory to store
    :param plugin_data: the plugin data (if any) to store
    :param context: an admin context
    """
    # If store_data == 'none', do not store the data
    store_data = CONF.inventory.data_backend
    if store_data == 'none':
        LOG.debug('Inspection data storage is disabled, the data will '
                  'not be saved for node %s', node.uuid)
        return
    if store_data == 'database':
        node_inventory.NodeInventory(
            context,
            node_id=node.id,
            inventory_data=inventory,
            plugin_data=plugin_data).create()
        LOG.info('Inspection data was stored in database for node %s',
                 node.uuid)
    if store_data == 'swift':
        swift_object_name = _store_inspection_data_in_swift(
            node_uuid=node.uuid,
            inventory_data=inventory,
            plugin_data=plugin_data)
        LOG.info('Inspection data was stored in Swift for node %(node)s: '
                 'objects %(obj_name)s-inventory and %(obj_name)s-plugin',
                 {'node': node.uuid, 'obj_name': swift_object_name})


def get_inspection_data(node, context):
    """Get inspection data.

    Retrieve the inspection data for a node either from database
    or the Object Storage API (swift/radosgw) as configured.

    :param node: the Ironic node that the required data is about
    :param context: an admin context
    :returns: dictionary with ``inventory`` and ``plugin_data`` fields
    :raises: NodeInventoryNotFound if no inventory has been saved
    """
    store_data = CONF.inventory.data_backend
    if store_data == 'none':
        raise exception.NodeInventoryNotFound(node=node.uuid)
    if store_data == 'database':
        node_inventory = objects.NodeInventory.get_by_node_id(
            context, node.id)
        return {"inventory": node_inventory.inventory_data,
                "plugin_data": node_inventory.plugin_data}
    if store_data == 'swift':
        try:
            return _get_inspection_data_from_swift(node.uuid)
        except exception.SwiftObjectNotFoundError:
            raise exception.NodeInventoryNotFound(node=node.uuid)


def _store_inspection_data_in_swift(node_uuid, inventory_data, plugin_data):
    """Uploads inspection data to Swift.

    :param data: data to store in Swift
    :param node_id: ID of the Ironic node that the data came from
    :returns: name of the Swift object that the data is stored in
    """
    swift_api = swift.SwiftAPI()
    swift_object_name = f'{_OBJECT_NAME_PREFIX}-{node_uuid}'
    container = CONF.inventory.swift_data_container
    swift_api.create_object_from_data(f'{swift_object_name}-inventory',
                                      inventory_data,
                                      container)
    swift_api.create_object_from_data(f'{swift_object_name}-plugin',
                                      plugin_data,
                                      container)
    return swift_object_name


def _get_inspection_data_from_swift(node_uuid):
    """Get inspection data from Swift.

    :param node_uuid: UUID of the Ironic node that the data came from
    :returns: dictionary with ``inventory`` and ``plugin_data`` fields
    """
    swift_api = swift.SwiftAPI()
    container = CONF.inventory.swift_data_container
    inv_obj = f'{_OBJECT_NAME_PREFIX}-{node_uuid}-inventory'
    plug_obj = f'{_OBJECT_NAME_PREFIX}-{node_uuid}-plugin'
    try:
        inventory_data = swift_api.get_object(inv_obj, container)
    except exception.SwiftOperationError:
        LOG.error("Failed to retrieve object %(obj)s from container %(cont)s",
                  {'obj': inv_obj, 'cont': container})
        raise exception.SwiftObjectNotFoundError(obj=inv_obj,
                                                 container=container,
                                                 operation='get')
    try:
        plugin_data = swift_api.get_object(plug_obj, container)
    except exception.SwiftOperationError:
        LOG.error("Failed to retrieve object %(obj)s from container %(cont)s",
                  {'obj': plug_obj, 'cont': container})
        raise exception.SwiftObjectNotFoundError(obj=plug_obj,
                                                 container=container,
                                                 operation='get')
    return {"inventory": inventory_data, "plugin_data": plugin_data}


LOOKUP_CACHE_FIELD = 'lookup_bmc_addresses'


def lookup_node(context, mac_addresses, bmc_addresses, node_uuid=None):
    """Do a node lookup by the information from the inventory.

    :param context: Request context
    :param mac_addresses: List of MAC addresses.
    :param bmc_addresses: List of BMC (realistically, IPMI) addresses.
    :param node_uuid: Node UUID (if known).
    :raises: NotFound with a generic message for all failures to avoid
        disclosing any information.
    """
    node = None
    if node_uuid:
        try:
            node = objects.Node.get_by_uuid(context, node_uuid)
        except exception.NotFound:
            # NOTE(dtantsur): we are reraising the same exception to make sure
            # we don't disclose the difference between nodes that are not found
            # at all and nodes in a wrong state by different error messages.
            raise exception.NotFound()

    if mac_addresses:
        try:
            node = objects.Node.get_by_port_addresses(context, mac_addresses)
        except exception.NotFound as exc:
            # The exception has enough context already, just log it and move on
            LOG.debug("Lookup for inspection: %s", exc)
        else:
            if node_uuid and node.uuid != node_uuid:
                LOG.error('Conflict on inspection lookup: node %(node1)s '
                          'does not match MAC addresses (%(macs)s), which '
                          'belong to node %(node2)s. This may be a sign of '
                          'incorrectly created ports.',
                          {'node1': node_uuid,
                           'node2': node.uuid,
                           'macs': ', '.join(mac_addresses)})
                raise exception.NotFound()

    # TODO(dtantsur): support active state inspection
    if node and node.provision_state != states.INSPECTWAIT:
        LOG.error('Node %(node)s was found during inspection lookup '
                  'with MAC addresses %(macs)s, but it is in '
                  'provision state %(state)s',
                  {'node': node.uuid,
                   'macs': ', '.join(mac_addresses),
                   'state': node.provision_state})
        raise exception.NotFound()

    # NOTE(dtantsur): in theory, if the node is found at this point, we could
    # short-circuit the lookup process and return it without considering BMC
    # addresses. However, I've seen cases where users ended up enrolling nodes
    # with BMC addresses from different nodes. Continuing to process BMC
    # addresses allows us to catch these situations that otherwise can lead
    # to updating wrong nodes.

    if bmc_addresses:
        # NOTE(dtantsur): the same BMC hostname can be used by several nodes,
        # e.g. in case of Redfish. Find all suitable nodes first.
        nodes_by_bmc = set()
        for candidate in objects.Node.list(
                context,
                filters={'provision_state': states.INSPECTWAIT},
                fields=['uuid', 'driver_internal_info']):
            # This field has to be populated on inspection start
            for addr in candidate.driver_internal_info.get(
                    LOOKUP_CACHE_FIELD) or ():
                if addr in bmc_addresses:
                    nodes_by_bmc.add(candidate.uuid)

        # NOTE(dtantsur): if none of the nodes found by the BMC match the one
        # found by the MACs, something is definitely wrong.
        if node and nodes_by_bmc and node.uuid not in nodes_by_bmc:
            LOG.error('Conflict on inspection lookup: nodes %(node1)s '
                      'and %(node2)s both satisfy MAC addresses '
                      '(%(macs)s) and BMC address(s) (%(bmc)s). The cause '
                      'may be ports attached to a wrong node.',
                      {'node1': ', '.join(nodes_by_bmc),
                       'node2': node.uuid,
                       'macs': ', '.join(mac_addresses),
                       'bmc': ', '.join(bmc_addresses)})
            raise exception.NotFound()

        # NOTE(dtantsur): at this point, if the node was found by the MAC
        # addresses, it also matches the BMC address. We only need to handle
        # the case when the node was not found by the MAC addresses.
        if not node and nodes_by_bmc:
            if len(nodes_by_bmc) > 1:
                LOG.error('Several nodes %(nodes)s satisfy BMC address(s) '
                          '(%(bmc)s), but none of them satisfy MAC addresses '
                          '(%(macs)s). Ports must be created for a successful '
                          'inspection in this case.',
                          {'nodes': ', '.join(nodes_by_bmc),
                           'macs': ', '.join(mac_addresses),
                           'bmc': ', '.join(bmc_addresses)})
                raise exception.NotFound()

            node_uuid = nodes_by_bmc.pop()
            try:
                # Fetch the complete object now.
                node = objects.Node.get_by_uuid(context, node_uuid)
            except exception.NotFound:
                raise  # Deleted in-between?

    if not node:
        LOG.error('No nodes satisfy MAC addresses (%(macs)s) and BMC '
                  'address(s) (%(bmc)s) during inspection lookup',
                  {'macs': ', '.join(mac_addresses),
                   'bmc': ', '.join(bmc_addresses)})
        raise exception.NotFound()

    LOG.debug('Inspection lookup succeeded for node %(node)s using MAC '
              'addresses %(mac)s and BMC addresses %(bmc)s',
              {'node': node.uuid, 'mac': mac_addresses, 'bmc': bmc_addresses})
    return node


def _get_bmc_addresses(node):
    """Get the BMC address defined in the node's driver_info.

    All valid hosts are returned along with their v4 and v6 IP addresses.

    :param node: Node object with defined driver_info dictionary
    :return: a set with suitable addresses
    """
    result = set()

    # FIXME(dtantsur): this extremely lame process is adapted from
    # ironic-inspector. Now that it's in Ironic proper, we need to replace it
    # with something using information from hardware types.
    for name, address in node.driver_info.items():
        if not name.endswith('_address'):
            continue

        # NOTE(sambetts): IPMI address is useless to us if bridging is enabled
        # so just ignore it.
        if (name.startswith('ipmi_')
                and ipmitool.is_bridging_enabled(node)):
            LOG.debug('Will not used %(field)s %(addr)s for lookup since '
                      'IPMI bridging is enabled for node %(node)s',
                      {'addr': address, 'field': name, 'node': node.uuid})
            continue

        if '//' in address:
            address = urllib.parse.urlparse(address).hostname

        # Strip brackets in case used on IPv6 address.
        address = address.strip('[').strip(']')

        try:
            addrinfo = socket.getaddrinfo(address, None, proto=socket.SOL_TCP)
        except socket.gaierror as exc:
            LOG.warning('Failed to resolve the hostname (%(addr)s) in '
                        '%(field)s of node %(node)s: %(exc)s',
                        {'addr': address, 'field': name, 'node': node.uuid,
                         'exc': exc})
            continue

        for *other, sockaddr in addrinfo:
            ip = sockaddr[0]
            if utils.is_loopback(ip):
                LOG.warning('Ignoring loopback %(field)s %(addr)s '
                            'for node %(node)s',
                            {'addr': ip, 'field': name, 'node': node.uuid})
            else:
                result.add(ip)

        if not utils.is_loopback(address):
            result.add(address)

    return result


def cache_lookup_addresses(node):
    """Cache lookup addresses for a quick access."""
    addresses = _get_bmc_addresses(node)
    if addresses:
        LOG.debug('Will use the following BMC addresses for inspection lookup '
                  'of node %(node)s: %(addr)s',
                  {'node': node.uuid, 'addr': addresses})
        node.set_driver_internal_info(LOOKUP_CACHE_FIELD, list(addresses))
    else:
        LOG.debug('No BMC addresses to use for inspection lookup of node %s',
                  node.uuid)
        clear_lookup_addresses(node)


def clear_lookup_addresses(node):
    """Remove lookup addresses cached on the node."""
    return node.del_driver_internal_info(LOOKUP_CACHE_FIELD)
