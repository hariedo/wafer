# interpolations - routines for numerical interpolations between control values

'''

Routines for numerical interpolation between various control values.

SYNOPSIS

    >>> import interpolations ; from interpolations import *
    >>> import vectors ; from vectors import *

    Linear:

    >>> linear(0.5,  10, 20)
        15.0

    >>> linear(1.0, 2.0,  1.5,  10, 20)
        15.0

    >>> linear(1.0, 2.0,  1.5,  V(10,100,1000), V(20,200,2000))
        V(15.0, 150.0, 1500.0)

    Bezier:

    >>> bezier(0.5,  10, 20, 10)
        15.0

    >>> bezier(0.5,  10, 20, 20, 10)
        175.0

    >>> bezier(0.5,  V(10,100), V(20,200), V(20,200), V(10,100))
        V(17.5, 175.0)

AUTHOR

    Ed Halley (ed@halley.cc) 25 October 2007

REFERENCES

    Bezier code adapted and ported to python from a C++ v3 implementation:
    http://local.wasp.uwa.edu.au/~pbourke/surfaces_curves/bezier/index2.html

'''

__all__ = [ 'linear', 'bezier' ]

#----------------------------------------------------------------------------

import math

#----------------------------------------------------------------------------

def linear(*args):
    '''Find a point along a linear path of two controls.
    Controls may be scalars, or vectors if arithmetic operators defined.

    May take three arguments, linear(i, A, B).
    Interpolated values equal control A at i==0.0, and control B at i==1.0.
    
    May take five arguments, linear(x, y, i, A, B).
    Interpolated values equal control A at i==x, and control B at i==y.
    '''
    if len(args) == 3:
        (xmin, xmax) = (0., 1.)
        (x, hmin, hmax) = args
    elif len(args) == 5:
        (xmin, xmax, x, hmin, hmax) = args
    else:
        raise ValueError('linterp() takes 3 or 5 arguments')
    return ( ((x)-(xmin)) * ((hmax)-(hmin)) / ((xmax)-(xmin)) + (hmin) )

#----------------------------------------------------------------------------

# ref:
# http://local.wasp.uwa.edu.au/~pbourke/surfaces_curves/bezier/index2.html

def bezier3(i, A, B, C):
    '''Find a point along a bezier curve of three controls.
    Controls may be scalars, or vectors if arithmetic operators defined.

    Takes four arguments, bezier3(i, A, B, C).
    Interpolated values touch A at i==0.0, and C at i==1.0.
    Interpolated values may not touch B value.
    '''
    ii = 1.-i
    i2 = i*i
    ii2 = ii*ii
    j = A*ii2 + 2*B*ii*i + C*i2
    return j

def bezier4(i, A, B, C, D):
    '''Find a point along a bezier curve of four controls.
    Controls may be scalars, or vectors if arithmetic operators defined.

    Takes five arguments, bezier4(i, A, B, C, D).
    Interpolated values touch A at i==0.0, and D at i==1.0.
    Interpolated values may not touch B or C values.
    '''
    ii = 1.-i
    i3 = i*i*i
    ii3 = ii*ii*ii
    j = A*ii3 + 3*B*i*ii*ii + 3*C*i*i*ii + D*i3
    return j

def bezier(i, *A):
    '''Find a point along a bezier curve of arbitrary number of controls.
    Controls may be scalars, or vectors if arithmetic operators defined.

    Takes at least two arguments, bezier(i, A, ...).  Interpolated values
    touch A at i==0.0, and last control at i==1.0.  Interpolated values
    may or may not touch any of the control value except the first and
    last control values.

    Uses linear interpolation for two controls (A, B),
    or constant if only given one control (A).
    '''
    n = len(A)-1
    if n < 4:
        if n < 0: raise ValueError('need at least one control value')
        if n == 0: return A[0]
        if n == 1: return linear(i, *A)
        if n == 2: return bezier3(i, *A)
        if n == 3: return bezier4(i, *A)
    ik = 1
    ii = 1-i
    ink = math.pow(ii, float(n))
    if i == 1.0:
        return A[-1]*1.0
    j = A[0]*0.0
    for k in range(n+1):
        nn = n
        kn = k
        nkn = n - k
        blend = ik*ink
        ik *= i
        ink /= ii
        while (nn >= 1):
            blend *= nn
            if (kn > 1):
                blend /= kn
                kn -= 1
            if (nkn > 1):
                blend /= nkn
                nkn -= 1
            nn -= 1
        j += A[k]*blend
    return j

#----------------------------------------------------------------------------

def __spline_4p(i, n1, p0, p1, p2):
    # Find point between p0 at i==0.0, and p1 at i==1.0
    return (i*((2-i)*i - 1)     * n1 +
            (i*i*(3*i - 5) + 2) * p0 +
            i*((4-3*i)*i + 1)   * p1 +
            (i-1)*i*i           * p2 ) / 2

def spline(i, *P, **kwargs):
    '''Find a point along a spline curve passing through all given points P.
    Points may be scalars, or vectors if arithmetic operators defined.

    Takes at least three arguments, spline(i, P0, P1), but more typically
    at least four points are given, spline(i, P0, P1, P2, P3, ...).
    Interpolated values touch P0 at i==0.0, and touch P1 at i==1.0, and
    touch the last P<n> at i==<n>.

    Unlike most Catmull-Rom splines, this routine allows interpolation
    between the first two points, and between the last two points.  The
    slope through P1 and P<n-1> are defined as if the P0 and P<n> are
    duplicated.

    Any value of i outside the range (0, <n>) will return the P0 or P<n>
    point.
    '''
    if len(P) < 4:
        raise ValueError('need at least four points to interpolate spline')
    if terminal:
        if i <= 0.0: return P[0]
        if i >= float(len(P)-1): return P[-1]
    else:
        if i <= 1.0: return P[1]
        if i >= float(len(P)-2): return P[-2]
    ix = int(i)
    if terminal:
        P = [ P[0], ] + list(P) + [ P[-1] ]
        ix += 1
    return __spline_4p(i-int(i), P[ix-1], P[ix], P[ix+1], P[ix+2])

def cospline(i, Q, P):
    '''Find a point along a spline curve passing through all given points P.
    Points may be scalars, or vectors if arithmetic operators defined.

    Takes exactly three arguments, a scalar and two lists or tuples with
    at least four elements each.  The first list is a series of scalar
    values in ascending or descending order, to be compared against the
    given scalar i.

    '''
    if len(P) < 4:
        raise ValueError('need at least four points to interpolate spline')
    if len(Q) != len(P):
        raise ValueError('need two sequences of the same length')
    if Q[0] > Q[-1]:
        Q = list(reversed(Q))
        P = list(reversed(P))
    if i <= Q[0]:
        return P[0]
    if i >= Q[-1]:
        return P[-1]
    # catmull-rom spline interpolation demands two extra control points
    # so we just duplicate the first and last ones
    P = [ P[0], ] + P + [ P[-1] ]
    ix = 0
    while ix < len(Q) and Q[ix+1] < i:
        ix += 1
    i = linear(Q[ix], Q[ix+1], i, 0.0, 1.0)
    return __spline_4p(i, P[ix], P[ix+1], P[ix+2], P[ix+3])

#----------------------------------------------------------------------------

def __table__():
    for x in range(40+1):
        i = x/40.0
        print(i, ',', bezier(i, 1.0,2.0,0.0,2.0,1.0))

def __splinetest__():
    import vectors
    V = vectors.V
    for t in range(0, 4*10+1):
        print(t/10.0+1,
              spline(t/10.0+1,
                     V(1,11), V(2,22), V(3,33), V(4, 44), V(5,55)))
    print('--')
    for t in range(0, 4*10+1):
        print(t/10.0+1,
              cospline(t/10.0+1, [ 1,2,3,4,5 ], [11,22,33,44,55]))

if __name__ == '__main__':

    import vectors ; from vectors import V,equal,zero

    assert linear(0.5, 50, 60) == 55
    assert linear(1, 2, 1.5, 50, 60) == 55
    assert linear(1, 2, 1.5, V(50,500), V(60,600)) == V(55,550)

    assert bezier3(0.0,  0.0, 1.0, 0.0) == 0.0
    assert bezier3(0.5,  0.0, 1.0, 0.0) == 0.5
    assert equal( bezier3(0.2,  0.0, 1.0, 0.0),
                  bezier3(0.8,  0.0, 1.0, 0.0) )
    assert bezier3(1.0,  0.0, 1.0, 0.0) == 0.0

    assert bezier4(0.0,  0.0, 1.0, 1.0, 0.0) == 0.0
    assert bezier4(0.5,  0.0, 1.0, 1.0, 0.0) == 0.75
    assert equal( bezier4(0.2,  0.0, 1.0, 1.0, 0.0),
                  bezier4(0.8,  0.0, 1.0, 1.0, 0.0) )
    assert bezier4(1.0,  0.0, 1.0, 1.0, 0.0) == 0.0

    assert bezier(0.0,  0.0, 1.0, 1.0, 1.0, 0.0) == 0.0
    assert bezier(0.5,  0.0, 1.0, 1.0, 1.0, 0.0) == 0.875
    assert equal( bezier(0.2,  0.0, 1.0, 1.0, 1.0, 0.0),
                  bezier(0.8,  0.0, 1.0, 1.0, 1.0, 0.0) )
    assert bezier(1.0,  0.0, 1.0, 1.0, 1.0, 0.0) == 0.0
    assert bezier(1.0,  0.0, 1.0, 1.0, 1.0, 0.0) == 0.0

    print('interpolations.py: all internal tests on this module passed.')
