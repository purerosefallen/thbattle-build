import gevent
from gevent.server import StreamServer
from server.core import Receptionist
from network import Endpoint

import logging
import sys

logging.basicConfig(stream=sys.stdout)
logging.getLogger().setLevel(logging.DEBUG)

def new_client(sock, addr):
    u = Endpoint.spawn(sock, addr)
    Receptionist.spawn(u)

server = StreamServer(('0.0.0.0', 9999), new_client, None)
server.serve_forever()

