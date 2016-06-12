# timelines - a data model for events to be compared and rendered

'''

A data model for events to be compared and rendered.

SYNOPSIS

    >>> import timelines

    >>> line = timelines.Timeline('Japanese Eras')
    >>> line.add( timelines.Mark(1600, 'battle of sekigahara' )
    >>> line.add( 'tokugawa shogunate',
                  timelines.Mark(1603, 'tokugawa ieyasu takes power'),
                  timelines.Mark(1867, 'shogunate abolished') )
    >>> line.add( timelines.Mark(1853, 'perry sails into tokyo bay' )

ABSTRACT

    A general-purpose data model for tracking a number of time-sorted
    events for the purpose of drawing on a timeline.

    A timeline is composed of events or marks on the timeline at
    specified times.  The data type for a timestamp is left to the
    caller, as long as the types are comparable.  Thus, it's possible to
    standardize on floating point numbers, strings, or time/date
    structures, depending on the need of the caller.

    Some libraries have a special "timespan" type of event that gives a
    start and end time as a single mark.  Instead, this library allows
    nested timelines, so a timespan is just a sub-timeline with its own
    starting and ending events.

AUTHOR:

    Ed Halley (ed@halley.cc) 12 June 2016

'''

class Thing (object):
    # An abstract base class for simple named objects that are tagged
    # with arbitrary keywords.  Specialized classes can reserve specific
    # arguments for their own use, and send all other named arguments
    # here.  No attempt is made to keep names unique at this level.
    def __init__(self, name, tags=None):
        self.name = name
        if tags is None: tags = [ ]
        self.tags = set(tags)

class Mark (Thing):
    '''A single point on a timeline, with keywords to categorize.'''

    DEFAULT = 'star'
    MARKERS = { 'star': '*', 'spot': 'o', 'plus': '+',
                'left': '<', 'right': '>' }

    def __init__(self, when, name, fuzzy=False, marker=None, tags=None):
        super(Mark, self).__init__(name, tags)
        self.when = when
        self.fuzzy = fuzzy
        if marker is None:
            marker = Mark.DEFAULT
        if marker.lower() in Mark.MARKERS:
            marker = Mark.MARKERS[marker]
        self.marker = marker

    def __cmp__(self, other):
        try:
            return cmp(self.when, other.when)
        except:
            pass
        return cmp(self.when, other)

class Timeline (Thing):
    '''A collection of marks or other timelines.

    Whenever a mark or a sub-timeline is added to this timeline, the span
    of events is kept updated to aid in rendering.

    '''

    def __init__(self, name, tags=None, *things):
        self.lines = set([])
        self.marks = set([])
        self.first = None
        self.final = None
        self.parent = None
        for each in things:
            self.add(each)

    def find(self, tags=None):
        '''Find Mark objects in this timeline or its sub-timelines.
        
        If given a collection of tags, only Mark objects with at least
        one of the given tags are returned.
        '''
        if tags is None:
            found = self.marks.copy()
        else:
            tags = set(tags)
            found = set([])
            for each in self.marks:
                if each.tags.intersection(tags):
                    found.add(each)
        for each in self.lines:
            found = found.union(each.find(tags=tags))
        return found

    def stretch(self, thing):
        # Update the first/final range references to include the given.
        if isinstance(thing, Timeline):
            if thing.first is not None:
                if self.first is None or thing.first < self.first:
                    self.first = thing.first
            if thing.final is not None:
                if self.final is None or thing.final > self.final:
                    self.final = thing.final
        if isinstance(thing, Mark):
            if self.first is None or thing.when < self.first.when:
                self.first = thing
            if self.final is None or thing.when > self.final.when:
                self.final = thing
        if self.parent is not None:
            self.parent.stretch(thing)

    def add(self, thing):
        '''Add another Mark or Timeline as a child of this line.'''
        if isinstance(thing, Timeline):
            thing.parent = self
            self.lines.add(thing)
        if isinstance(thing, Mark):
            self.marks.add(thing)
        self.stretch(thing)
        if self.parent is not None:
            self.parent.stretch(self)

#----------------------------------------------------------------------------

if __name__ == '__main__':
    line = Timeline('example')
    a = Mark('2014-04-01', 'assignment made official', tags=['Halley'])
    b = Mark('2015-11-11', 'first flight', tags=['MRJ90'])
    line.add(a)
    assert line.first is a
    assert line.final is a
    line.add(b)
    assert line.first is a
    assert line.final is b
    assert len(line.find()) == 2
    assert a in line.find(tags=['Halley'])
    assert not b in line.find(tags=['Halley'])

    print('timelines.py: all internal tests on this module passed.')
