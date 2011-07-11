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

tgtadm = [ "/usr/sbin/tgtadm", "--lld", "iscsi" ]

def show():
    global tgtadm
    cmd = tgtadm + [ "--op", "show", "--mode", "target" ]
    lines = run(cmd)
    results = []

    current = {}

    for line in lines:
        m = re.match('Target (\d+): (\S+)\n$', line)
        if m:
            current["tid"] = int(m.group(1))
            current["iqn"] = str(m.group(2))

        m = re.match('\s*LUN: (\d+)\n$', line)
        if m:
            current["lun"] = int(m.group(1))
        m = re.match('\s*SCSI ID: (\S+)\s+(\S+)\n$', line)
        if m:
            current["scsi_vendor"] = str(m.group(1))
            current["scsi_id"] = str(m.group(2))
        m = re.match('\s*SCSI SN: (\S+)\n$', line)
        if m:
            current["scsi_sn"] = str(m.group(1))
        m = re.match('\s*Backing store path: (\S+)\n$', line)
        if m:
            current["path"] = str(m.group(1))
            results.append(current)
    return results

def unique_tids(luns):
    return set(map(lambda x:x["tid"], luns))

def new(tid, iqn):
    global tgtadm
    cmd = tgtadm + [ "--op", "new", "--mode", "target", "--tid", str(tid), "-T", iqn ]
    run(cmd)

def delete(tid):
    global tgtadm
    cmd = tgtadm + [ "--op", "delete", "--mode", "target", "--tid=%d" % tid ]
    run(cmd)

# NB 3 threads are created for each LUN so we rapidly burn virtual memory
# in a 32-bit process.
def add_lun(tid, lun, device):
    global tgtadm
    cmd = tgtadm + [ "--op", "new", "--mode", "logicalunit", "--tid", str(tid), "--lun", str(lun), "-b", device ]
    run(cmd)

def remove_lun(tid, lun):
    global tgtadm
    cmd = tgtadm + [ "--op", "delete", "--mode", "logicalunit", "--tid", str(tid), "--lun", str(lun) ]
    run(cmd)    

class PreRequisites(unittest.TestCase):
    def testOutput(self):
        """show() should always produce some output and not fail"""
        show ()

iqn_counter = 1
def unique_iqn():
    global iqn_counter
    prefix = "iqn.2001-04.com.example"
    iqn_counter = iqn_counter + 1
    return "%s:%d" % (prefix, iqn_counter)

def make_sparse_file(size="1M"):
    path = "/tmp/block"
    try:
        os.unlink(path)
    except:
        pass
    run([ "/bin/dd", "if=/dev/zero", "of=%s" % path, "seek=1M", "count=0", "bs=1"])
    return path

class TestLUNs(unittest.TestCase):
    def setUp(self):
        self.dev = make_sparse_file()
        for tid in unique_tids(show()):
            delete(tid)
    def testOne(self):
        """Check that creating a target with a single LUN works"""
        new(1, unique_iqn())
        add_lun(1, 1, self.dev)
        luns = show()
        lun = luns[0]
        if lun["tid"] <> 1:
            raise "tid: expected %d, got %d" % (str(1), str(lun["tid"]))
        if lun["path"] <> self.dev:
            raise "path: expected %s, got %s" % (dev, lun["path"])
    def testMany(self):
        """Check that creating a target with many LUNs works"""
        new(1, unique_iqn())
        lun_ids = range(1, 100)
        for lun_id in lun_ids:
            add_lun(1, lun_id, self.dev)
        luns = show()
        self.failUnless(len(luns) == len(lun_ids) + 1)
        for lun in show():
            if lun["tid"] <> 1:
                raise "tid: expected %d, got %d" % (str(1), str(lun["tid"]))
            if lun["path"] <> self.dev:
                raise "path: expected %s, got %s" % (dev, lun["path"])

    def testReuse(self):
        """Check that the same LUN id can be re-used"""
        new(1, unique_iqn())
        add_lun(1, 1, self.dev)
        self.failUnless(len(show()) == 2)
        remove_lun(1, 1)
        self.failUnless(len(show()) == 1)

    def tearDown(self):
        os.unlink(self.dev)
        for tid in unique_tids(show()):
            delete(tid)
        


if __name__ == "__main__":
    unittest.main ()
