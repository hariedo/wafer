# bindings - a simple non-destructive unification of arbitrary terms

'''

A simple non-destructive unification between arbitrary sets of terms.

ABSTRACT

    A Binding is a set of term names and any term values bound to them,
    whether "bound" or "unbound."  A "bound" term has a value that is not
    the None value.  Bindings can be combined to see if they contain
    values that do not "conflict" with each other.  That is, if two
    bindings have the same term but each with different non-None values,
    then the bindings are said to conflict.  The None value does not
    conflict with any value.

SYNOPSIS

    >>> import bindings ; from bindings import *

    >>> b = Binding()
    >>> b.put( city='Denver', altitude=None )
    >>> b
    Binding( { 'city': 'Denver', 'altitude': None } )

    >>> # b is unmodified by checking if some terms are bindable
    ... b.bindable( city='Denver', altitude=5280 )
    True
    >>> b
    Binding( { 'city': 'Denver', 'altitude': None } )

    >>> # b is modified if the binding succeeds
    ... b.bind( city='Denver', pop=2000000 )
    True
    >>> b
    Binding( { 'city': 'Denver', 'altitude': None, 'pop': 2000000 } )

    >>> # b is not modified if given terms conflict with non-None values
    ... b.bind( city='Dallas', altitude=625 )
    False
    >>> b
    Binding( { 'city': 'Denver', 'altitude': None, 'pop': 2000000 } )

    >>> b.bound( 'city', 'pop' )
    True

    >>> b.bound( 'city', 'altitude' )
    False

AUTHOR

    Ed Halley (ed@halley.cc) 19 April 2008

'''

__all__ = [ 'Binding' ]

#----------------------------------------------------------------------------

class Binding (object):

    '''

    A Binding is a simple way of implementing non-destructive unification.

    A Binding is a set of term names and any term values bound to them,
    whether "bound" or "unbound."  A "bound" term has a value that is not
    the None value.  Bindings can be combined to see if they contain
    values that do not "conflict" with each other.  That is, if two
    bindings have the same term but each with different non-None values,
    then the bindings are said to conflict.  The None value does not
    conflict with any value.

    '''

    def __init__(self, *args, **terms):
        '''Constructs a new set of bindings.

        An initial set of bound terms can be added in a variety of ways.
        To make an empty binding:
            binding = Binding()
        To make a clone of another binder, use an unnamed argument.
            binding = Binding( original )
        To make a binding from a dict, pass it in as an unnamed argument.
            binding = Binding( { 'city': 'Denver', 'altitude': 5280 } )
        To make a binding from simple named terms, use named argument(s).
            binding = Binding( city='Denver', altitude=5280 )

        Other methods can also accept these flexible arguments, all of
        which will be referred as <terms> in the documentation for each
        method below.
        '''
        self.terms = { }
        self.put(*args, **terms)

    def __nonzero__(self):
        return True and self.terms

    def __contains__(self, term):
        '''Check if a term exists in the binding (dict-like).'''
        return term in self.terms

    def __getitem__(self, term):
        '''Get the value bound to a term in the binding (dict-like).'''
        return self.terms[term]

    def __repr__(self):
        if not self.terms:
            return '%s()' % self.__class__.__name__
        return '%s(%s)' % (self.__class__.__name__, repr(self.terms))

    def put(self, *args, **terms):
        '''Forcefully asserts each given term to add or replace values.
            binding.put( <terms> )

        This is usually used only to set up a new binding, but can be
        used at any time to replace values which might conflict with
        existing ones.
        '''
        for arg in args:
            if hasattr(arg, 'terms'): arg = arg.terms
            for term in arg:
                self.terms[term] = arg[term]
        if terms:
            self.put(terms)

    def __updated(self, *args, **terms):
        # internal non-conflicting binding of terms
        # returns updated dict of terms if successful
        # returns None if any conflict found
        result = self.terms.copy()
        for arg in args:
            if hasattr(arg, 'terms'): arg = arg.terms
            for term in arg:
                if not term in result:
                    result[term] = arg[term]
                elif result[term] is None:
                    result[term] = arg[term]
                elif result[term] != arg[term]:
                    return None
        if terms:
            for term in terms:
                if not term in result:
                    result[term] = terms[term]
                elif result[term] is None:
                    result[term] = terms[term]
                elif result[term] != terms[term]:
                    return None
        return result

    def bindable(self, *args, **terms):
        '''Attempts to bind all given binding values.
            if binder.bindable( <terms> ): pass
        Returns False if any given term conflicts with current values.
        Returns True if the given terms would successfully bind.
        '''
        return self.__updated(*args, **terms) is not None

    def bind(self, *args, **terms):
        '''Attempts to bind all given binding values.
            if binder.bind( <terms> ): pass
        Returns False and does not modify any bindings if conflicts found.
        Returns True and updates the bindings with new terms if successful.
        '''
        result = self.__updated(*args, **terms)
        if not result: return False
        self.terms = result
        return True

    def bound(self, *names):
        '''Checks if all terms, or all given names, have defined values.
            if binder.bound(): pass
            if binder.bound( name1, name2 ): pass
        If no names are given, then all of our term names will be checked.
        Returns True if any of the terms to check have None for its value.
        '''
        if not names: names = self.terms.keys()
        for name in names:
            if name in self.terms:
                if self.terms[name] is None:
                    return False
        return True

#----------------------------------------------------------------------------

if __name__ == '__main__':

    # create a binding object
    b = Binding()
    b.put( city='Denver', altitude=None )
    assert 'city' in b
    assert b['city'] == 'Denver'
    assert 'altitude' in b
    assert b['altitude'] is None

    # checking if something is bindable does not modify the binding
    assert b.bindable( city='Denver', altitude=5280 )
    assert b['altitude'] is None

    # b is modified if the binding succeeds
    assert b.bind( city='Denver', pop=2000000 )
    assert b['city'] is 'Denver'
    assert b['altitude'] is None
    assert b['pop'] is 2000000

    # b is not modified if given terms conflict with non-None values
    assert not b.bind( city='Dallas', altitude=625 )
    assert b['altitude'] is None

    assert b.bound( 'city', 'pop' )
    assert not b.bound( 'city', 'altitude' )

    print('bindings.py: all internal tests on this module passed.')
