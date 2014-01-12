import logging

import twisted.protocols.policies as policies

import pymodbus.transaction as transaction
import pymodbus.server.async as async
import pymodbus.internal.ptwisted as ptwisted

_log = logging.getLogger(__name__)

def start(context, identity=None, address=None, console=False):
    ''' Helper method to start the Modbus Async TCP server

    :param context: The server data context
    :param identify: The server identity to use (default empty)
    :param address: An optional (interface, port) to bind to.
    :param console: A flag indicating if you want the debug console
    '''
    from twisted.internet import reactor

    address = address or ("", 502)
    framer  = transaction.ModbusSocketFramer
    factory = _GatewayServerFactory(context, framer, identity)
    if console: ptwisted.InstallManagementConsole({'factory': factory})

    _log.info("Starting Dirus Gateway Server on %s:%s" % address)
    reactor.listenTCP(address[1], factory, interface=address[0])
    reactor.run()

class _GatewayServerFactory(async.ModbusServerFactory,
                            policies.LimitTotalConnectionsFactory, object):

    connectionLimit = 4

