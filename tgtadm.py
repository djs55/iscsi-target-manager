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

def query_account():
    global tgtadm
    cmd = tgtadm + [ "--op", "show", "--mode", "account" ]
    lines = run(cmd)
    results = []

    reading_accounts = False
    for line in lines:
        m = re.match('^Account list:\n$', line)
        if m:
            reading_accounts = True
            continue
        if reading_accounts:
            m = re.match('^\s*(\S+)\n$',line)
            if m:
                results.append(m.group(1))
    return set(results)

def query_target():
    global tgtadm
    cmd = tgtadm + [ "--op", "show", "--mode", "target" ]
    lines = run(cmd)
    results = []
    acl = []

    current = {}
    lun = {}
    reading_acl = False

    for line in lines:
        m = re.match('Target (\d+): (\S+)\n$', line)
        if m:
            if current <> {}:
                results.append(current)
                current = {}
            current["tid"] = int(m.group(1))
            current["iqn"] = str(m.group(2))
            current["luns"] = []
            reading_acl = False

        if reading_acl:
            m = re.match('\s*(\S+)\n$', line)
            if m:
                current["acl"].append(str(m.group(1)))
            else:
                raise "Failed to parse ACL %s" % line
            continue

        m = re.match('\s*LUN: (\d+)\n$', line)
        if m:
            if lun <> {}:
                current["luns"].append(lun)
                lun = {}
            lun["id"] = int(m.group(1))
        m = re.match('\s*SCSI ID: (\S+)\s+(\S+)\n$', line)
        if m:
            lun["scsi_vendor"] = str(m.group(1))
            lun["scsi_id"] = str(m.group(2))
        m = re.match('\s*SCSI SN: (\S+)\n$', line)
        if m:
            lun["scsi_sn"] = str(m.group(1))
        m = re.match('\s*Backing store path: (\S+)\n$', line)
        if m:
            lun["path"] = str(m.group(1))
            if lun <> {}:
                current["luns"].append(lun)
                lun = {}

        m = re.match('\s*ACL information:\n$', line)
        if m:
            reading_acl = True
            current["acl"] = []

    if current <> {}:
        results.append(current)
        current = {}
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

def add_initiator(tid, initiator='ALL'):
    global tgtadm
    cmd = tgtadm + [ "--op", "bind", "--mode", "target", "--tid", str(tid), "-I", initiator ]
    run(cmd)

def remove_initiator(tid, initiator='ALL'):
    global tgtadm
    cmd = tgtadm + [ "--op", "unbind", "--mode", "target", "--tid", str(tid), "-I", initiator ]
    run(cmd)

def add_user(username, password):
    global tgtadm
    cmd = tgtadm + [ "--op", "new", "--mode", "account", "--user", username, "--password", password ]
    run(cmd)

def remove_user(username):
    global tgtadm
    cmd = tgtadm + [ "--op", "delete", "--mode", "account", "--user", username ]
    run(cmd)

class PreRequisites(unittest.TestCase):
    def testOutput(self):
        """query_target() should always produce some output and not fail"""
        query_target ()

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
        for tid in unique_tids(query_target()):
            delete(tid)
        for user in query_account():
            remove_user(user)
    def testOne(self):
        """Check that creating a target with a single LUN works"""
        new(1, unique_iqn())
        add_lun(1, 1, self.dev)
        targets = query_target()
        target = targets[0]
        if target["tid"] <> 1:
            raise "tid: expected %d, got %d" % (str(1), str(lun["tid"]))
        for lun in target["luns"]:
            if lun["id"] == 1:
                if lun["path"] <> self.dev:
                    raise "path: expected %s, got %s" % (self.dev, lun["path"])
    def testMany(self):
        """Check that creating a target with many LUNs works"""
        new(1, unique_iqn())
        lun_ids = range(1, 100)
        for lun_id in lun_ids:
            add_lun(1, lun_id, self.dev)
        targets = query_target()
        target = targets[0]
        luns = target["luns"]
        self.failUnless(len(luns) == len(lun_ids) + 1)
        for lun in luns:
            if lun["id"] in lun_ids:
                if lun["path"] <> self.dev:
                    raise "path: expected %s, got %s" % (self.dev, lun["path"])

    def testReuse(self):
        """Check that the same LUN id can be re-used"""
        new(1, unique_iqn())
        add_lun(1, 1, self.dev)
        self.failUnless(len(query_target()[0]["luns"]) == 2)
        remove_lun(1, 1)
        self.failUnless(len(query_target()[0]["luns"]) == 1)

    def testIP(self):
        """Check that we can add/remove initiator IPs"""
        new(1, unique_iqn())
        add_lun(1, 1, self.dev)
        self.failUnless(query_target()[0]["acl"] == [])
        add_initiator(1) # ALL
        self.failUnless(query_target()[0]["acl"] == [ "ALL" ])
        remove_initiator(1) # AL
        self.failUnless(query_target()[0]["acl"] == [])
        add_initiator(1, "127.0.0.1")
        self.failUnless(query_target()[0]["acl"] == [ "127.0.0.1" ])
        remove_initiator(1, "127.0.0.1")
        self.failUnless(query_target()[0]["acl"] == [])

    def testUser(self):
        """Check that we can add/remove users"""
        new(1, unique_iqn())
        add_user("root", "password")
        users = query_account()
        self.failUnless(users == set([ "root" ]))
        add_user("root2", "password")
        users = query_account()
        self.failUnless(users == set([ "root", "root2" ]))
        remove_user("root")

    def tearDown(self):
        os.unlink(self.dev)
        for tid in unique_tids(query_target()):
            delete(tid)
        for user in query_account():
            remove_user(user)


if __name__ == "__main__":
    unittest.main ()
