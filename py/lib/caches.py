# caches - a simple and generic abstract cache class

'''

A simple and generic abstract cache class.

SYNOPSIS

    import caches
    class MyCache (caches.Cache):
        def loadPayload(self, address, context):
            payload = make_a_payload_from_address_or_context(...)
            return payload

    capacity = 15
    mycache = MyCache(capacity)
    while (True):
        payload = c.fetch( pick_some_useful_address() )

AUTHOR

    Ed Halley (ed@halley.cc) 17 March 2007

'''

#----------------------------------------------------------------------------

class CacheError (Exception): pass

class Cache:

    '''

    A simple and generic abstract cache class.

    Summary

        In short, a cache is like a read-only dict data structure, where
        the keys are called 'addresses' and the values are called
        'payloads.'  However, unlike a regular dict, a cache has a
        predetermined capacity and will automatically dismiss or unload
        some payload values to fit that capacity.

        * payload = mycache[address]

        * payload = mycache.fetch(address)

        A cache is usually used to manage the trade-off between memory
        consumption versus access speed.  The cache speeds access to
        frequently-used items without requiring all possible addressable
        items to remain in memory at all times.

        Whenever capacity is full, some older items are purged from memory
        on the assumption that with a little work they can be recreated
        or reloaded from storage if needed again.  The freed capacity is
        then used to keep more recent items for ready access.

    Addresses and Payloads

        The cache translates addresses to payloads.  Both are completely
        up to the application to define their data types and
        capabilities, but each have certain rules.

        * An address cannot be None.

        * A payload object cannot be None.

        * All addresses uniquely identify one payload object.

        * For any given address, a function can reload, calculate, or
          otherwise construct the appropriate payload object from
          scratch.

        * Your class provides that function, overriding loadPayload().

        This Cache class is abstract; it is not usable as-is.  Instead,
        base your own class on Cache, and then override at least one
        function to make it load payload objects on command.  See
        loadPayload().

        Once constructed, the cache will return the same instance of the
        payload every time it is requested through the fetch() routine,
        until it is freed from the cache.  After being freed, a new copy
        will be constructed the next time that address is fetched.

    Contexts for Metadata

        As a convenience and a cost-estimating feature, this cache type
        offers an optional middle ground between the very simple address
        and the potentially costly or heavy payload data types.  This is
        called a context.

        A cache context is any intermediate data value which is quick to
        load or calculate, and which can be preloaded for every possible
        address to enhance the cache's ability to load or cost-estimate
        the actual payload objects.

        For example, an image thumbnailing program might refer to the
        image filename as an address, some image cost-estimating facts
        like pixel dimensions and byte counts in a context object, and
        the actual pixel and byte data in the payload.

    Planning for Capacity

        Loading each payload has a certain cost associated with it.  The
        cache itself will try not to exceed a certain total cost for all
        payload objects that are active simultaneously.

        For a simple cache, it may be sufficient to count the number of
        payloads loaded, and not exceeding a certain count.  This is the
        default cost structure if your class does not provide any new
        costing routines.

        * cost = mycache.costAddress(address, context) +
                 mycache.costPayload(address, payload)

        For a more complicated cache, there is a choice between costs
        calculated BEFORE loading and costs that can only be calculated
        AFTER loading the payload object.  If you can pre-determine all
        of your payload costs given just an address or a context object,
        then override cache.costAddress() and return a positive number.
        If you must load the payload before a cost is known, then
        override cache.costPayload() and return a positive number.  You
        can return zero from either of these routines, or non-zero from
        both, but the sum of both routines must be a positive cost value.

        For pre-loading costs (from costAddress()), the cache will free
        up old payloads until the new object can fit within the cache's
        capacity value.

        For post-loading costs (from costPayload()), the cache will allow
        one fetch beyond the rated capacity.  This is because the cache
        cannot know how much to free beforehand to ensure it does not
        exceed the capacity.  If it is vital not to exceed the capacity,
        then use the context facility to calculate accurate costs before
        loading whole payload objects.

    Exceptions

        For the following reasons, a CacheError will be raised.  The
        message included in each error is generally self-explanatory.

        * It's an error to have an address cost that exceeds the whole
          cache capacity.  Review the range of costs you return from
          costAddress() override, and create caches that have at least
          this much capacity.

        * It's an error to have zero or negative total cost for a
          payload.  The sum of costAddress() and costPayload() must be
          a positive number.  It is okay to have a zero cost from one
          or the other, but not from both.

        * If the cache is marked as being definitive, then it's an error
          to fetch from an address which was never added via
          addAddress().  Your override of loadSpace() will be called
          once, and this is an opportunity to call addAddress() for all
          possible addresses.  The default cache is not definitive,
          allowing for unpredicted addresses.

        * When the cache must flush out payloads, it double-checks the
          costs; if there is an unexpected change in loading costs, a
          CacheError is raised.

    '''

    def __init__(self, capacity=10):
        '''Construct a cache of a given fetch-cost capacity.'''
        self.realized = False
        self.definitive = False  # if unknown addresses are illegal to fetch
        self.capacity = capacity
        self.utilized = 0
        self.facts = { }   # all possible addresses -> context or None
        self.known = { }   # all possible addresses -> payload or None
        self.alive = { }   # just addresses loaded in memory -> last fetched
        self.fetches = 0
        self.hits = 0
        self.misses = 0
        self.loads = 0
        self.unloads = 0

    def setCapacity(self, capacity):
        '''Assign a new capacity to the cache.'''
        self.capacity = capacity
        self.reduce(capacity)

    def setDefinitive(self, definitive=True):
        '''Mark if the set of all valid addresses is definitively known.'''
        self.definitive = definitive
        self.realize()

    def loadPayload(self, address, context):
        '''Override this function in your own Cache-derived class.
        This is the only REQUIRED override to make a functional cache.

        From a given address value and/or its associated context value,
        this routine should load, calculate, or build the appropriate
        payload value.
    
        The payload returned can be any value except None.
        '''
        return None

    def loadContext(self, address):
        '''Override this. From an address, load or build a context object.'''
        return None

    def costAddress(self, address, context):
        '''Override this. Return the cost known before loading a payload.'''
        return 1

    def costPayload(self, address, payload):
        '''Override this. Return the cost known after loading a payload.'''
        return 0

    def unloadPayload(self, address, payload):
        '''Override this. Free up, finalize, save, close a payload.'''
        return None

    def loadSpace(self):
        '''Override this. Return all possible legal addresses as a list.'''
        return None

    def realize(self):
        '''Ensure the cache is ready to start fetching from legal addresses.'''
        if self.realized: return
        self.realized = True
        if not self.known:
            knowns = self.loadSpace()
            if isinstance(knowns, list):
                for each in knowns:
                    self.known[each] = None

    def addAddress(self, address):
        '''User can add new known addresses in ad-hoc order with this.'''
        self.realize()
        if not address in self.facts:
            self.facts[address] = self.loadContext(address)
        if not address in self.known:
            self.known[address] = None

    def getContext(self, address):
        '''Retrieve the metadata for a given address, if any.'''
        if not address in self.facts:
            self.facts[address] = self.loadContext(address)
        return self.facts[address]

    def fetched(self, address):
        '''Check if a given address is already fetched into the cache.'''
        if address in self.alive:
            return True
        return False

    def reduce(self, utilization):
        '''Flush enough items to ensure a given utilization maximum.'''
        if utilization > self.capacity:
            utilization = self.capacity
        while self.utilized > utilization:
            current = self.utilized
            address = self.flush()
            if self.utilized >= current:
                raise Exception( "Unloading %s didn't reduce cache size." %
                                 repr(address) )

    def flush(self, address=None):
        '''Find and unload one payload from cache.
        If an address is not given, try the least-recently fetched.
        Once flushed, fetching the same address will require loading.
        '''
        if not self.alive:
            return None
        # flush the oldest alive if not specified
        if address is None:
            addresses = list(self.alive.keys())
            addresses.sort(key=lambda i: self.alive[i])
            address = addresses[0]
        payload = self.known[address]
        if not address in self.facts:
            self.facts[address] = self.loadContext(address)
        context = self.facts[address]
        cost = ( self.costAddress(address, context) +
                 self.costPayload(address, payload) )
        if cost <= 0:
            raise Exception( "Total cost of %s cannot be negative or zero." %
                             repr(address) )
        self.utilized -= cost
        self.unloadPayload(address, payload)
        self.known[address] = None
        del self.alive[address]
        self.unloads += 1
        return address

    def fetch(self, address):
        '''Find (and load if necessary) a payload into the cache.'''
        self.realize()
        # address not previously known? allow or disallow
        if not address in self.known:
            if self.definitive:
                raise Exception( "Address %s is definitively not valid." %
                                 repr(address) )
            self.addAddress(address)
        # legal address, so let's see if we already have it in cache
        self.fetches += 1
        if address in self.alive:
            self.hits += 1
            self.alive[address] = self.fetches
            return self.known[address]
        # we now know it's a cache miss
        self.misses += 1
        # figure out the address cost of loading this one
        if not address in self.facts:
            self.facts[address] = self.loadContext(address)
        context = self.facts[address]
        cost = self.costAddress(address, context)
        # free up enough payloads to fit at least our address cost
        if cost > self.capacity:
            raise Exception( "Payload at %s would exceed capacity alone." %
                             repr(address) )
        self.reduce(self.capacity - cost)
        # we can now load the payload
        payload = self.loadPayload(address, context)
        if payload is None:
            raise Exception( "Address %s failed to load payload into cache." %
                             repr(address) )
        self.loads += 1
        # actual cost is address cost plus payload cost, okay to exceed capacity
        cost += self.costPayload(address, payload)
        if cost <= 0:
            self.unloadPayload(address, payload)
            raise Exception( "Total cost of %s cannot be negative or zero." %
                             repr(address) )
        # finally attach the payload to the cache
        self.alive[address] = self.fetches
        self.known[address] = payload
        self.utilized += cost
        return payload

    def __contains__(self, address):
        '''Operator 'in' overloaded; equivalent to calling cache.fetched().'''
        return self.fetched(address)

    def __getitem__(self, key):
        '''Operator cache[key] overloaded as equivalent to calling fetch().'''
        return self.fetch(key)

    def clear(self):
        '''Flush all loaded payloads from the cache.'''
        loaded = list(self.alive.keys())
        for each in loaded:
            self.flush(each)
        if self.alive:
            raise Exception("Emptying the cache did not unload all payloads.")
        if self.utilized != 0:
            raise Exception("Unloading everything did not go to zero cost.")
        self.reset()

    def reset(self):
        '''Reset the cache performance statistics.'''
        self.hits = 0
        self.misses = 0
        self.loads = 0
        self.unloads = 0

    def performance(self):
        '''Return a tuple of cache performance data:
        (utilization, hits, misses, performance)
        '''
        performed = 0.0
        if self.hits+self.misses != 0:
            performed = self.hits / float(self.hits+self.misses)
        return (self.utilized, self.hits, self.misses, performed)

    def choice(self, loaded=False):
        '''Return a known address at random.
        If loaded=True, only considers payloads already loaded.
        Otherwise, it may return a known address that is not loaded.
        '''
        import random
        if not self.known: return None
        if loaded: return random.choice( self.alive.keys() )
        return random.choice( self.known.keys() )

#----------------------------------------------------------------------------

# Run the module directly for a demonstration or self-test.

if __name__ == '__main__':

    import pprint

    data = { 'one':   [1],
             'two':   [2,2],
             # 'three': [3,3,3], # special ad-hoc case added later
             'four':  [4,4,4,4],
             'five':  [5,5,5,5,5],
             'six':   [6,6,6,6,6, 6],
             'seven': [7,7,7,7,7, 7,7],
             'eight': [8,8,8,8,8, 8,8,8],
             'nine':  [9,9,9,9,9, 9,9,9,9],
             'ten':   [10,10,10,10,10, 10,10,10,10,10] }

    class MyCache (Cache):
        def loadContext(self, address):
            # here, we give the first element in the data as a context
            # this is enough to figure storage costs without the whole payload
            return data[address][0]
        def loadPayload(self, address, context):
            # this example needs the address, but it could use the context
            return data[address]
        def costAddress(self, address, context):
            # we can fit only a number of elements; bigger payloads cost more
            return context
        def costPayload(self, address, payload):
            # we don't compute a cost on the payload once it's loaded
            return 0
        def unloadPayload(self, address, payload):
            # regular garbage collection is enough
            return None
        def loadSpace(self):
            # optional, but if we know most addresses already, useful
            return data.keys()

    capacity = 15

    c = MyCache(capacity)
    if c.utilized != 0: raise Exception()

    o2 = c.fetch('two')
    if c.utilized != 2: raise Exception()

    data['three'] = [3,3,3]
    c.addAddress('three') # added after loadSpace() found the rest

    o6 = c['six']
    if 'nonsense' in c: raise Exception()
    if not 'six' in c: raise Exception()
    if c.utilized != 2+6: raise Exception()
    
    o8 = c.fetch('eight') # should flush lru item 'two'
    if c.fetched('two'): raise Exception()
    if not c.fetched('six'): raise Exception()
    if not c.fetched('eight'): raise Exception()
    if c.utilized != 2+6+8-2: raise Exception()
    
    o2 = c.fetch('two') # should flush lru item 'six'
    o3 = c.fetch('three') # should not need to flush anything
    if not c.fetched('two'): raise Exception()
    if not c.fetched('three'): raise Exception()
    if c.fetched('six'): raise Exception()
    if not c.fetched('eight'): raise Exception()
    if c.utilized != 2+6+8-2-6+2+3: raise Exception()

    o2_again = c['two']
    if o2 is not o2_again: raise Exception()

    p = c.performance()
    if p[0] != 13: raise Exception()
    if p[1] != 1: raise Exception()
    if p[2] != 5: raise Exception()
    c.reset()
    p = c.performance()
    if p[0] != 13: raise Exception()
    if p[1] != 0: raise Exception()
    if p[2] != 0: raise Exception()
    if p[3] != 0.0: raise Exception()
    c.clear()
    p = c.performance()
    if p[0] != 0: raise Exception()

    print('caches.py: all internal tests on this module passed.')
