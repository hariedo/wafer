# -*- python -*-

'''

patterns - Data-agnostic pattern matching classes.

ABSTRACT

    Given a stream of input data points, these classes form a foundation
    for detecting patterns in the stream.  Data points can be of any type
    that supports comparisons, such as numeric or textual or even
    structural components.

    As an analogy, a regular expression is a similar pattern matching
    facility that typically works on a stream of input data of character
    type.  Extend the concept to matching on numerical elements instead
    of characters, or match on even more complicated data structures.

SYNOPSIS

    >>> import patterns

    Defining a pattern:

    >>> class bullmarket (patterns.SpanPattern):
    ...    def match(self, point):
    ...       if not super(bullmarket, self).match(point):
    ...          return False
    ...       is_bull = compute_if_trending_up(self.points)
    ...       return is_bull

    Using the pattern:

    >>> bull = bullmarket(15) # SpanPattern records past n points
    >>> for day in chart:
    ...    if bull.match(day):
    ...       print('bull market detected prior to ', day)

AUTHOR

    Ed Halley (ed@halley.cc) 23 January 2010


'''

from __future__ import print_function

#----------------------------------------------------------------------------

class Pattern (object):
    '''Abstract base for data pattern matching routines.'''
    def __init__(self): pass
    def match(self, point): return False

#----------------------------------------------------------------------------
# Match Patterns (patterns that compare against known constant exemplars)

class MatchPattern (Pattern):
    '''Given an examplar, match if a point is EQUAL TO the exemplar.'''
    def __init__(self, exemplar):
        self.exemplar = exemplar
    def match(self, point):
        return point == self.exemplar

class MatchClassPattern (MatchPattern):
    '''Given a set of unique exemplars, match if the point is IN the set.'''
    def match(self, point):
        return point in self.exemplar

class MatchLambdaPattern (MatchPattern):
    '''Match against an arbitrary callable that takes one data point.'''
    def match(self, point):
        return bool(self.exemplar(point))

#----------------------------------------------------------------------------
# Unary Patterns (patterns that monitor other patterns)

class UnaryPattern (Pattern):
    '''Abstract base for a transform on another single pattern.'''
    def __init__(self, pattern):
        self.pattern = pattern

class NotPattern (UnaryPattern):
    '''An inverse of another pattern: if it returns False, we give True.'''
    def match(self, point):
        return not self.pattern.match(point)

class EverPattern (UnaryPattern):
    '''An inverse of another pattern: if it returns False, we give True.'''
    def match(self, point):
        # we stop calling child once we're flagged;
        # beware this may interfere with child's data collection
        if getattr(self, 'flag', False):
            return True
        if self.pattern.match(point):
            self.flag = True
            return True
        return False

class NeverPattern (UnaryPattern):
    '''An inverse of another pattern: if it returns False, we give True.'''
    # same as NotPattern(EverPattern(pattern))
    def match(self, point):
        # we stop calling child once we're flagged;
        # beware this may interfere with child's data collection
        if getattr(self, 'flag', False):
            return False
        if self.pattern.match(point):
            self.flag = True
            return False
        return True

#----------------------------------------------------------------------------
# Composite Patterns

class CompositePattern (Pattern):
    '''Abstract base for all voting or sequencing patterns.'''
    def __init__(self, *patterns):
        if len(patterns) == 1 and isinstance(patterns[0], (list,tuple)):
            patterns = patterns[0]
        self.patterns = patterns
    def match(self, point):
        self.matches = [ x.match(point) for x in self.patterns ]
        # it's important to always ask match() on all child patterns
        # as some children may collect data over a period of time
        return True

class AllPattern (CompositePattern):
    '''A unanimous voting pattern: all member patterns must vote True.'''
    # same as AnyPattern(NotPattern(pattern1), NotPattern(pattern2), ...)
    def match(self, point):
        super(AllPattern, self).match(point)
        return self.matches.count(True) == len(self.patterns)

class AnyPattern (CompositePattern):
    '''A nomination voting pattern: any member pattern can vote True.'''
    def match(self, point):
        super(AnyPattern, self).match(point)
        return self.matches.count(True) > 0

class NoPattern (CompositePattern):
    '''A veto voting pattern: any member voting True means False.'''
    # same as NotPattern(AnyPattern(patterns))
    def match(self, point):
        super(NoPattern, self).match(point)
        return self.matches.count(True) == 0

class VotePattern (CompositePattern):
    '''A counted voting pattern: enough member patterns must vote True.'''
    def __init__(self, enough, *patterns):
        super(VotePattern, self).__init__(*patterns)
        self.enough = enough
    def match(self, point):
        super(VotePattern, self).match(point)
        return self.matches.count(True) >= self.enough

class SequencePattern (CompositePattern):
    '''A serial pattern: members must vote True to proceed, False to abort.'''
    def __init__(self, *patterns):
        super(SequencePattern, self).__init__(*patterns)
        self.progress = 0
    def match(self, point):
        super(SequencePattern, self).match(point)
        if self.matches[self.progress]:
            self.progress += 1
            if self.progress >= len(self.patterns):
                self.progress = 0
                return True
        else:
            self.progress = 0
        return False

class SpanPattern (Pattern):
    '''Abstract base for patterns that use a span of recent points.'''
    def __init__(self, span):
        super(SpanPattern, self).__init__()
        if span < 2: raise ValueError('must have a span of at least two')
        self.span = span
        self.points = []
    def match(self, point):
        if len(self.points) >= self.span:
            self.points = self.points[1-self.span:]
        self.points.append(point)
        return len(self.points) >= self.span

#----------------------------------------------------------------------------

if __name__ == '__main__':

    m = MatchPattern('M')
    n = MatchClassPattern(set(['N','n']))
    l = MatchLambdaPattern(lambda point: point == 'L')
    all = AllPattern(l, m, n)
    any = AnyPattern(l, m, n)
    none = NoPattern(l, m, n)
    notl = NotPattern(l)
    everl = EverPattern(l)
    neverl = NeverPattern(l)
    vote = VotePattern(2, m, n, everl)
    five = SpanPattern(5)

    print('-', end='')
    tests = 'l m n all any none notl everl nev\'l vote five'.split()
    print(' '.join([ "%5s" % x for x in tests ]))
    results = { }
    sequence = 'JKLMNOP'
    for x in sequence:
        results[x] = [ ]
        results[x].append(l.match(x))
        results[x].append(m.match(x))
        results[x].append(n.match(x))
        results[x].append(all.match(x))
        results[x].append(any.match(x))
        results[x].append(none.match(x))
        results[x].append(notl.match(x))
        results[x].append(everl.match(x))
        results[x].append(neverl.match(x))
        results[x].append(vote.match(x))
        results[x].append(five.match(x))

    for x in sorted(results.keys()):
        print(x, end=' ')
        for t in results[x]:
            print("%5s" % t, end=' ')
        print('')

    expected = {
        #        l      m      n     all    any   none   notl   everl  nev'l  vote   five
        'J': [ False, False, False, False, False,  True,  True, False,  True, False, False ],
        'K': [ False, False, False, False, False,  True,  True, False,  True, False, False ],
        'L': [  True, False, False, False,  True, False, False,  True, False, False, False ],
        'M': [ False,  True, False, False,  True, False,  True,  True, False,  True, False ],
        'N': [ False, False,  True, False,  True, False,  True,  True, False,  True,  True ],
        'O': [ False, False, False, False, False,  True,  True,  True, False, False,  True ],
        'P': [ False, False, False, False, False,  True,  True,  True, False, False,  True ]
        }

    assert results == expected

    print('patterns.py: all internal tests on this module passed.')
