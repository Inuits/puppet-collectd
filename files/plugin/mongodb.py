#!/usr/bin/env python
#
################################
### File managed with puppet ###
################################
#
# Plugin to collectd statistics from MongoDB
#
# src: https://github.com/sebest/collectd-mongodb
#
# manually changes:
#   - deu (Zdenek Janda): automatic database discovery
#   - kayn (Pavel Pulec): collecting stats about replication lag etc..

import collectd
import socket
import pymongo
from pymongo import MongoClient
from pymongo.read_preferences import ReadPreference
from distutils.version import StrictVersion as V

def replication_get_time_diff(con):
    col = 'oplog.rs'
    local = con.local
    ol = local.system.namespaces.find_one({"name": "local.oplog.$main"})
    if ol:
        col = 'oplog.$main'
    firstc = local[col].find().sort("$natural", 1).limit(1)
    lastc = local[col].find().sort("$natural", -1).limit(1)
    first = firstc.next()
    last = lastc.next()
    tfirst = first["ts"]
    tlast = last["ts"]
    delta = tlast.time - tfirst.time
    return delta


class MongoDB(object):

    def __init__(self):
        self.plugin_name = "mongo"
        self.mongo_host = "127.0.0.1"
        self.mongo_port = 27017
        self.mongo_db = ""
        self.mongo_user = None
        self.mongo_password = None

        self.lockTotalTime = None
        self.lockTime = None
        self.accesses = None
        self.misses = None

    def submit(self, type, instance, value, db=None):
        if db:
            plugin_instance = '%s-%s' % (self.mongo_port, db)
        else:
            plugin_instance = str(self.mongo_port)
        v = collectd.Values()
        v.plugin = self.plugin_name
        v.plugin_instance = plugin_instance
        v.type = type
        v.type_instance = instance
        v.values = [value, ]
        v.dispatch()

    def do_server_status(self):
        con = MongoClient(host=self.mongo_host, port=self.mongo_port, read_preference=ReadPreference.SECONDARY)

        # get list of databases from running mongo
        if not self.mongo_db:
            self.mongo_db = con.database_names()
        db = con[self.mongo_db[0]]

        if self.mongo_user and self.mongo_password:
            db.authenticate(self.mongo_user, self.mongo_password)
        server_status = db.command('serverStatus')

        version = server_status['version']
        at_least_2_4 = V(version) >= V('2.4.0')

        # operations
        for k, v in server_status['opcounters'].items():
            self.submit('total_operations', k, v)

        # memory
        for t in ['resident', 'virtual', 'mapped']:
            self.submit('memory', t, server_status['mem'][t])

        # connections
        self.submit('connections', 'current', server_status['connections']['current'])
        if 'available' in server_status['connections']:
            self.submit('connections', 'available', server_status['connections']['available'])
        if 'totalCreated' in server_status['connections']:
            self.submit('connections', 'totalCreated', server_status['connections']['totalCreated'])

        # network
        if 'network' in server_status:
            for t in ['bytesIn', 'bytesOut', 'numRequests']:
                self.submit('bytes', t, server_status['network'][t])

        # locks
        if 'lockTime' in server_status['globalLock']:
            if self.lockTotalTime is not None and self.lockTime is not None:
                if self.lockTime == server_status['globalLock']['lockTime']:
                    value = 0.0
                else:
                    value = float(server_status['globalLock']['lockTime'] - self.lockTime) * 100.0 / float(server_status['globalLock']['totalTime'] - self.lockTotalTime)
                self.submit('percent', 'lock_ratio', value)

            self.lockTime = server_status['globalLock']['lockTime']
        self.lockTotalTime = server_status['globalLock']['totalTime']

        # indexes
        if 'indexCounters' in server_status:
            accesses = None
            misses = None
            index_counters = server_status['indexCounters'] if at_least_2_4 else server_status['indexCounters']['btree']

            if self.accesses is not None:
                accesses = index_counters['accesses'] - self.accesses
                if accesses < 0:
                    accesses = None
            misses = (index_counters['misses'] or 0) - (self.misses or 0)
            if misses < 0:
                misses = None
            if accesses and misses is not None:
                self.submit('cache_ratio', 'cache_misses', int(misses * 100 / float(accesses)))
            else:
                self.submit('cache_ratio', 'cache_misses', 0)
            self.accesses = index_counters['accesses']
            self.misses = index_counters['misses']

        for mongo_db in self.mongo_db:
            db = con[mongo_db]
            if self.mongo_user and self.mongo_password:
                con[self.mongo_db[0]].authenticate(self.mongo_user, self.mongo_password)
            db_stats = db.command('dbstats')

            # stats counts
            self.submit('counter', 'object_count', db_stats['objects'], mongo_db)
            self.submit('counter', 'collections', db_stats['collections'], mongo_db)
            self.submit('counter', 'num_extents', db_stats['numExtents'], mongo_db)
            self.submit('counter', 'indexes', db_stats['indexes'], mongo_db)

            # stats sizes
            self.submit('file_size', 'storage', db_stats['storageSize'], mongo_db)
            self.submit('file_size', 'index', db_stats['indexSize'], mongo_db)
            self.submit('file_size', 'data', db_stats['dataSize'], mongo_db)

        # Replica check

        rs_status = {}
        slaveDelays = {}
        # Get replica set status
        try:
            rs_status = con.admin.command("replSetGetStatus")
        except pymongo.errors.OperationFailure, e:
            if str(e).find('not running with --replSet"'):
                print "OK - Not running with replSet"
                con.disconnect()
                return 0

        rs_conf = con.local.system.replset.find_one()
        for member in rs_conf['members']:
            if member.get('slaveDelay') is not None:
                slaveDelays[member['host']] = member.get('slaveDelay')
            else:
                slaveDelays[member['host']] = 0

        # Find the primary and/or the current node
        primary_node = None
        host_node = None

        for member in rs_status["members"]:
            if member["stateStr"] == "PRIMARY":
                primary_node = member
            potential_hosts = [ socket.gethostname().split('.')[0], socket.gethostname(), self.mongo_host, socket.gethostbyname(socket.gethostname()) ]
            if member["name"].split(':')[0] in potential_hosts and int(member["name"].split(':')[1]) == self.mongo_port:
                host_node = member

        # Check if we're in the middle of an election and don't have a primary
        if primary_node is None:
            print "WARNING - No primary defined. In an election?"
            con.disconnect()
            return 1

        # Check if we failed to find the current host
        # below should never happen
        if host_node is None:
            print "CRITICAL - Unable to find host '" + self.mongo_host + "' in replica set."
            con.disconnect()
            return 2
        # Is the specified host the primary?
        if host_node["stateStr"] == "PRIMARY":
            print "OK - This is the primary."
            con.disconnect()
            return 0
        elif host_node["stateStr"] == "ARBITER":
            print "OK - This is an arbiter"
            con.disconnect()
            return 0
        else:
            # Find the difference in optime between current node and PRIMARY
            optime_lag = abs(primary_node["optimeDate"] - host_node["optimeDate"])

            try:  # work starting from python2.7
                lag = optime_lag.total_seconds()
            except:
                lag = float(optime_lag.seconds + optime_lag.days * 24 * 3600)

            # send message with lag
            self.submit('replication', 'lag-seconds', str(lag))

            # send message with lag in percentage
            try:
                con_primary = MongoClient(host=primary_node['name'].split(':')[0], port=int(primary_node['name'].split(':')[1]), read_preference=ReadPreference.SECONDARY)
            except:
                print "CRITICAL - Unable to connect to primary node" + primary_node['name'].split(':')[0]
                return 3

            primary_timediff = replication_get_time_diff(con_primary)
            if primary_timediff != 0:
                lag = int(float(lag) / float(primary_timediff) * 100)
            else:
                lag = 0
            self.submit('replication', 'lag-percentage', str(lag))
            con_primary.disconnect()
            con.disconnect()
            return 0


    def config(self, obj):
        for node in obj.children:
            if node.key == 'Port':
                self.mongo_port = int(node.values[0])
            elif node.key == 'Host':
                self.mongo_host = node.values[0]
            elif node.key == 'User':
                self.mongo_user = node.values[0]
            elif node.key == 'Password':
                self.mongo_password = node.values[0]
            elif node.key == 'Database':
                self.mongo_db = node.values
            else:
                collectd.warning("mongodb plugin: Unkown configuration key %s" % node.key)

mongodb = MongoDB()
collectd.register_read(mongodb.do_server_status)
collectd.register_config(mongodb.config)

# comment out the import of collectd, self.submit and collectd.xxx above and run
# this command below for testing purspose
# mongodb.do_server_status()
