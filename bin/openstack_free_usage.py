#!/usr/bin/env python
# -*- coding: utf-8 -*-#
# @(#)openstack_free_usage.py
#
#
# Copyright (C) 2013, GC3, University of Zurich. All rights reserved.
#
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

__docformat__ = 'reStructuredText'

import argparse
import logging as syslogging
import sys
import time

from nova import flags

from nova import db
from nova import context
from nova.compute import instance_types
from nova.openstack.common import cfg
from nova.openstack.common import log as logging

logging.setup("nova")
log = logging.getLogger("nova")

FLAGS = flags.FLAGS
args = flags.parse_args(['openstack_free_usage'])

def count_free_slots_by_flavor(ctxt, nodes, flavor):
    count = 0
    max_count = 0
    for node in nodes:
        n_vms = min(
            (node.vcpus - node.vcpus_used) / flavor['vcpus'],
            node.free_ram_mb / flavor['memory_mb'],
            (node.local_gb - node.local_gb_used) / (
                flavor['root_gb'] + flavor['ephemeral_gb']))

        n_maxvms = min(
            (node.vcpus) / flavor['vcpus'],
            node.memory_mb / flavor['memory_mb'],
            (node.local_gb) / (
                flavor['root_gb'] + flavor['ephemeral_gb']))

        if n_vms > 0:
            count += n_vms
        if n_maxvms > 0:
            max_count += n_maxvms
        # print "Node %s, flavor %s, free cpus %d, free ram %s, count: %d" % (
        #     node.hypervisor_hostname, flavor['name'],
        #     node.vcpus - node.vcpus_used, node.free_ram_mb, n_vms)
    return (count, max_count)

def main(verbose, filter_flavors=[]):
    ctxt = context.get_admin_context()
    flavors = instance_types.get_all_types(ctxt).values()
    # compute_nodes = db.compute_node_get_all(ctxt)
    # compute_nodes.sort(key=lambda x: x.hypervisor_hostname)
    compute_nodes = []
    for s in db.service_get_all(ctxt):
        if not s.disabled:
            compute_nodes.extend(s.compute_node)

    compute_nodes.sort(cmp=lambda x,y: cmp(x.hypervisor_hostname, y.hypervisor_hostname))
            
    if verbose > 0:
        print "%d compute nodes" % len(compute_nodes)
        print "  vcpus total: %d" % sum(i.vcpus for i in compute_nodes)
        print "  vcpus used:  %d" % sum(i.vcpus_used for i in compute_nodes)
        print "  ram total:   %d mb" % sum(i.memory_mb for i in compute_nodes)
        print "  ram free:    %d mb" % sum(i.free_ram_mb for i in compute_nodes)
        print "  disk total:  %d gb" % sum(i.local_gb for i in compute_nodes)
        print "  disk used:   %d gb" % sum(i.local_gb_used for i in compute_nodes)
        print

    for node in compute_nodes:
        if node.local_gb - node.local_gb_used < 0 and verbose:
            print "WARNING: node %s, disk total/used/free: %d/%d/%d" % (
                node.hypervisor_hostname, node.local_gb, node.local_gb_used,
                (node.local_gb - node.local_gb_used))
        if verbose > 2:
            print "DEBUG: node %s: free cpus: %d/%d free mem: %d/%d, free disk: %d/%d" % (
                node.hypervisor_hostname, node.vcpus - node.vcpus_used, node.vcpus,
                node.free_ram_mb, node.memory_mb, node.local_gb - node.local_gb_used, node.local_gb
                )

    if filter_flavors:
        flavors = [f for f in flavors if f['name'] in filter_flavors]

    def cmp_flavor(x, y):
        cpus = cmp(x['vcpus'], y['vcpus'])
        return cpus if cpus else cmp(x['memory_mb'], y['memory_mb'])

    # flavors.sort(key=lambda x: x['vcpus'])
    flavors.sort(cmp=cmp_flavor)

    if verbose > 1:
        for flavor in flavors:
            print "Flavor '%s'" % flavor['name']
            print "  vcpus:  %d" % flavor['vcpus']
            print "  memory: %d mb" % flavor['memory_mb']
            print "  root disk: %d gb" % flavor['root_gb']
            print "  ephemeral disk: %d gb" % flavor['ephemeral_gb']
            print "Max nr. of VMs: %d (total capacity: %d)" % count_free_slots_by_flavor(
                ctxt, compute_nodes, flavor)
            print

    flavor_len = max(len(f['name']) for f in flavors)
    for flavor in flavors:
        print flavor['name'].ljust(flavor_len), ": %4d/%4d" % count_free_slots_by_flavor(
            ctxt, compute_nodes, flavor)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', help="Increase verbosity.", action="count", default=0)
    parser.add_argument('-f', '--flavor', help="Select flavor.", nargs="*", default=[])
    args = parser.parse_args()
    main(args.verbose, args.flavor)
