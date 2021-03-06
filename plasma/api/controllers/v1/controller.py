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

from pecan import route, expose, request
from plasma.api.controllers.v1 import flavor as v1flavor
from plasma.api.controllers.v1 import nodes as v1nodes
from plasma.api.controllers import base 
from plasma.api.controllers import link
from plasma.api.controllers import types


class MediaType(base.APIBase):
    """A media type representation."""

    fields = {
        'base': {
            'validate': types.Text.validate
        },
        'type': {
            'validate': types.Text.validate
        },
    }


class V1(base.APIBase):
    """The representation of the version 1 of the API."""

    fields = {
        'id': {
            'validate': types.Text.validate
        },
        'media_types': {
            'validate': types.List(types.Custom(MediaType)).validate
        },
        'links': {
            'validate': types.List(types.Custom(link.Link)).validate
        },
        'services': {
            'validate': types.List(types.Custom(link.Link)).validate
        },
    }

    @staticmethod
    def convert():
        v1 = V1()
        v1.id = "v1"
        v1.links = [link.Link.make_link('self', request.host_url,
                                        'v1', '', bookmark=True),
                    link.Link.make_link('describedby',
                                        'http://docs.openstack.org',
                                        'developer/plasma/dev',
                                        'api-spec-v1.html',
                                        bookmark=True, type='text/html')]
        v1.media_types = [MediaType(base='application/json',
                          type='application/vnd.openstack.plasma.v1+json')]
        v1.services = [link.Link.make_link('self', request.host_url,
                                           'services', ''),
                       link.Link.make_link('bookmark',
                                           request.host_url,
                                           'services', '',
                                           bookmark=True)]
        return v1


class V1Controller(object):
    @expose('json')
    def index(self):
        return V1.convert()

route(V1Controller, 'flavor',  v1flavor.FlavorController())
route(V1Controller, 'nodes',  v1nodes.NodesController())
route(V1Controller, 'power',  v1nodes.NodePowerController())
route(V1Controller, 'bootsource',  v1nodes.NodeBootSourceController())
