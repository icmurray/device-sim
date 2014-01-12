import logging
import random
import struct
import time

import pymodbus.datastore as datastore

_log = logging.getLogger(__name__)

# Some of the registers that we simulate
_HOUR_METER = 0xC550
_FREQUENCY = 0xC55E
_PHASE_CURRENT_1 = 0xC560
_NEUTRAL_CURRENT = 0xC566

'''
Register configuration tables for Dirus products
'''

TABLE_1 = dict( (addr,2) for addr in range(0xC550, 0xC58C + 1, 2) )
TABLE_2 = dict( (addr,2) for addr in range(0xC650, 0xC681 + 1, 2) )

TABLE_3 = dict( (addr,2) for addr in range(0xC750, 0xC78E + 1, 2) )
TABLE_3.update( dict( (addr,1) for addr in range(0xC790, 0xC795 + 1, 1) ))

TABLE_4 = dict( (addr,1) for addr in range(0xC850, 0xC871 + 1, 1) )
TABLE_5 = dict( (addr,1) for addr in range(0xC900, 0xC907 + 1, 1) )
TABLE_6 = dict( (addr,1) for addr in range(0xC950, 0xCA92 + 1, 1) )

TABLES = [TABLE_1, TABLE_2, TABLE_3, TABLE_4, TABLE_5, TABLE_6]

REGISTER_LIMITS = {
    50520: [0, 50000],
    50514: [0, 50000],
    50528: [0, 20000],
    50544: [0, 1000],
    50556: [0, 1000],
    50550: [0, 1000],
    50562: [-1000, 1000],
    
    50522: [0, 50000],
    50516: [0, 50000],
    50530: [0, 20000],
    50546: [0, 1000],
    50558: [0, 1000],
    50552: [0, 1000],
    50564: [-1000, 1000],
    
    50524: [0, 50000],
    50518: [0, 50000],
    50532: [0, 20000],
    50548: [0, 1000],
    50560: [0, 1000],
    50554: [0, 1000],
    50566: [-1000, 1000],
    
    50526: [3000, 7000],
    50534: [0, 20000],
    50536: [0, 1000],
    50540: [0, 1000],
    50538: [0, 1000],
    50542: [-1000, 1000],
}

ALL = {}
for t in TABLES:
    ALL.update(t)

_INITIAL_REGISTER_VALUES = dict((k,0) for k in ALL)
for addr, limits in REGISTER_LIMITS.items():
    _INITIAL_REGISTER_VALUES[addr] = int(sum(limits)/2)

def create():
    '''Create a new A40 slave

    For the timebeing this is just a stub.  But it does start the input registers
    at the correct address.
    '''
    return A40SlaveContext(
        di = datastore.ModbusSequentialDataBlock(0, [1]),
        co = datastore.ModbusSequentialDataBlock(0, [1]),
        ir = datastore.ModbusSequentialDataBlock(0, [1]),
        hr = A40HoldingRegistersDataBlock(_INITIAL_REGISTER_VALUES.copy())
    )

_ALL_REGISTERS = ALL

class A40SlaveContext(datastore.context.ModbusSlaveContext):
    '''
    Sub-class the standard slave context with one especially for the A40
    because the A40 refers to registers 1-16 as 1-16, and not 0-15 as it should
    according to section 4.4 of the modbus specification.  This class ensures
    that this SlaveContext behaves like an A40, and not like the standard
    modbus specification.
    '''

    def validate(self, fx, address, count=1):
        ''' Validates the request to make sure it is in range

        :param fx: The function we are working with
        :param address: The starting address
        :param count: The number of values to test
        :returns: True if the request in within range, False otherwise
        '''
        ## address = address + 1  # section 4.4 of specification
        _log.debug("validate[%d] %d:%d" % (fx, address, count))
        return self.store[self.decode(fx)].validate(address, count)

    def getValues(self, fx, address, count=1):
        ''' Validates the request to make sure it is in range

        :param fx: The function we are working with
        :param address: The starting address
        :param count: The number of values to retrieve
        :returns: The requested values from a:a+c
        '''
        ## address = address + 1  # section 4.4 of specification
        _log.debug("getValues[%d] %d:%d" % (fx, address, count))
        return self.store[self.decode(fx)].getValues(address, count)

    def setValues(self, fx, address, values):
        ''' Sets the datastore with the supplied values

        :param fx: The function we are working with
        :param address: The starting address
        :param values: The new values to be set
        '''
        ## address = address + 1  # section 4.4 of specification
        _log.debug("setValues[%d] %d:%d" % (fx, address, len(values)))
        self.store[self.decode(fx)].setValues(address, values)

class A40HoldingRegistersDataBlock(datastore.ModbusSparseDataBlock):
    '''A simulated datablock of registers for the Diris A40.

    A convenient subclass of a sparse data block, this transparantly handles
    the A40's multi-word registers upon initialization.

    It also dynamically updates its values using the twisted reactor.
    '''

    def __init__(self, values=None, dynamic=True):
        if values is None:
            values = {}
        assert set(values.keys()) <= set(_ALL_REGISTERS.keys())

        expanded_values = {}
        addrs = _ALL_REGISTERS.keys()
        for d in ( self._expand_register_value(addr, values.get(addr, 0)) \
                        for addr in addrs ):
            expanded_values.update(d)

        super(A40HoldingRegistersDataBlock, self).__init__(expanded_values)

        if dynamic:
            self._last_values = {}
            _log.debug("A40 Register Block initialised with dynamic updating")
            from twisted.internet import task
            self._start_time = time.time()
            l = task.LoopingCall(self._step)
            l.start(1.0)     # in seconds.

    def _expand_register_value(self, addr, value):
        '''Returns a dict of register addresses to register values.

        A40 registers can have register values greater than 2 bytes.  In which
        case the value is split across contiguous registers.

        This function takes a register address; looks up how wide it expects the
        value to be; and returns a mapping of register addresses to values.
        '''
        assert addr in _ALL_REGISTERS
        width = _ALL_REGISTERS[addr]

        to_return = {}
        for i, value in enumerate(_pack_value(value, width)):
            to_return[addr + i] = value

        return to_return

    def _step(self):
        '''Step to the next set of values in this simulated datablock'''
        elapsed_time = time.time() - self._start_time
        
        # The A40 updates its hour meter every 1/100-th of an hour, ie
        # every 36 seconds.
        diris_time = int(elapsed_time / 36)
        self.setValues(_HOUR_METER, self._expand_register_value(_HOUR_METER, diris_time))

        for k in _INITIAL_REGISTER_VALUES:
            self._update_varying_register(k)

        ##self._update_varying_register(_PHASE_CURRENT_1)
        ##self._update_varying_register(_FREQUENCY)
        ##self._update_varying_register(_NEUTRAL_CURRENT)

    def _update_varying_register(self, addr):
        limits = REGISTER_LIMITS.get(addr, [0, 1000])
        if addr not in self._last_values:
            self._last_values[addr] = int(sum(limits)/2.0)
        else:
            p = random.randint(0,100)
            if p < 25:
                self._last_values[addr] = min(limits[1],
                                              self._last_values[addr]+25)
            elif p < 50:
                self._last_values[addr] = max(limits[0],
                                              self._last_values[addr]-25)

        self.setValues(addr,
                       self._expand_register_value(addr, self._last_values[addr]))

_REGISTER_TYPES = {
    1: 'h',     # Signed short
    2: 'i',     # Signed int
    4: 'q',     # Signed long long
}

def _pack_value(value, width):
    '''Pack the given value as a list of 16-bit unsigned shorts.'''
    value_type = _REGISTER_TYPES[width]
    byte_string = struct.pack('>' + value_type, value)

    return [ struct.unpack('>H', byte_string[2*i : 2*i+2])[0] \
                    for i in xrange(width) ]

