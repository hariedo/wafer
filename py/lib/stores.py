# persists - general storage-depot persistence helpers

'''

Some general storage-depot persistence helper classes.

ABSTRACT

    Builds on pickle, creating a depot or repository of uniquely
    identified persistent objects.  Each object has its own permanent
    unchanging identity with id(), and that identity is used in the
    filesystem or database as a key to retrieve it later.

    Two mix-in classes, Identified and Persistent, cooperate to give
    objects a permanent identity, and to interface with a data store.

    A generic class called Store gives simple memory-only data store; an
    extended version uses the filesystem to save individual objects in
    binary pickle files.  Making other extensions is very
    straightforward.

AUTHOR

    Ed Halley (ed@halley.cc) 12 December 2006

'''

__all__ = [ 'Identified', 'Persistent',
            'Store', 'FileStore', 'DbmStore',
            'fetch' ]

try: import cPickle as pickle
except: import pickle

import glob
import uuid
import dbm
import re
import os

#----------------------------------------------------------------------------

class Identified:
    """A mix-in class for anything needing a permanent unique identity.

       class MyClass (MyBaseClass, Identified):
           pass

       myobj = MyClass()
       print myobj.id()

    To give your MyClass instances a globally unique identity, add this
    class to your bases.  The instance will gain a method .id() to
    retrieve the unique identifier for the instance.  The identifier
    value itself resides in a private attribute ._id for serialization,
    which should not be modified by any application code.
    """

    def allocid(self):
        '''Compute a new identifier suitable for this object.
        Take special care that identifiers are unique for all objects
        in an application or persistent store, not just based on the
        state information within the object's current properties.
        The base version employs a general globally unique identifier
        routine; see module uuid for details.
        '''
        return str(uuid.uuid1())

    def id(self, assigned=None):
        '''Retrieve the unique identifier for this object.
        If given an identifier, this will be assigned to the object.
        This identifier must be unique to all objects existing within
        an application or persistent store.  The allocid() method is
        the recommended source of unique identifiers.  Once assigned,
        the identity should be permanent and never modified.
        '''
        if hasattr(self, '_id'):
            if assigned and self._id != assigned:
                raise KeyError('already has a different id')
        else:
            self._id = assigned or self.allocid()
        return self._id

#----------------------------------------------------------------------------

class Persistent:
    """A mix-in class for anything you need to persist in a data store.

       class MyClass (MyBaseClass, Persistent):
           pass

       s = Store()

       myobj = MyClass()
       s.add(myobj) # attaches to store

       myobj.commit()

    To manage your MyClass instances in a persistent store, add this
    class to your bases.  The instance will gain one method, .commit(),
    to attach the instance to the store and also flush any uncommitted
    modifications.  As a whole, your MyClass definition must be able to
    be serialized independently with the pickle module.  If your MyClass
    instances need references to other stored items, then use symbolic
    references instead (such as the .id() given by Identified).
    """

    def __schema__(self):
        pass

    def __default__(self, attr, val):
        if not hasattr(self, attr):
            setattr(self, attr, val)
        return getattr(self, attr)

    def store(self, name=None):
        '''Get a reference to the store that owns this object.
        If given a name, that store will be found if the object is not owned.
        '''
        store = getattr(self, '_store', name)
        store = Store.find(store)
        return store

    def commit(self, name=None):
        '''Ensures the current state is committed to persistent storage.'''
        store = self.store(name)
        store.commit(self)

    def release(self):
        store = self.store()
        store.release(self)

#----------------------------------------------------------------------------

class Store:
    """A system to manage any number of persistent, identified objects.

    The stored objects must include the Identified and Persistent bases.
    Using a Store is as follows.

        >>> store = Store()

        >>> x = MyClass()   # must support Identified and Persistent
        >>> id = store.add(x)

        >>> x = store.fetch(id)
        >>> x.mystate = something
        >>> store.flush(x)

        >>> store.close()

    The basic Store class provides a generic data store in memory only.
    See the FileStore class for a filesystem version that saves objects
    in pickle files, or DbmStore for a simple database version.

    Making a new Store type is very straightforward.  Overwrite some or
    all of these methods:

        startup(*args, **kwargs)
        exists(id)
        load(id)
        save(id, blob)
        kill(id)
        close()

    The startup() routine is only needed if the extended type requires
    any special configuration, like db connections or user credentials.
    It should return a list, set or tuple of all identifiers that exist
    in the store, or None if that list would be computationally expensive
    to compute.

    The exists() routine should return True if a given identifier is
    present in the database.  The load() routine should lookup and
    retrieve a binary blob given any identifier present in the store.
    Similarly, save() should write the given identifier and blob to the
    storage.  If kill() is called, then any existance of the identifier
    or its data must be erased.

    There are two major differences between the use of a data store and
    directly using a database such as the 'dbm/ndbm/anydbm' modules
    provide.  First, the Store uses live objects as values, instead of
    just exposing strings that you have to pickle yourself.  Second, the
    Store tries to ensure that your caller only has one instance of a
    given object at any time; you cannot get two instances for the same
    identifier, nor replace one object for another object using the wrong
    identifier.  Items in a Store know their own identity and work with
    the Store to achieve persistence.

    """

    _stores = { } # name : store

    @classmethod
    def find(cls, name):
        '''Try to find a Store instance given its assigned name.'''
        if isinstance(name, Store): return name
        if not name in Store._stores:
            return Store(name)
        return Store._stores[name]

    def __keyerror__(self, id):
        raise KeyError('Id %s not in store %s' % (id, self.name))

    def __collideerror__(self, id):
        raise KeyError('Id %s already in store %s' % (id, self.name))

    def __typeerror__(self, cls):
        raise TypeError('Stored objects must include %s base type.' % cls)
    
    def __foreignerror__(self, store):
        raise KeyError('Object already kept in store %s.' % store)

    def __init__(self, name=None, *args, **kwargs):
        '''Create and configure a Store instance.
        Generally, a Store has an application-defined name, which can be
        used with Store.find() to recall it later.  Persistent objects
        put into Stores know this name.  Any other arguments are specific
        to the type of Store, to configure various storage options.
        '''
        self._awake = { }
        if not name:
             name = 'Store' + str(len(Store._stores))
        self.name = name
        Store._stores[name] = self
        self.startup(*args, **kwargs)

    def startup(self, *args, **kwargs):
        '''Configure the Store instance.
        This is an overridable callback, for classes that extend or
        specialize the Store class.  The default version is suitable
        for memory-only storage.  Not intended to be called directly.
        Callers should pass configuration when creating a new Store.
        '''
        self._storage = { }
        return []

    def exists(self, id):
        '''Determine if an identifier exists in the store.
        This is an overridable callback, for classes that extend or
        specialize the Store class.  The default version is suitable
        for memory-only storage.  May be called directly.
        '''
        return id in self._storage

    def load(self, id):
        '''Retreive the binary data that represents a Persistent object.
        The binary data is usually a string as a result of pickling.
        This is an overridable callback, for classes that extend or
        specialize the Store class.  The default version is suitable
        for memory-only storage.  Not intended to be called directly.
        Callers should use fetch().
        '''
        if not id in self._storage: return None
        blob = self._storage[id]
        return blob

    def save(self, id, blob):
        '''Record the binary data that represents a Persistent object.
        The binary data is usually a string as a result of pickling.
        This is an overridable callback, for classes that extend or
        specialize the Store class.  The default version is suitable
        for memory-only storage.  Not intended to be called directly.
        Callers should use commit().
        '''
        self._storage[id] = blob
        return id

    def kill(self, id):
        '''Destroy the stored data that represents a Persistent object.
        The data should be erased, freed, culled, or reaped permanently.
        This is an overridable callback, for classes that extend or
        specialize the Store class.  The default version is suitable
        for memory-only storage.  Not intended to be called directly.
        Callers should use destroy().
        '''
        if id in self._awake:
            raise RuntimeError('Call destroy() instead.')
        self._storage.pop(id)

    def add(self, item):
        '''Adopt a given data object as owned by this Store.
        The object must inherit Identified and Persistent mixins classes.
        An object may only be owned by one Store.  It is an error to add
        the same object multiple times.
        '''
        if not isinstance(item, Identified):
            self.__typeerror__('Identified')
        if not isinstance(item, Persistent):
            self.__typeerror__('Persistent')
        store = getattr(item, '_store', None)
        if store and store != self.name:
            self.__foreignerror__(store)
        if store == self.name:
            if self.exists(id):
                self.__collideerror__(id)
        id = item.id()
        self._awake[id] = item
        item._store = self.name
        blob = self.serialize(item)
        self.save(id, blob)
        return id

    def destroy(self, id):
        '''Remove an object by its identifier from the Store.
        The object is no longer owned by the Store.  Any persistent
        storage is reclaimed or freed.  The object is not loaded into
        memory, and any existing references to the object or its
        identifier should be discarded by the caller.
        '''
        if isinstance(id, Identified):
            id = id.id()
        if not self.exists(id):
            self.__keyerror__(id)
        if id in self._awake:
            self._awake.pop(id)
        self.kill(id)

    def fetch(self, id):
        '''Retrieve an object by its identifier.
        If the same identifier is fetched by multiple callers, the same
        instance is returned for all of them.  (There must be only one
        instance of an Identified object at any given time.)
        '''
        if isinstance(id, Identified):
            id = id.id()
        if not self.exists(id):
            self.__keyerror__(id)
        if not id in self._awake:
            blob = self.load(id)
            if blob is None:
                self.__keyerror__(id)
            item = self.deserialize(blob)
            self._awake[id] = item
        return self._awake[id]

    def __contains__(self, id):
        "As a convenience, id in mystore refers to mystore.exists(id)."
        return self.exists(id)

    def __getitem__(self, id):
        "As a convenience, mystore[id] refers to mystore.fetch(id)."
        return self.fetch(id)

    def __setitem__(self, id, item):
        if id != item.id():
            raise KeyError('Identifier does not match item.')
        self.add(item)

    def serialize(self, item):
        '''Convert an identified object to its binary representation.
        The base version uses pickling on the object instance.
        '''
        if self.exists(item):
            item = self.fetch(item)
        blob = pickle.dumps(item)
        # See PicklingError exception notes below.
        return blob

    def deserialize(self, blob):
        '''Convert a binary data into an object instance.
        The base version assumes pickle loading will restore the object
        instance.  If the object has a __schema__() method, this is
        called after loading.  This is an opportunity to attempt object
        versioning corrections; the object may have been saved using a
        different version of its own implementation code.
        '''
        item = pickle.loads(blob)
        if hasattr(item, '__schema__'):
            item.__schema__()
        return item

    def release(self, id):
        '''Commit any changes to storage, and dismiss it from memory.'''
        if isinstance(id, Identified):
            id = id.id()
        self.commit(id)
        if id in self._awake:
            self._awake.pop(id)

    def commit(self, id=None):
        '''Ensure the current state of an object is recorded to storage.
        If no object identifier is given, commits all loaded objects.
        '''
        if id is None:
            for id in self._awake:
                self.commit(id)
            return
        if isinstance(id, Identified):
            id = id.id()
        if not self.exists(id):
            self.__keyerror__(id)
        blob = self.serialize(id)
        self.save(id, blob)
        return id

    def clone(self, id):
        '''Creates another object that is identical to one identified.
        The only difference in the new object is that it has a unique
        identifier.  Returns the new object.
        '''
        if isinstance(id, Identified):
            id = id.id()
        if not self.exists(id):
            self.__keyerror__(id)
        if id in self._awake:
            self.commit(id)
        blob = self.load(id)
        if blob is None:
            self.__keyerror__(id)
        other = self.deserialize(blob)
        other._id = other.allocid()
        self._awake[other._id] = other
        blob = self.serialize(other)
        self.save(other._id, blob)
        return other

    def close(self):
        '''Commits all changes and finalizes the store.
        This is an overridable callback, for classes that extend or
        specialize the Store class.  The default version is suitable
        for memory-only storage, or implementations needing no special
        disconnections.  May be called directly.
        '''
        self.commit()
        self._awake = { }

#
# Possible errors or exceptions raised:
#
# PicklingError: Can't pickle <class 'X'>: attribute lookup X failed
#   The above message may indicate X is not at top level of a module.
#   Can't embed a persistent class in a def or a class, for example.  The
#   workaround is to transfer the symbol in the local namespace into the
#   global namespace for the module attempting the serialization-- e.g.,
#   globals()['X'] = locals()['X'].
#

#----------------------------------------------------------------------------

class FileStore (Store):

    '''A specialized Store that records the state of any owned objects in
    independent files in the filesystem.  The files are named after their
    identifier, with a .blob extension.  The default location of the
    files is in a subdirectory below the current directory, according to
    the name of the store.

    A path= argument in the constructor will specify a different location
    for these files.  Future versions of this class may employ other
    files or directories inside the store's location.

    Larger data stores (more than a few hundred items) should probably be
    database, instead of the filesystem.  See the DbmStore class.
    '''

    def startup(self, *args, **kwargs):
        '''Supports path= to specify a location, otherwise assumes the
        current directory.  Appends the store name, and creates the
        directory if required.
        '''
        path = kwargs.get('path', '.')
        self._path = '%s/%s' % (path, self.name)
        if not os.path.exists(self._path):
            os.mkdir(self._path)
        files = glob.glob(self._path + '/*.blob')
        known = [ ]
        for file in files:
            m = re.search(r'/([^/.]+).blob\Z', file)
            if m: known.append(m.group(1))
        return known

    def path(self, id):
        '''Convert an identifier into a file path within the store.'''
        return '%s/%s.blob' % (self._path, id)

    def exists(self, id):
        # overridable callback for external storage
        return os.path.exists(self.path(id))

    def load(self, id):
        # overridable callback for external storage, do not call directly
        try:
            file = open(self.path(id), 'rb')
        except IOError:
            return None
        blob = file.read()
        file.close()
        return blob

    def save(self, id, blob):
        # overridable callback for external storage, do not call directly
        file = open(self.path(id), 'wb')
        file.write(blob)
        file.close()
        return id

    def kill(self, id):
        # overridable callback for external storage, do not call directly
        if id in self._awake:
            raise RuntimeError('Call destroy() instead.')
        path = self.path(id)
        if os.path.exists(path):
            os.unlink(path)

#----------------------------------------------------------------------------

class DbmStore (Store):

    '''A specialized Store that records the state of any owned objects in a
    database managed by a 'dbm'-like module.  The default location of the
    database files is the current directory, according to the name of the
    store.

    A path= argument in the constructor will specify a different location
    for these files.  Future versions of this class may employ other
    files or directories inside the store's location.
    '''

    def startup(self, *args, **kwargs):
        '''Supports path= to specify a location, otherwise assumes the
        current directory.
        '''
        path = kwargs.get('path', '.')
        self._path = '%s/%s' % (path, self.name)
        self._db = dbm.open(self._path, 'c')
        return [ ]

    def exists(self, id):
        # overridable callback for external storage
        if not isinstance(id, str): return False
        return id in self._db

    def load(self, id):
        # overridable callback for external storage, do not call directly
        if not self.exists(id): return None
        blob = self._db[id]
        return blob

    def save(self, id, blob):
        # overridable callback for external storage, do not call directly
        self._db[id] = blob
        return id

    def kill(self, id):
        # overridable callback for external storage, do not call directly
        if id in self._awake:
            raise RuntimeError('Call destroy() instead.')
        if self.exists(id):
            del self._db[id]

    def close(self):
        self._db.close()

#----------------------------------------------------------------------------

def fetch(id):
    "A global routine attempts to fetch one or more objects from all Stores."
    if isinstance(id, (list, tuple, set)):
        return [ fetch(x) for x in id ]
    for store in Store._stores.values():
        if store.exists(id):
            return store.fetch(id)
    return None

#----------------------------------------------------------------------------

def __test__():
    from testing import __ok__
    import timing

    print('Testing persistant object storage...')

    name = '_test_persist'
    if os.path.isdir(name):
        print('Directory %s already exists. Cannot complete tests.' % name)
        __ok__(name, None)
        return

    if os.path.exists(name + '.db'):
        print('Dbm file %s.db already exists. Cannot complete tests.' % name)
        __ok__(name, None)
        return

    count = 500

    class _other (object): pass
    class X (Identified, Persistent, _other): pass
    for __ in ['_other','X']: globals()[__] = locals()[__]

    # use a filestore
    p = FileStore(name)
    __ok__(p, p)
    x = X()
    p.add(x)
    id = x.id()
    __ok__(id is not None)
    __ok__(p.exists(id), id in p)

    y = fetch(id)
    __ok__(x.id() == y.id())
    __ok__(x is y)

    found = glob.glob('./%s/*' % name)
    __ok__(len(found), 1)
    __ok__(found[0], found[0])

    y = x = None
    p.destroy(id)
    found = glob.glob('./%s/*' % name)
    __ok__(len(found), 0)
    y = fetch(id)
    __ok__(y, None)
    p.close()

    os.rmdir(name)

    print('Testing persistant filestore...')

    # use a filestore for many items
    p = FileStore(name)
    x = X()
    p.add(x)
    id = x.id()
    __ok__(id is not None)
    p.destroy(x)

    ids = set([])
    timing.start()
    for n in range(1, count+1):
        y = X()
        y.number = n
        id = p.add(y)
        if n < 5:
            __ok__(id in ids, False)
        else:
            if id in ids: __ok__(False, 'id collision on #%d' % n)
        ids.add(id)
    timing.finish()
    print('%g created per second' % (float(n)/(timing.t1-timing.t0)))
    found = glob.glob('./%s/*.blob' % name)
    __ok__(len(found), len(ids))
    p.close()

    p = FileStore(name)
    for id in ids:
        p.destroy(id)
    found = glob.glob('./%s/*/*' % name)
    __ok__(len(found), 0)
    p.close()

    os.rmdir(name)

    print('Testing persistent dbmstore...')

    # use a dbmstore
    p = DbmStore(name)
    x = X()
    p.add(x)
    id = x.id()
    __ok__(id is not None)
    __ok__(p.exists(id), id in p)

    y = fetch(id)
    __ok__(x.id() == y.id())
    __ok__(x is y)

    y = x = None
    p.destroy(id)
    y = fetch(id)
    __ok__(y, None)

    ids = set([])
    timing.start()
    for n in range(1, count+1):
        y = X()
        y.number = n
        id = p.add(y)
        if n < 5:
            __ok__(id in ids, False)
        else:
            if id in ids: __ok__(False, 'id collision on #%d' % n)
        ids.add(id)
    timing.finish()
    print('%g created per second' % (float(n)/(timing.t1-timing.t0)))
    p.close()

    p = DbmStore(name)
    for id in ids:
        p.destroy(id)
    p.close()

    os.unlink(name + '.db')

if __name__ == '__main__':
    from testing import __report__
    __test__()
    __report__()
