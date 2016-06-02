#!python

import cPickle as pickle
import SocketServer
import threading
import traceback
import logging
import socket
import struct
import time
import sys
import re

#----------------------------------------------------------------------------

class Relay (object):

    '''A general-purpose non-topological TCP/IP network message relay node.

    Unlike most network code which focuses on differences between "servers"
    and "clients," the Relay mechanism just refers to generic nodes
    throughout the network.  These relay nodes can be arranged in any
    sort of topology with simple routing rules.  Any relay is a server to
    many clients; any relay is a client of many servers; a relay can be
    both server and client at the same time.

    From the point of view of any individual Relay, there are two kinds
    of connections: connections we initiated, and connections we
    accepted.  Those that we initiate, we consider to be "above" us.  The
    ones we have accepted are "below" us.  The routing rules use these
    concepts to specify how packets are handled.

    A Relay has a default packet-protocol format, which can be changed to
    any one of several built-in formats.  Custom formatting routines can
    also be supplied for special or external network datagram formats.

    '''

    FREE = 0
    LINES = 1
    N8LEN = 2
    N16LEN = 3
    N32LEN = 4
    NVLEN = 5
    PICKLE = 6

    ABOVE = -1
    BELOW = -2

    class Conduit (SocketServer.BaseRequestHandler):
        '''Internal packet queuing and parsing management mechanism.'''
        #
        # Not a lot of doc-strings, as Conduit is meant for internal use.
        #
        # The python libs call it a 'request' but it's basically an open
        # socket session, from connection accepted to connection closed.
        #
        # This represents a handler for any socket session in a Relay,
        # providing the queuing of incoming raw data into application
        # packets, and allowing multiple threads to post output packets
        # to send.
        #
        def setup(self):
            # Called once by our base class to perform configuration.
            self.server.relay.conduits[self] = self.client_address
            self.server.relay.addresses[self.client_address] = self
            self.mode(self.server.relay.packet)
            self.pending = threading.Event()
            self.since = time.time()
            self.queue = []
            self.data = ''
            self.icount = 0
            self.ocount = 0
            self.quit = False
        def __repr__(self):
            return '<Conduit:%r>' % (self.client_address,)
        def handle(self):
            # Called once by our base class to perform the whole life cycle
            # of the open socket session.  We make a separate thread for
            # our transmitting duties, so transmitting and receiving are
            # fully asynchronous.
            self.transmitting = threading.Thread(target=self.transmitting)
            self.transmitting.setDaemon(True)
            self.transmitting.start()
            self.receiving()
            self.shutdown()
        def mode(self, packet=None, parse=None, make=None):
            # Set up the available parsing options that can recognize
            # valid raw data as application packets.  An extension to
            # this class may replace or extend this parsing process.
            parsers = [ parse_free, parse_line, parse_n8len,
                        parse_n16len, parse_n32len, parse_nVlen,
                        parse_pickle ]
            makers = [ make_free, make_line, make_n8len,
                       make_n16len, make_n32len, make_nVlen,
                       make_pickle ]
            if parse is None and packet >= 0 and packet < len(parsers):
                parse = parsers[packet]
            if make is None and packet >= 0 and packet < len(makers):
                make = makers[packet]
            if parse: self.parse = parse
            if make: self.make = make
        def receiving(self):
            # Called by handle() in the main thread.
            # Whenever a chunk arrives, we see if that completes a packet.
            # Whenever a packet successfully parses, we view() it.
            talk = self.request
            while not self.quit:
                chunk = talk.recv(4096)
                # r = repr(chunk)
                # if len(r) > 20: r = r[:17] + '...' + r[-1:]
                if len(chunk) == 0:
                    break
                self.data += chunk
                try:
                    (packet, self.data) = self.parse(self.data)
                    while packet is not None:
                        self.view(packet)
                        (packet, self.data) = self.parse(self.data)
                except:
                    address = self.client_address
                    _LOG.error('Malformed packet from %s:%d' % address)
                    _LOG.trace()
                    self.shutdown()
        def transmitting(self):
            # Called by handle() as a separate thread.
            # We just watch our pending queue and send whatever is posted.
            talk = self.request
            while not self.quit:
                self.pending.wait()
                self.pending.clear()
                while self.queue:
                    packet = self.queue.pop(0)
                    try: talk.send(packet)
                    except: self.shutdown()
        def shutdown(self):
            # Orderly one-step shutdown including our transmit thread.
            self.quit = True
            try: self.request.close()
            except: pass
            self.pending.set()
            if self.client_address:
                address = self.client_address
                self.client_address = None
                self.server.relay.kill(self)
        def view(self, packet):
            # Called whenever we successfully parse raw data into a packet.
            r = repr(packet)
            if len(r) > 20: r = r[:17] + '...' + r[-1:]
            self.icount += 1
            self.server.incoming.append( (self.client_address, packet) )
            self.server.pending.set()
        def stats(self):
            # Some debugging or status information formatted for display.
            life = time.time() - self.since
            text = 'i=%d, o=%d, l=%.1fsec' % (self.icount, self.ocount, life)
            if life >= 1.0:
                text += ', r=%.1f/sec' % ((self.icount+self.ocount) / life)
            return text
        def post(self, packet):
            # Add a packet to be sent in turn.
            self.ocount += 1
            self.queue.append(self.make(packet))
            self.pending.set()

    class RelayServer (SocketServer.ThreadingTCPServer):
        '''Internal listening socket and thread mechanism.'''
        #
        # Not a lot of doc-strings, as RelayServer is meant for internal use.
        #
        # We add the concept of 'jilted' or banned addresses.  A Relay
        # can check the list of jilts to see whether a connection should
        # be accepted to form a new connection (a Conduit).
        #
        # We support logging of opened/closed connections.
        #
        allow_reuse_address = 1
        # The TCPServer should use socket.SO_REUSEADDR before bind().
        #
        def __init__(self, address, handler, relay):
            SocketServer.TCPServer.__init__(self, address, handler)
            self.daemon_threads = True
            self.relay = relay
            self.quit = False
            self.incoming = []
            self.outgoing = []
            self.pending = threading.Event()
        def server_close(self):
            self.quit = True
            SocketServer.ThreadingTCPServer.server_close(self)
        shutdown = server_close
        def get_request(self):
            # Retrieve the 'request' (the connect session, or Conduit).
            (request, address) = SocketServer.ThreadingTCPServer.get_request(self)
            return (request, address)
        def verify_request(self, request, address):
            # New request to connect. Check if we accept it.
            return self.relay.accept(address, self)
            #return True
        def finish_request(self, request, address):
            # Actually create the request Conduit. It self-attaches.
            handler = self.RequestHandlerClass(request, address, self)
        def handle_error(self, request, address):
            _LOG.error('Exception handling message from %s:%d' % address)
            _LOG.trace()
        def listening(self):
            # Our lifecycle is a simple loop to listen for new connections.
            while not self.quit:
                try: self.handle_request()
                except: pass
        def routing(self):
            while not self.quit:
                self.pending.wait()
                self.pending.clear()
                while self.incoming:
                    self.relay.route_incoming(self.incoming.pop(0))
                while self.outgoing:
                    self.relay.route_outgoing(self.outgoing.pop(0))

    # public methods of a Relay

    def __init__(self, host='localhost', port=4567,
                 packet=LINES, viewer=None):
        '''Construct a generic message relay node.

        The caller may provide a binding address or default to
        'localhost'.  The default port for relays is 4567, but any port
        number may be provided (ports under 1024 may need higher user
        privileges on some systems).

        The default style of packet passing is by lines (terminated with
        \r\n); other packet styles are freeform or python pickled
        objects.

        If a callable function is given, it will be called for each packet
        received.

            def viewer_callback(relay, from_address, message): pass

        The view() method can be overridden instead of supplying a
        callback function.
        '''
        self.address = (host, port)
        self.server = Relay.RelayServer(self.address, Relay.Conduit, self)
        self.jilts = set([]) # 'hostname' we do not accept contact
        self.jiltseen = set([]) # temp 'hostname' we did not accept contact
        self.jiltmasks = set([]) # 'host*' masks we do not accept contact
        self.above = set([]) # (addr,port)
        self.below = set([]) # (addr,port)
        self.conduits = {} # conduit: (addr,port)
        self.addresses = {} # (addr,port): conduit
        self.packet = packet # initial assumed packet mode being received
        self.viewer = viewer # callback handler instead of override handler
        self.listening = threading.Thread(target=self.server.listening)
        self.listening.setDaemon(True)
        self.listening.start()
        self.routing = threading.Thread(target=self.server.routing)
        self.routing.setDaemon(True)
        self.routing.start()
        _LOG.info('Startup; now listening at %s:%d' % self.address)

    def shutdown(self):
        '''Disconnect from everything and terminate our threads.'''
        _LOG.info('Shutdown; not listening at %s:%d' % self.address)
        for conduit in self.conduits.keys():
            self.kill(conduit)
        if self.server:
            self.server.shutdown()
        _LOG.info('Shutdown; server stopped at %s:%d' % self.address)

    def find(self, target):
        '''Given an address or conduit, return a tuple with both.
        Given the constants ABOVE or BELOW, returns a list of tuples.
        '''
        if target is Relay.ABOVE:
            return [ self.find(each) for each in self.above ]
        if target is Relay.BELOW:
            return [ self.find(each) for each in self.below ]
        conduit = address = None
        if target in self.conduits:
            conduit = target
            address = self.conduits[conduit]
        if target in self.addresses:
            address = target
            conduit = self.addresses[address]
        for conduit in self.conduits:
            if conduit.request is target:
                return (conduit, conduit.client_address)
        return (conduit, address)

    def route_incoming(self, envelope):
        '''The incoming envelope shows the conduit delivering a message.'''
        (source, message) = envelope
        self.view(source, message)

    def route_outgoing(self, envelope):
        '''Outgoing messages must be propagated.'''
        (targets, message) = envelope
        if isinstance(targets, list):
            for target in targets:
                (conduit, address) = self.find(target)
                if conduit: conduit.post(message)
            return
        (conduit, address) = self.find(targets)
        if conduit: conduit.post(message)

    def jilted(self, address):
        '''Returns True if calls from the address should not be accepted.'''
        if isinstance(address, tuple):
            address = address[0]
        if address in self.jilts or address in self.jiltseen:
            return True
        for mask in self.jiltmasks:
            if _mask_match(address, mask):
                self.jiltseen.add(address)
                return True
        return False

    def jilt(self, address):
        '''Add a new hostname or hostmask to refuse all incoming contact.

        Hostnames can be specific DNS or IPv4/IPv6 addresses.  Hostmasks
        can use '*' wildcards as well.
        '''
        if isinstance(address, tuple):
            address = address[0]
        if '*' in address:
            self.jiltmasks.add(address)
        else:
            self.jilts.add(address)

    def unjilt(self, address):
        '''Remove a hostname or hostmask from the set of jilted addresses.'''
        if isinstance(address, tuple):
            address = address[0]
        if address in self.jilts: self.jilts.remove(address)
        if address in self.jiltseen: self.jiltseen.remove(address)
        for mask in self.jiltmasks.keys():
            within = mask.replace('*', '#')
            if _mask_match(within, address):
                self.jiltmasks.remove(mask)

    def accept(self, address, conduit):
        '''Check if an address is jilted, or accept the new connection.'''
        if self.jilted(address):
            _LOG.warning('Connection refused from %s:%d' % address)
            return False
        _LOG.info('Connection accepted from %s:%d' % address)
        self.below.add(address)
        return True

    def hangup(self, address, conduit):
        '''Finish anything before a connection is removed.
        Note that the remote side may have already hung up.
        '''
        if self.server and self.server.outgoing:
            _LOG.info('%d undelivered packets for %s:%d' %
                      (len(self.server.outgoing), address[0], address[1]))
        _LOG.info('Connection hanging up from %s:%d' % address)

    def kill(self, conduit):
        '''If the address is connected, disconnect immediately.'''
        if not conduit in self.conduits:
            return
        address = self.conduits[conduit]
        self.hangup(address, conduit)
        del self.conduits[conduit]
        del self.addresses[address]
        if address in self.above: self.above.remove(address)
        if address in self.below: self.below.remove(address)
        _LOG.info('Disconnecting %s:%d (%s)' % (address[0], address[1],
                                               conduit.stats()))
        conduit.shutdown()

    def call(self, address, packet=None):
        '''Initiate contact with a higher Relay or another plain socket.

        The first argument is an address tuple of the following form:

            ('hostname', port)

        The second argument is optional, and will set the packet
        forming/parsing mode for the created conduit.
        '''
        (conduit, addressed) = self.find(address)
        if conduit:
            self.kill(conduit)
        if packet is None:
            packet = self.packet
        _LOG.info('Calling %s:%d...' % address)
        talk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        talk.connect(address)
        self.above.add(address)
        self.server.process_request(talk, address)
        _LOG.info('Contacted peer at %s:%d' % address)
        #HACK: need time to settle the connection before pounding on it
        #      especially if calling a listener on the same machine
        time.sleep(0.25)

    def mode(self, target=None, packet=None, parse=None, make=None):
        '''Adjust the packet parsing and/or making mode.

        The first argument is either a conduit or an address tuple.  To
        apply the same packet mode to all currently connected conduits,
        supply target=None.
        
        Packet modes may be any of the existing values:
            FREE, LINES, N8LEN, N16LEN, N32LEN, NVLEN, PICKLE
            
        A custom packet parsing routine can be supplied with parse=P.
        The def P(data) should take one datastring argument, and return a
        two-element tuple (deserialized_value, remainder_of_datastring).
        If the datastring does not contain enough data to deserialize a
        value, return (None, whole_unmodified_datastring).

        A custom packet making routine can be supplied with make=M.  The
        def M(value) should take one value argument, and return the
        serialized datastring that can be parsed by the remote system.
        '''
        if target is None:
            for conduit in self.conduits:
                if not conduit: break
                self.mode(target=conduit, packet=packet,
                          parse=parse, make=make)
        (conduit, address) = self.find(target)
        if conduit:
            conduit.mode(packet=packet, parse=parse, make=make)

    def push(self, message):
        '''Accepts a new pending incoming message.
        Usually, incoming messages come from various network connections.
        Some applications may want to fabricate new messages and queue
        them up following any existing incoming messages.  This method
        adds a message to the queue, with our own address as the source.
        '''
        self.server.incoming.append( (self.address, message) )

    def post(self, targets, message):
        '''Accepts a new pending outgoing message.

        The first argument is a single target which must already have
        been connected.  This can be a conduit or an address tuple.
        Alternatively, this argument can be a list of valid targets.
        Each target will receive an identical copy of the message.
        The constants ABOVE and BELOW refer to all currently connected
        conduits to above or below relays.

        The second argument is the actual data to be made into a data
        packet using the currently selected packet making routine.
        '''
        targets = self.find(targets)
        _LOG.debug('Posting to %r: %r' % (targets, message))
        self.server.outgoing.append( (targets, message) )
        self.server.pending.set()

    def view(self, source, message):
        '''Called when receiving each incoming message.

        This method is overridable.  For many Relay-based applications,
        this may be the only method you need to override.  Alternatively,
        supply a viewer callback function to the constructor; the default
        behavior calls that function if supplied.

        The "source" argument refers to which conduit of this Relay
        delivered the message.  You can reply to the same conduit by
        using that source value as the target in the post() method.  For
        example, a simple echo server would implement a view like this:

            def view(self, source, message):
                self.post(source, message)
        
        The "message" argument is the actual contents of the message.  It
        is the result returned from the selected packet parsing routine,
        so there is no need to manage or understand many underlying
        protocol details.

        Any other tracking information or meta-routing data is not
        supported by Relay itself, and must be encapsulated within the
        message.
        '''
        if source == self.address:
            _LOG.debug('Message from %r [ourself]: %r' % (source, message))
        else:
            _LOG.debug('Message from %r: %r' % (source, message))
        if callable(self.viewer):
            (self.viewer)(self, source, message)
        pass

#----------------------------------------------------------------------------

def parse_free(data):
    '''Passes all available data as a single packet.'''
    return (data, '')

def parse_line(data):
    r'''Parses normal ASCII/UTF-8 lines with terminating CRLF ('\r\n').
    Any embedded extra solitary CR or LF characters are ignored and
    passed as part of the packet.
    '''
    term = '\r\n'
    packet = data.find(term)
    if packet < 0:
        return (None, data)
    packet += len(term)
    return (data[:packet], data[packet:])

def parse_n8len(data):
    '''Parses data packets preceded by 8-bit unsigned packet size.'''
    if len(data) < 1: return (None, data)
    packet = ord(data[0]) + 1
    if len(data) < packet: return (None, data)
    return (data[1:packet], data[packet:])

def parse_n16len(data):
    '''Parses data packets preceded by 16-bit big-endian packet size.'''
    if len(data) < 2: return (None, data)
    packet = struct.unpack('!H', data)[0] + 2
    if len(data) < packet: return (None, data)
    return (data[2:packet], data[packet:])

def parse_n32len(data):
    '''Parses data packets preceded by 32-bit big-endian packet size.'''
    if len(data) < 4: return (None, data)
    packet = struct.unpack('!L', data)[0] + 4
    if len(data) < packet: return (None, data)
    return (data[4:packet], data[packet:])

def parse_nVlen(data):
    '''Parses data packets preceded by variable big-endian packet size.
    The packet size is broken into 7-bit pieces. The most-significant
    7-bits is put into the first byte, and the high bit is set if there
    are more bytes required to describe the packet size. This minimizes
    overhead of packet size descriptors while not limiting packet size.
    '''
    v = 1
    packet = 0
    while data and ord(data[0]) == 128:
        data = data[1:]
    while True:
        if len(data) < v: return (None, data)
        byte = ord(data[v-1])
        packet = (packet << 7) | (byte & 0x7F)
        if 0 == (byte & 0x80): break
        v += 1
        if v > 6: raise ValueError, 'packet length too long'
    packet += v
    if len(data) < packet: return (None, data)
    return (data[v:packet], data[packet:])

def parse_pickle(data):
    '''Parses data packets that were formed by python serialization into
    "pickle" datagrams.  This serialized data must be preceded by a
    variable size prefix such as that used by parse_nVlen(), so the
    caller does not work extra hard trying to parse incomplete pickle
    streams repeatedly.  Any pickle failure exceptions will be raised, or
    the reconstituted object will be returned as the packet.
    '''
    (blob, data) = parse_nVlen(data)
    if blob is None: return (None, data)
    packet = pickle.loads(blob)
    return (packet, data)

def make_free(packet):
    '''Makes a datagram directly from any data packet given.'''
    return packet

def make_line(packet):
    '''Makes a datagram from an ASCII/UTF-8 text line.
    Supplies a terminating CRLF ('\r\n') pair if none is given.
    Removes solitary CR characters and turns solitary LF into CRLF pairs.
    '''
    packet.replace('\r', '')
    packet.replace('\n', '\r\n')
    if not packet.endswith('\r\n'):
        packet += '\r\n'
    return packet

def make_n8len(packet):
    '''Makes a small datagram with an 8-bit unsigned packet size prefix.
    It is a ValueError if the packet is too long to fit in this prefix.
    '''
    if len(packet) > 0xFF: raise ValueError, 'packet length too long'
    return chr(len(packet)) + packet

def make_n16len(packet):
    '''Makes a medium datagram with a 16-bit unsigned packet size prefix.
    It is a ValueError if the packet is too long to fit in this prefix.
    '''
    if len(packet) > 0xFFFF: raise ValueError, 'packet length too long'
    v = struct.pack('!H', len(packet))
    return v + packet

def make_n32len(packet):
    '''Makes a large datagram with a 32-bit unsigned packet size prefix.
    It is a ValueError if the packet is too long to fit in this prefix.
    '''
    if len(packet) > 0xFFFFFFFF: raise ValueError, 'packet length too long'
    v = struct.pack('!L', len(packet))
    return v + packet

def make_nVlen(packet):
    '''Makes a datagram with a variable packet size prefix.
    It is a ValueError if the packet is too long to fit in this prefix.
    '''
    v = ''
    n = len(packet)
    while True:
        byte = n & 0x7F
        if v != '':
            byte |= 0x80
        v = struct.pack('@B', byte) + v
        n = n >> 7
        if not n:
            break
    return v + packet

def make_pickle(packet):
    '''Makes a datagram that encapsulates a python serialization (or
    "pickle") of an arbitrary object.  The remote system would have to
    have access to the identical definitions of any classes and datatypes
    used in the pickle.  To simplify the parsing side, the serialized
    data is then prefixed with length information, using the make_nVlen()
    function.
    '''
    blob = pickle.dumps(packet)
    return make_nVlen(blob)

#----------------------------------------------------------------------------

def _trace():
    text = traceback.format_exception(sys.exc_type,
                                      sys.exc_value,
                                      sys.exc_traceback)
    text = ''.join(text)
    text = text.split('\n')
    if not text[-1]: text.pop()
    _LOG.debug(('\n' + ' '*28 + '| ').join(text))

if True:
    _LOG = logging.getLogger('Relay')
    _LOG.trace = _trace
    _format = '(%(levelname).1s) %(asctime)-15s | %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=_format)

def _mask_match(name, mask):
    # hostname string falls within hostmask
    name = name.replace('.', ':')
    mask = mask.replace('.', ':').replace('*', '.*') + r'\Z'
    if re.match(mask, name):
        return True
    return False

#----------------------------------------------------------------------------

def _test_nVlen():
    for n in (0, 1, 2, 3, 6, 124, 125, 126, 127, 128, 129, 250, 1250, 3650):
        sent = 'broadcast' * ((n / 8)+1)
        sent = sent[:n]
        assert len(sent) == n
        #
        p = make_nVlen(sent)
        (d,r) = parse_nVlen(p)
        assert len(d) == len(sent)
        assert d == sent
        assert r == ''
        #
        p = make_nVlen(sent) + 'junk'
        (d,r) = parse_nVlen(p)
        assert len(d) == len(sent)
        assert d == sent
        assert r == 'junk'

def _test_crashing_parse_line(data):
    packet = data.find('\r\n')
    if packet < 0:
        return (None, data)
    if '1' in data: raise ValueError, 'boom'
    packet += len('\r\n')
    (packet, data) = (data[:packet], data[packet:])
    return (packet, data)

def _test_socket_to_relay():
    r = Relay(port=5500)
    #
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', 5500))
    s.send('Hello, World\r\n')
    s.send('Blah blah.\r\n')
    #
    time.sleep(0.5)
    s.close()
    time.sleep(0.5)
    #
    r.shutdown()

class _socker (threading.Thread):
    def __init__(self, address, breadth=3):
        threading.Thread.__init__(self)
        self.address = address
        self.breadth = breadth
        self.setDaemon(True)
    def run(self):
        import random
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.address)
        for i in range(self.breadth):
            try: s.send('i=%d\r\n' % i)
            except: pass
            time.sleep(0.1 + random.random() * 0.3)
        while True:
            try: chunk = s.recv(1024)
            except: chunk = ''
            if len(chunk) == 0:
                break
            _LOG.debug(repr(chunk))
        s.close()

def _test_multi_socket_to_relay():
    r = Relay(port=4400)
    #
    width = 3
    breadth = 3
    for i in range(width):
        s = _socker( ('localhost', 4400), breadth )
        s.start()
    #
    time.sleep(width)
    r.shutdown()

def _test_relay_to_relay():
    r = Relay(port=6600)
    t = Relay(port=7700)
    time.sleep(0.1)
    #
    a = ('localhost', 7700)
    r.call( a )
    #time.sleep(0.5)
    #
    r.post( a, 'Hello, World\r\n' )
    time.sleep(0.5)
    #
    r.post( a, 'Blah blah blah\r\n' )
    time.sleep(0.5)
    #
    r.post( a, 'Goodbye, Cruel World\r\n' )
    time.sleep(0.5)
    #
    time.sleep(2)
    r.kill( a )
    time.sleep(0.5)
    #
    r.shutdown()
    t.shutdown()

_complete = 0
def _test_relay_queueing():
    #
    def _account(relay, source, message):
        global _complete
        _complete += 1
    #
    r = Relay(port=6600, viewer=_account)
    t = Relay(port=7700, viewer=_account)
    time.sleep(0.1)
    #
    a = ('localhost', 7700)
    b = ('localhost', 6600)
    r.call( a )
    time.sleep(0.5)
    #
    count = 20
    for i in range(count):
        r.post( a, 'r -> t %d\r\n' % i )
        t.post( b, 't -> r %d\r\n' % i )
    #
    started = time.time()
    while _complete < (count*2) and time.time() < started+10.0:
        time.sleep(0.1)
    complete = _complete
    remaining = (count*2) - complete
    print "Slept for %.1fsec to catch up." % (time.time() - started)
    print "Accounted for %d packets sent and received." % complete
    if remaining:
        print "Disconnecting with %d still pending in queues." % remaining
    #
    r.kill( a )
    time.sleep(0.5)
    #
    r.shutdown()
    t.shutdown()

def _test_pickle_relays():
    r = Relay(port=6600, packet=Relay.PICKLE)
    t = Relay(port=7700, packet=Relay.PICKLE)
    time.sleep(0.1)
    #
    a = ('localhost', 7700)
    r.call( a )
    time.sleep(0.5)
    # pickle a set as a packet
    r.post( a, set( [ 1, 2, 3 ] ) )
    time.sleep(0.5)
    # pickle a dict as a packet
    r.post( a, { 'a': 'alpha', 'b': 'baker' } )
    time.sleep(0.5)
    # define some new pickle-able class (must be in global() table)
    class _TEST (object):
        def __init__(self, v):
            self.v = v
        def __repr__(self):
            return '_TEST(%d)' % self.v
    globals()['_TEST'] = locals()['_TEST']
    # pickle an object as a packet
    r.post( a, _TEST(5) )
    time.sleep(0.5)
    #
    time.sleep(2)
    r.kill( a )
    time.sleep(0.5)
    #
    r.shutdown()
    t.shutdown()

if __name__ == '__main__':

    _LOG.debug('Testing the relays module. May take a few moments.')
    for test in [ _test_nVlen,
                  _test_socket_to_relay,
                  _test_multi_socket_to_relay,
                  _test_relay_to_relay,
                  _test_relay_queueing,
                  _test_pickle_relays,
                  ]:
        _LOG.debug('-'*40)
        test()
