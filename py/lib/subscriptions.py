# subscriptions - a multiple-subscriber queue, each subscriber gets each item

'''

A multiple-subscriber queue, where each subscriber gets each item.

ABSTRACT

    A subscription is an orderly developed series of information, which may
    be observed by multiple subscribers concurrently.  Each observer sees
    the same series in the same order, but may read at their own rate.
    Issues published onto the subscription are only removed from memory
    when all known subscribers have received their copies.

AUTHOR

    Ed Halley (ed@halley.cc) 21 March 2007

'''

#----------------------------------------------------------------------------

class Subscription (object):

    '''A subscription is a queue that supports multiple subscribers, each
    of which sees all issues in the queue.  Each subscriber should
    register themselves with an arbitrary unique key; an issue is only
    freed when it has been received by all registered subscribers.
    Publishers need not be registered.
    '''

    def __init__(self, copier=None, archival=False):
        '''Sets up an empty queue for publishing and subscribing.

        If the issues (values being published) are mutable objects,
        a callable can be given to clone all issues as they're retrieved.
        Otherwise, issues may be modified by one subscriber, affecting all
        of the other subscribers that receive the same issue.

        If the subscribers may be added after the first issue, but they
        should receive all issues starting with the first one, then an
        archival flag can be set to True; this can significantly add to
        memory consumption for queues with many issues over its lifetime.
        This allows a new producer to begin publishing immediately, while
        other threads add subscribers later.  Calling the prune() method
        with a flush=True can dismiss these archived-but-never-recieved
        issues later.
        '''
        self.subscribers = { }
        self.issues = [ ]
        self.copier = copier
        if archival:
            self.register(self)

    def __repr__(self):
        '''Gives a compact readable state summary of the subscription.'''
        me = self.__class__.__name__ + '():'
        me += '\n\t.length = %d' % len(self.issues)
        if len(self.issues) > 2:
            me += '\n\t.issues[0] = %s' % repr(self.issues[0])
            me += '\n\t          :'
            me += '\n\t         [%d] = %s' % (len(self.issues)-1,
                                             repr(self.issues[-1]))
        else:
            for each in range(len(self.issues)):
                me += '\n\t.issues[%d] = %s' % (each,
                                                  repr(self.issues[each]))
        if len(self.subscribers):
            me += '\n\t.subscribers = %s' % repr(self.subscribers)
        return me

    def register(self, subscriber):
        '''Items are received only by registered subscribers.
        A subscriber can be any kind of token or object that is hashable.
        '''
        if not subscriber in self.subscribers:
            self.subscribers[subscriber] = len(self.issues)

    def registered(self, subscriber):
        '''Checks if a subscriber name has been registered.'''
        return subscriber in self.subscribers

    def unregister(self, subscriber):
        '''Removes a given subscriber name from the registry.'''
        if subscriber in self.subscribers:
            del self.subscribers[subscriber]

    def reproduce(self, issue):
        '''Makes shallow or deep copies of received issues as required.'''
        if callable(self.copier):
            issue = self.copier(issue)
        return issue

    def ready(self, subscriber, count=1):
        '''Checks if one or more items are ready to be received.'''
        self.register(subscriber)
        return len(self.issues) >= count + self.subscribers[subscriber]

    def peek(self, subscriber, count=1):
        '''Returns an item, without removing it from the queue.'''
        if not self.ready(subscriber, 1):
            return [ ]
        start = self.subscribers[subscriber]
        issues = [ self.reproduce(issue) for issue in
                   self.issues[start:start+count] ]
        return issues

    def receive(self, subscriber):
        '''Takes receipt of an item from the queue.
        This raises an error if the subscriber has no issues to receive.
        '''
        self.register(subscriber)
        issue = self.issues[self.subscribers[subscriber]]
        self.subscribers[subscriber] += 1
        self.prune()
        return self.reproduce(issue)

    def prune(self, flush=False):
        '''Trims past issues that have been received by all subscribers.
        If the flush flag is True, then any old archival issues are
        eligible for trimming; future subscribers will not receive them.
        '''
        if flush:
            self.unregister(self)
        low = min(self.subscribers.values())
        if low > 0:
            del self.issues[0:low]
            for each in self.subscribers:
                self.subscribers[each] -= low

    def publish(self, issue):
        '''Adds a new issue to the tail of the queue.'''
        if self.subscribers:
            self.issues.append(issue)
        return issue

    def __len__(self):
        '''The len() of a subscription is the number of active issues.'''
        return self.issues.__len__()
    def __getitem__(self, item): return self.issues.__getitem__(item)
    def __setitem__(self, item, value):
        return self.issues.__setitem__(item, value)

    def append(self): raise NotImplementedError()
    def insert(self): raise NotImplementedError()
    def sort(self): raise NotImplementedError()
    def pop(self): raise NotImplementedError()

#----------------------------------------------------------------------------

if __name__ == "__main__":

    s = Subscription()

    c1 = 'subscriber1'
    s.register(c1)

    s.publish(1)

    c2 = 'subscriber2'
    s.register(c2)
    c3 = 'subscriber3'
    s.register(c3)

    s.publish(2)
    s.publish('C')
    s.publish(4.0)

    assert(s.receive(c1) == 1)
    assert(s.receive(c1) == 2)
    assert(s.receive(c1) == 'C')
    assert(s.receive(c1) == 4.0)

    assert(s.receive(c2) == 2)
    assert(s.receive(c2) == 'C')
    assert(s.ready(c2))

    assert(s.receive(c3) == 2)
    assert(s.receive(c3) == 'C')
    assert(s.receive(c3) == 4.0)

    assert len(s) == 1, 'only one issue should be undelivered'
    assert s.receive(c2) == 4.0
    assert len(s) == 0, 'all issues should be delivered by now'

    print('subscriptions.py: all internal tests on this module passed.')
