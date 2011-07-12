#!/usr/bin/python
# Copyright (C) Citrix
#
# This program is free software; you can redistribute it and/or modify 
# it under the terms of the GNU Lesser General Public License as published 
# by the Free Software Foundation; version 2.1 only.
#
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the 
# GNU Lesser General Public License for more details.
#

import os, sys, re
from util import run, log

import unittest

iscsi_ls = [ "/usr/bin/iscsi-ls" ]
iscsi_inq = [ "/usr/bin/iscsi-inq" ]

# return the unit serial number
def page80(ip, iqn, lun):
    lines = run(iscsi_inq + [ "-e", "1", "-c", "128", "iscsi://%s/%s/%d" % (ip, iqn, lun) ])
    for line in lines:
        m = re.match('^Unit Serial Number:\[(.+)\]\n$', line)
        if m:
            return m.group(1)
    return None

# return the SCSIid
def page83(ip, iqn, lun):
    lines = run(iscsi_inq + [ "-e", "1", "-c", "131", "iscsi://%s/%s/%d" % (ip, iqn, lun) ])
    for line in lines:
        m = re.match('^Designator:\[(.+)\]\n$', line)
        return m.group(1)
    return None

# return the Vendor
def vendor(ip, iqn, lun):
    lines = run(iscsi_inq + [ "iscsi://%s/%s/%d" % (ip, iqn, lun) ])
    for line in lines:
        m = re.match('^Vendor:(.+)\n$', line)
        if m:
            return m.group(1)

# Return a map of target -> LUN list
def list(ip):
    results = {}
    current_luns = []
    current_target = None
    lines = run(iscsi_ls + [ "-s", "iscsi://" + ip ])
    for line in lines:
        m = re.match('^Target:(\S+) Portal:(\S+)\n$', line)
        if m:
            if current_luns <> []:
                results[current_target] = current_luns
            current_target = m.group(1)
            current_luns = []
        m = re.match('^Lun:(\d+)\s+.*\(Size:(.+)\)\n$', line)
        if m:
            lun = int(m.group(1))
            size = m.group(2)
            if size.endswith("k"):
                bytes = long(size[0:-1]) * 1024L
            elif size.endswith("M"):
                bytes = long(size[0:-1]) * 1024L * 1024L
            elif size.endswith("G"):
                bytes = long(size[0:-1]) * 1024L * 1024L * 1024L
            elif size.endswith("T"):
                bytes = long(size[0:-1]) * 1024L * 1024L * 1024L * 1024L
            else:
                bytes = long(size)
            current_luns.append((lun, bytes))
    if current_luns <> []:
        results[current_target] = current_luns
    return results

    
