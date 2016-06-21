# -*- python -*-

'''

recipes - Some basic numerical and statistical recipes implemented in Python.

SYNOPSIS

    >>> import recipes

AUTHOR

    Ed Halley (ed@halley.cc) 24 January 2010

SEE ALSO

    Simple Recipes in Python by William Park
    http://www.phys.uu.nl/~haque/computing/WPark_recipes_in_python.html

'''

#----------------------------------------------------------------------------

import math

def num(x):
    '''Return an integer or a float, if it can be cast successfully.
    Returns the original value otherwise.  Usually used on strings
    that may or may not parse to a number.
    '''
    try: return int(x)
    except:
        try: return float(x)
        except: pass
    return x

def sign(x):
    '''Return the sign of a value as -1, 0 or +1.'''
    # Compare with math.copysign() which handles -0 and NaN but not 0.
    if x < 0: return -1
    if x > 0: return 1
    return 0

def mean(X):
    '''Calculate the arithmetic mean of data.'''
    n = float(len(X))
    return sum(X) / n

def deviation(X):
    '''Calculate the standard deviation of data.'''
    n = float(len(X))
    a = mean(X) / n
    std = 0
    for x in X:
        std += (x - a)**2
    return math.sqrt(std / (n-1))

def linefit(X, Y=None, extra=False):
    '''Returns (a, b) of the regression line "y=ax+b" from given points.
    If given only one list, assumes X is a list of incrementing integers.
    If given extra=True, returns additional parameters of the regression,
    as (a, b, R*R, s*s).
    '''
    if Y is None:
        Y = X
        X = list(map(float, range(len(Y))))
    if len(X) != len(Y):
        raise ValueError('unequal length')
    n = len(X)
    Sx = sum(X)
    Sy = sum(Y)
    Sxx = Syy = Sxy = 0.0
    for x, y in zip(X, Y):
        Sxx += x*x
        Syy += y*y
        Sxy += x*y
    det = Sxx*n - Sx*Sx
    a = (Sxy*n - Sy*Sx) / det
    b = (Sxx*Sy - Sx*Sxy) / det

    if extra:
        meanerror = residual = 0.0
        for x, y in zip(X, Y):
            meanerror += (y - Sy/n)**2
            residual += (y - a*x - b)**2
        RR = 1.0 - residual/meanerror
        ss = residual / (n-2)
        #Var_a = ss*n / det
        #Var_b = ss*Sxx / det
        return (a, b, RR, ss) #, Var_a, Var_b)
    
    return a, b

#----------------------------------------------------------------------------

def weighted(choices, total=0):
    '''Given a dict of key:weight pairs, chooses a key at random.

    The dict values are non-negative numerical weights.  Keys with higher
    values are chosen more often than keys with lower values.

    If the caller knows the total of all weights, it can be given to
    avoid recalculating it internally on each call.  If the given total
    is not accurate, a key may be chosen with a poorly-shaped
    distribution.
    '''
    if not total:
        total = sum(choices.values())
    mark = random.random()*total
    keys = choices.keys()
    for i in xrange(len(keys)):
        span = choices[keys[i]]
        if span > mark:
            return keys[i]
        mark -= span
    # should not reach here if total is accurate
    return random.choice(keys)

#----------------------------------------------------------------------------

if __name__ == '__main__':

    assert sign(-3.14) == -1.0
    assert sign(0.0) == 0.0
    assert sign(3.14) == 1.0

    assert mean(range(5)) == 2.0
    assert mean(range(9)) == 4.0

    assert linefit( (1,3,5,7), (2,2,2,2) ) == (0.0, 2.0)
    assert linefit( (1,3,5,7), (2,3,4,5) ) == (0.5, 1.5)
    assert linefit( (1,3,5,7) ) == (2.0, 1.0)

    #TODO: quick sanity test that weighted() picks valid choices

    print('recipes.py: all internal tests on this module passed.')
