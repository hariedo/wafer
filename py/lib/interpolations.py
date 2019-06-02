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
        raise ValueError('linear() takes 3 or 5 arguments')
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

def spline(i, P, Q=None):
    '''Find a point along a spline curve passing through all given points P.
    Points may be scalars, or vectors if arithmetic operators defined.

    Unlike most Catmull-Rom splines, this routine allows interpolation
    between the first two points, and between the last two points.  The
    slope through P[1] and P[<n-1>] are defined as if the P[0] and P[<n>]
    are duplicated.

    Interpolated values touch P[0] at i==0.0, and touch the last P<n> at
    i==1.0.  If given a third argument Q, it should be an ordered list of
    scalars (matching the length of list P) to compare against the scalar
    <i> instead.  Interpolated values instead touch P[<n>] at i==Q[<n>].

    '''
    if Q is None:
        Q = [ float(x)/(len(P)-1) for x in range(len(P)) ]
    if len(P) < 2:
        raise ValueError('need at least two points to interpolate spline')
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
    try:
        import svgwrite
        d = svgwrite.Drawing('splinetest.svg', profile='tiny')
        q = [ V(10,11), V(20,33), V(30,22), V(40, 55), V(50,44) ]
        for a in q:
            d.add(d.circle(a*10, r=2))
        for t in range(1, 4*10+1):
            ay = (t-1)/40.0
            by = (t+0)/40.0
            ax = spline(ay, q)
            bx = spline(by, q)
            d.add(d.line( ax*10, bx*10, stroke=svgwrite.rgb(10,10,16,'%')))
            print(repr(ax))
        d.save()
        print(repr(bx))
    except:
        print('problem with svgwrite; test skipped.')
        raise

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

    q = [ V(10,11), V(20,33), V(30,22), V(40, 55), V(50,44) ]
    an = -1
    for t in range(0, 4*10+1):
        ay = t/40.0
        ax = spline(ay, q)
        if 0 == t % 10:
            assert ax in q
            an = q.index(ax)
        if 5 == t % 10:
            assert not ax in q
            assert q[an][0] < ax[0] < q[an+1][0]
            assert q[an][1] < ax[1] < q[an+1][1] or q[an][1] > ax[1] > q[an+1][1]

    print('interpolations.py: all internal tests on this module passed.')
