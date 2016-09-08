#!/usr/bin/env python
# Copyright (c) 2016 Intel, Inc.
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

import urllib2
import urllib
import json
import requests
import sys
import traceback
import os
from oslo_log import log as logging
from oslo_config import cfg
from plasma.common.redfish import tree

LOG = logging.getLogger(__name__)
cfg.CONF.import_group('podm', 'plasma.common.redfish.config')

_DEAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)',
            'Content-Type': 'application/json',
            'Authorization': 'Basic YWRtaW46YWRtaW4='}

_VAILD_POWER_ACTION = [ "On", "ForceOff", "GracefulShutdown", "GracefulRestart", "ForceRestart" ]

def get_rfs_url(serviceext):
    REDFISH_BASE_EXT = "/redfish/v1/"
    INDEX = ''
    #INDEX = '/index.json'
    if REDFISH_BASE_EXT in serviceext:
        return cfg.CONF.podm.url + serviceext + INDEX
    else:
        return cfg.CONF.podm.url + REDFISH_BASE_EXT + serviceext + INDEX


def send_request(resource):
    jsonContent = ''
    url = get_rfs_url(resource)
    user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
    headers = {'User-Agent': user_agent,
               'Authorization': 'Basic YWRtaW46YWRtaW4='}
    req = urllib2.Request(url, None, headers)
    response = urllib2.urlopen(req)
    jsonContent = response.read()
    return json.loads(jsonContent.replace("\n", ""))

def filter_chassis(jsonContent, filterCondition):
    returnJSONObj = {}
    returnMembers = []
    parsed = json.loads(jsonContent)
    members = parsed['Members']
    count = parsed['Members@odata.count']
    for member in members:
        resource = member['@odata.id']
        memberJson = send_request(resource)
        memberJsonObj = json.loads(memberJson)
        chassisType = memberJsonObj['ChassisType']
        if chassisType == filterCondition:
            returnMembers.append(member)
            # print(resource)
        returnJSONObj["Members"] = returnMembers
        returnJSONObj["Members@odata.count"] = len(returnMembers)
    return returnJSONObj

def generic_filter(jsonContent, filterConditions):
    # returns boolean based on filters..its generic filter
    returnMembers = []
    is_filter_passed = False
    for fc in filterConditions:
        if fc in jsonContent:
            if jsonContent[fc].lower() == filterConditions[fc].lower():
                is_filter_passed = True
            else:
                is_filter_passed = False
	        break
        elif "/" in fc:
            querylst = fc.split("/")
            tmp = jsonContent
            for q in querylst:
                tmp = tmp[q]
            if tmp.lower() == filterConditions[fc].lower():
                is_filter_passed = True
            else:
                is_filter_passed = False
            break
        else:
            LOG.warn(" Filter string mismatch ")
    LOG.info(" JSON CONTENT " + str(is_filter_passed))
    return is_filter_passed

def racks():
    jsonContent = send_request('Chassis')
    racks = filter_chassis(jsonContent, 'Rack')
    return json.dumps(racks)


def pods():
    jsonContent = send_request('Chassis')
    pods = filter_chassis(jsonContent, 'Pod')
    return json.dumps(pods)


def urls2list(url):
    # This will extract the url values from @odata.id inside Members
    respdata = send_request(url)
    return [u['@odata.id'] for u in respdata['Members']]


def extract_val(data, path):
    # function to select value at particularpath
    patharr = path.split("/")
    for p in patharr:
        data = data[p]
    return data


def node_cpu_details(nodeurl):
    cpucnt = 0
    cpuarch = ""
    cpulist = urls2list(nodeurl + '/Processors')
    for lnk in cpulist:
        LOG.info("Processing CPU %s" % lnk)
        respdata = send_request(lnk)
        cores = extract_val(respdata, "TotalCores") or 1
        cpucnt += cores
        cpuarch = extract_val(respdata, "InstructionSet")
        cpumodel = extract_val(respdata, "Model")
        LOG.debug(" Cpu details %s: %d: %s: %s "
                  % (nodeurl, cpucnt, cpuarch, cpumodel))
    return {"count": str(cpucnt), "arch": cpuarch, "model": cpumodel}


def node_ram_details(nodeurl):
    # this extracts the RAM and returns as dictionary
    resp = send_request(nodeurl)
    ram = extract_val(resp, "MemorySummary/TotalSystemMemoryGiB")
    LOG.debug(" Total Ram for node %s : %d " % (nodeurl, ram))
    return str(ram)


def node_nw_details(nodeurl):
    # this extracts the total nw interfaces and returns as a string
    resp = send_request(nodeurl + "/EthernetInterfaces")
    nwi = extract_val(resp, "Members@odata.count")
    LOG.debug(" Total NW for node %s : %d " % (nodeurl, nwi))
    return str(nwi)


def node_storage_details(nodeurl):
    # this extracts the RAM and returns as dictionary
    storagecnt = 0
    hddlist = urls2list(nodeurl + "/SimpleStorage")
    for lnk in hddlist:
        resp = send_request(lnk)
        hdds = extract_val(resp, "Devices")
        for sd in hdds:
            if "CapacityBytes" in sd:
                if sd["CapacityBytes"] is not None:
                    storagecnt += sd["CapacityBytes"]
    LOG.debug("Total storage for node %s : %d " % (nodeurl, storagecnt))
    # to convert Bytes in to GB. Divide by 1073741824
    return str(storagecnt/1073741824).split(".")[0]


def systems_list(count=None, filters={}):
    nodesurllist = urls2list("Nodes")
    nodes_list = {'nodes':[url.split('/')[-1] for url in nodesurllist]}
    return json.dumps(nodes_list)

def get_chassis_list():
    chassis_lnk_lst = urls2list("Chassis")
    lst_chassis = []

    for clnk in chassis_lnk_lst:
        data = send_request(clnk)
        if "Links" in data:
            contains = []
            containedby = {}
            computersystems = []
            linksdata = data["Links"]
            if "Contains" in linksdata:
                for c in linksdata["Contains"]:
                    contains.append(c['@odata.id'].split("/")[-1])

            if linksdata.get("ContainedBy"):
                odata = linksdata["ContainedBy"]['@odata.id']
                containedby = odata.split("/")[-1]
            if "ComputerSystems" in linksdata:
                for c in linksdata["ComputerSystems"]:
                    computersystems.append(c['@odata.id'])

            name = data["ChassisType"] + ":" + data["Id"]
            c = {"name": name,
                 "ChassisType": data["ChassisType"],
                 "ChassisID": data["Id"],
                 "Contains": contains,
                 "ContainedBy": containedby,
                 "ComputerSystems": computersystems}
            lst_chassis.append(c)
    return lst_chassis


def get_nodebyid(nodeid):
    return json.dumps(send_request("Nodes/" + nodeid))


def assemble_node(node_id):
    data = '{}'
    url = get_rfs_url('Nodes/%s/Actions/ComposedNode.Assemble' % node_id)
    res = requests.post(url, data=data, headers=_DEAULT_HEADERS, verify=False)
    return res.content


def set_boot_source(node_id, boot_source):
    data = '{"Boot":{"BootSourceOverrideEnabled":"Once","BootSourceOverrideTarget":"%s"}}' % boot_source
    url = get_rfs_url('Nodes/%s' % node_id)
    res = requests.patch(url, data=data, headers=_DEAULT_HEADERS, verify=False)
    return res.content


def power_manage(power_args):
    node_id = power_args.get('node_id')
    power_action = power_args.get('power_action')
    if power_action not in _VAILD_POWER_ACTION:
        raise
    data = '{"ResetType":"%s"}' % power_action
    url = get_rfs_url('Nodes/%s/Actions/ComposedNode.Reset' % node_id)
    res = requests.post(url, data=data, headers=_DEAULT_HEADERS, verify=False)
    return res.content

def allocate_node(data):
    data = json.dumps(data)
    url = get_rfs_url('Nodes/Actions/Allocate')
    res=requests.post(url, data=data, headers=_DEAULT_HEADERS, verify=False)
    if not res.ok:
        raise
    node_id=json.loads(systems_list())['nodes'][-1]
    return get_nodebyid(node_id)

def delete_node(node_id):
    url = get_rfs_url('Nodes/%s' % node_id)
    res=requests.delete(url, headers=_DEAULT_HEADERS, verify=False)
    return res.content

def compose_nodes(data):
    node = allocate_node(data)
    node_id = json.loads(node).get('Id')
    assemble_node(node_id)
    return node

def build_hierarchy_tree():
    # builds the tree sturcture of the PODM data to get the location hierarchy
    lst_chassis = get_chassis_list()
    podmtree = tree.Tree()
    podmtree.add_node("0")  # Add root node
    for d in lst_chassis:
        podmtree.add_node(d["ChassisID"], d)

    for d in lst_chassis:
        containedby = d["ContainedBy"] if d["ContainedBy"] else "0"
        podmtree.add_node(d["ChassisID"], d, containedby)
        systems = d["ComputerSystems"]
        for sys in systems:
            sysname = sys.split("/")[-2] + ":" + sys.split("/")[-1]
            podmtree.add_node(sys, {"name": sysname}, d["ChassisID"])
    return podmtree

