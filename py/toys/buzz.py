# buzz - a phrase generator which assembles phrases from random pieces

'''

NAME

    buzz - a phrase generator which assembles phrases from random pieces

SYNOPSIS

    >>> buzz = Buzz('(She|He) (found|saw) a (red|green|blue) (ball|block).')
    >>> buzz.select()
    'She saw a green ball.'
    >>> buzz.select()
    'He found a red block.'
    >>> buzz.select()    # each call returns a new unique permutation
    'He saw a blue block.'
        ...
    >>> buzz.select()    # returns None if new permutation not found quickly
    None
    
    >>> buzz.sample()    # choose one of the earlier select() results
    'He saw a blue block.'
    >>> buzz.sample(2)   # choose N of the earlier select() results
    [ 'He found a red block.', 'He saw a blue block.' ]

DESCRIPTION

    This module was inspired by many novelty tools which purport to
    create convincing buzzword-filled jargon, by assembling sentences
    from a few scraps of impressive but meaningless prose:

        "As a resultant implication, " +
        "initiation of critical subsystem development " +
        "is further compounded when taking into account " +
        "the evolution of specifications over a given time period."

    Besides this narrow novelty application, I have found that having
    pronounceable names, or thematic phrases, has been a recurring
    requirement in many gaming and non-gaming applications.  A
    SimCity-like game may use this sort of generator to produce
    convincing but unique street names or neighborhoods, for example:

        neigbborhoods = Buzz("%{serene} %{botany} %{geography}", terms)

        'Shady Oakwood Estates'
        'Rolling Pine Meadows'
        'Breezy Willow River'
        'Cozy Cottonwood Creek'
        'Rolling Oakwood Heights'
        (etc.)

    The constructor supports several ways of defining the pieces which
    are assembled into the final formulaic phrase constructions.  The
    buzzword object keeps track of past selections, so as to avoid
    unintended repeat results.  The terms can even be redefined later, to
    allow more choices when the original set starts to wear thin.

AUTHOR

    Ed Halley (ed@halley.cc) 21 April 2008

'''

#----------------------------------------------------------------------------

import random
import re

class Buzz:

    '''A phrase generator, turning sets of fragments into unique phrases.'''

    TRIFIX = re.compile(r'\A(.*?)(\%\{.*?\}|\%[A-Za-z])(.*)\Z', re.DOTALL)
    EXPAND = re.compile(r'(\%\{.*?\}|\%[A-Za-z])', re.DOTALL)
    PARENS = re.compile(r'(\(([^()]*?)\))', re.DOTALL)
    
    def __init__(self, format='', *dicts, **terms):
        '''Constructs a new buzz generator that can return unique phrases.
        
        The first argument should define the basic format for all phrases
        generated.  There are two special strings that can be used in a
        format string: (x|y|z) or %{name}.  If the %{name} syntax is
        used, then the list of choices for that name should be passed in
        additional arguments, such as a dict or a named parameter.

        Each example gives identical results, but uses alternate
        arguments to define the expandable choices.

            # generates phrases like "a red block" or "a green car"
            buzz = Buzz('a (red|green|blue) (ball|block|car)')

            buzz = Buzz('a %{color} %{toy}',
                        color="red|green|blue",
                        toy=['ball','block','car'])

            buzz = Buzz('a %{color} %{toy}',
                        { 'color': "red|green|blue",
                        'toy': ['ball','block','car'] } )

        Note that expansion terms can be nested, referring to other terms:

            buzz = Buzz('a %{adj} %{noun}',
                        adj='%{texture} %{color}',
                        noun='%{toy}|%{garment}',
                        texture='shiny|rough|smooth|soft',
                        color='red|blue|green',
                        toy='ball|block|car',
                        garment='shirt|dress|hat|pair of boots')

        Circular or self-referential terms are not detected, but an error
        may be raised when trying to call the pick() method.

        If called without arguments, the strings returned are always
        empty.  The same options exist for the Buzz.setup() method which
        can be called subsequently.

        '''
        self.reset()
        self.setup(format, *dicts, **terms)

    def reset(self):
        '''Forgets all previously returned results from select().'''
        self.spent = set([])
        self.total = 0

    def addterm(self, name, choices):
        '''Adds or replaces one term with a new set of expansion choices.
        If the example in the __init__() documentation is followed, then
        this method can replace existing terms:

            # changes the toy selection
            buzz.addterm( 'toy', 'doll|ball|truck|book' )
            
        '''
        if hasattr(choices, 'split'):
            choices = choices.split('|')
        self.terms[name] = choices
        self.factors[name] = len(choices)
        self.total = 0

    def addterms(self, terms):
        '''Adds or replaces multiple expansion terms from a dictionary.'''
        for term in terms:
            self.addterm(term, terms[term])

    def setup(self, format, *dicts, **terms):
        '''Replaces the entire expansion term selection from all arguments.
        This routine is called on initialization, but can be called at any
        other time as well.  See the __init__() documentation on the forms
        of arguments accepted.
        '''
        self.factors = { }
        self.terms = { }
        for d in dicts:
            self.addterms(d)
        if terms:
            self.addterms(terms)
        format = self.autodef(format)
        self.format = self.split(format)
        self.picks = { }

    def autodef(self, format):
        '''Defines any terms directly from the format, in (x|y|z) syntax.
        Chooses new unique numerical names for the replacement terms.
        Returns a new format string which uses %{1} syntax instead.
        '''
        counter = 0
        m = Buzz.PARENS.search(format)
        while m:
            counter += 1
            while str(counter) in self.terms:
                counter += 1
            name = '%%{%s}' % counter
            format = format.replace(m.group(1), name, 1)
            self.addterm( str(counter), m.group(2) )
            m = Buzz.PARENS.search(format)
        return format

    def split(self, format):
        '''Converts format string into list of string components.'''
        parts = [ ]
        m = Buzz.TRIFIX.match(format)
        while m:
            parts.append(m.group(1))
            parts.append(m.group(2))
            format = m.group(3)
            m = Buzz.TRIFIX.match(format)
        if format:
            parts.append(format)
        return parts

    def pick(self):
        '''Returns a random phrase expanded from the defined choices.
        Self-referential terms for expansion will raise an error.
        An example of a self-referential expansion term would be:
            Buzz('a %{fruit} is sweet', fruit=['%{fruit}'])
        '''
        names = set([])
        parts = [ ]
        for part in self.format:
            m = Buzz.EXPAND.search(part)
            while m:
                term = m.group(1)[2:-1]
                if term in names:
                    raise ValueError('self-referential choices')
                names.add(term)
                if term in self.terms:
                    choice = random.choice(self.terms[term])
                    part = part.replace(m.group(1), choice)
                m = Buzz.EXPAND.search(part)
            parts.append(part)
        return ''.join(parts)

    def permutes(self):
        '''Returns a conservative estimate of the number of unique string
        selections that can be returned by pick().  This may be above or
        below the actual number of unique strings possible.  Given the
        way that terms can refer to other nested terms, we can only
        determine an estimate, and the select() method uses this estimate
        as a default number of retries to search for a new unique result.
        '''
        if self.total > 0:
            return self.total
        total = 1
        for factor in self.factors.values(): total *= factor
        self.total = total
        return total

    def select(self, retries=None):
        '''Tries to return a never-before returned phrase to the caller.

        Each time select() is called, a unique phrase is returned.
        If no unique phrases can be found, the None value is returned.
        This will happen if all permutations have already been selected.
        
        The None value may also be returned when nearly all of the
        possible permutations have been selected, and a new unique
        permutation is not found in a limited number of internal retries.
        See the permutes() method for more information.
        '''
        if retries is None:
            retries = self.permutes()
        for attempt in range(retries):
            try: choice = self.pick()
            except ValueError: continue
            if not choice in self.spent:
                self.spent.add(choice)
                return choice
        return None

    def sample(self, k=None):
        '''Returns a random previous result from earlier select() calls.
        Raises an error if select() has not been called since reset().
        '''
        if k is None:
            return self.sample(1)[0]
        if len(self.spent) < k:
            raise IndexError('must select() more before sample(%d)' % k)
        return random.sample(self.spent, k)

#----------------------------------------------------------------------------

# Run the module directly for a demonstration or self-test.

if __name__ == '__main__':

    buzz1 = Buzz('a %{adj} %{noun}',
                 adj='%{texture} %{color}',
                 noun='%{toy}|%{garment}',
                 texture='shiny|rough|smooth|soft',
                 color='red|blue|green',
                 toy='ball|block|car',
                 garment='shirt|dress|hat|pair of boots')

    buzz2 = Buzz('a %{color} %{toy}',
                 color="red|green|blue",
                 toy=['ball','block','car'])

    buzz3 = Buzz('(She|He) (found|saw) a (red|green|blue) (ball|block).')

    for buzz in (buzz1, buzz2, buzz3):
        seen = set([])
        for i in range(buzz.permutes() * 2):
            choice = buzz.select()
            if choice in seen:
                raise ValueError('repeated choice ' + repr(choice))
            if choice is not None:
                seen.add(choice)
                print(repr(choice))
        print('%d unique selections' % len(seen))
        print('%d estimated permutes' % buzz.permutes())
        print('(expected:  selections <= permutes <= selections*10)')
        print(repr(buzz.sample(2)))
        print('')
