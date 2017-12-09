# BSD 3-Clause License
#
# Copyright (c) 2016, 2017, The University of Sydney. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""lattice.py: define lattices for use in meet-over-paths calculations.

We will take bottom elements to mean maximal value constraint
(uninitialised, or empty set), while top elements will be taken to mean a
maximally-unconstrained element (all possible values, universal set)."""

import abc
import functools
import itertools
import types
import typing as t
from copy import copy


class LatticeElement(abc.ABC):
    def __init__(self, value):
        """
        Construct a lattice element with the given value.

        Args:
          value: the value of this LatticeElement
        """
        self.value = value

    @abc.abstractclassmethod
    def meet(cls, a: 'LatticeElement', b: 'LatticeElement') -> 'LatticeElement':
        """Return the infimum of the given elements."""

    @classmethod
    def meet_all(cls, elements: t.Iterable['LatticeElement'],
                 initial: 'LatticeElement' = None) -> 'LatticeElement':
        """
        Return the infimum of the given iterable of elements.

        Args:
          elements: a sequence of elements whose common meet to obtain
          initial: an additional element to meet with the rest.
                   An empty sequence will result in this value, if provided.
        """
        if initial is not None:
            return functools.reduce(
                lambda a, b: cls.meet(a, b),
                elements,
                initial
            )
        return functools.reduce(
            lambda a, b: cls.meet(a, b),
            elements,
        )

    @abc.abstractclassmethod
    def join(cls, a: 'LatticeElement', b: 'LatticeElement') -> 'LatticeElement':
        """Return the infimum of the given elements."""

    @classmethod
    def join_all(cls, elements: t.Iterable['LatticeElement'],
                 initial: 'LatticeElement' = None) -> 'LatticeElement':
        """
        Return the supremum of the given iterable of elements.

        Args:
          elements: a sequence of elements whose common join to obtain
          initial: an additional element to join with the rest.
                   An empty sequence will result in this value, if provided.
        """
        if initial is not None:
            return functools.reduce(
                lambda a, b: cls.join(a, b),
                elements,
                initial
            )
        return functools.reduce(
            lambda a, b: cls.join(a, b),
            elements,
        )

    def __eq__(self, other):
        return self.value == other.value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            str(self)
        )


class BoundedLatticeElement(LatticeElement):
    """An element from a lattice with defined Top and Bottom elements."""
    TOP_SYMBOL = "⊤"
    BOTTOM_SYMBOL = "⊥"

    def __init__(self, value):
        """
        Construct a bounded lattice element with the given value.

        Args:
          value: the value this lattice element should take.
        """
        super().__init__(value)

    @classmethod
    def meet_all(cls,
                 elements: t.Iterable['BoundedLatticeElement']) -> 'BoundedLatticeElement':
        """
        Take the meet of all elements in the given sequence.
        An empty sequence produces Top.
        """
        return super().meet_all(elements, cls.top())

    @classmethod
    def join_all(cls,
                 elements: t.Iterable['BoundedLatticeElement']) -> 'BoundedLatticeElement':
        """
        Take the join of all elements in the given sequence.
        An empty sequence produces Bottom.
        """
        return super().join_all(elements, cls.bottom())

    @property
    def is_top(self):
        """True if this element is Top."""
        return self.value == self._top_val()

    @property
    def is_bottom(self):
        """True if this element is Bottom."""
        return self.value == self._bottom_val()

    def __str__(self):
        if self.is_top:
            return self.TOP_SYMBOL
        elif self.is_bottom:
            return self.BOTTOM_SYMBOL
        else:
            return str(self.value)

    @abc.abstractclassmethod
    def _top_val(cls):
        """Return the Top value of this lattice."""

    @abc.abstractclassmethod
    def _bottom_val(cls):
        """Return the Bottom value of this lattice."""

    @classmethod
    def top(cls) -> 'BoundedLatticeElement':
        """Return the Top lattice element."""
        return cls(cls._top_val())

    @classmethod
    def bottom(cls) -> 'BoundedLatticeElement':
        """Return the Bottom lattice element."""
        return cls(cls._bottom_val())

    def widen_to_top(self):
        """Set this element's value to Top without changing anything else."""
        self.value = self._top_val()


class IntLatticeElement(BoundedLatticeElement):
    """
    An element of the lattice defined by augmenting
    the (unordered) set of integers with top and bottom elements.

    Integers are incomparable with one another, while Top and Bottom
    compare superior and inferior with every other element, respectively.
    """

    def __init__(self, value: int):
        """
        Args:
          value: the integer this element contains, if it is not Top or Bottom.
        """
        super().__init__(value)

    def is_int(self) -> bool:
        """True iff this lattice element is neither Top nor Bottom."""
        return not (self.is_top or self.is_bottom)

    def __add__(self, other):
        if self.is_int() and other.is_int():
            return IntLatticeElement(self.value + other.value)
        return self.bottom()

    @classmethod
    def _top_val(cls):
        return cls.TOP_SYMBOL

    @classmethod
    def _bottom_val(cls):
        return cls.BOTTOM_SYMBOL

    @classmethod
    def meet(cls,
             a: 'IntLatticeElement', b: 'IntLatticeElement') -> 'IntLatticeElement':
        """Return the infimum of the given elements."""

        if a.is_bottom or b.is_bottom:
            return cls.bottom()

        if a.is_top:
            return copy(b)
        if b.is_top:
            return copy(a)
        if a.value == b.value:
            return copy(a)

        return cls.bottom()

    @classmethod
    def join(cls,
             a: 'IntLatticeElement', b: 'IntLatticeElement') -> 'IntLatticeElement':
        """Return the supremum of the given elements."""

        if a.is_top or b.is_top:
            return cls.top()

        if a.is_bottom:
            return copy(b)
        if b.is_bottom:
            return copy(a)
        if a.value == b.value:
            return copy(a)

        return cls.top()


class SubsetLatticeElement(BoundedLatticeElement):
    """
    A subset lattice element. The top element is the complete set of all
    elements, the bottom is the empty set, and other elements are subsets of top.
    """

    def __init__(self, value: t.Iterable):
        """
        Args:
          value: an iterable of elements which will compose the value of this
                 lattice element. It will be converted to a set, so duplicate
                 elements and ordering are ignored.
        """
        super().__init__(set(value))

    def __len__(self):
        if self.is_top:
            # TODO: determine if this is the right thing here. TOP has unbounded size.
            return 0
        return len(self.value)

    def __iter__(self):
        if self.is_top:
            raise TypeError("Top lattice element cannot be iterated.")
        return iter(self.value)

    def map(self, f: types.FunctionType) -> 'SubsetLatticeElement':
        """
        Return the result of applying a function to each of this element's values.

        Incidentally, this could be seen as special case of cartesian_map().
        """
        if self.is_top:
            return copy(self)
        return type(self)([f(val) for val in self.value])

    @classmethod
    def cartesian_map(cls, f: types.FunctionType,
                      elements: t.Iterable['SubsetLatticeElement']) \
        -> 'SubsetLatticeElement':
        """
        Apply the given function to each tuple of members in the product of the
        input elements, and return the resulting lattice element.

        The function's arity must match the number of input elements.
        For example, for a binary function, and input elements a, b, the result is
        the element defined by the set f(u, v) for each u in a, v in b.
        """

        # Symbolic manipulations could be performed here as some operations might
        # constrain the results, even if some input set is unconstrained.
        if any([e.is_top for e in elements]):
            return cls.top()

        prod = itertools.product(*(list(e) for e in elements))
        return cls([f(*args) for args in prod])

    @classmethod
    def _top_val(cls):
        return set(cls.TOP_SYMBOL)

    @classmethod
    def _bottom_val(cls):
        return set()

    @classmethod
    def meet(cls, a: 'SubsetLatticeElement',
             b: 'SubsetLatticeElement') -> 'SubsetLatticeElement':
        """Return the set intersection of the given elements."""
        if a.is_top:
            return copy(b)
        if b.is_top:
            return copy(a)

        return cls(a.value & b.value)

    @classmethod
    def join(cls, a: 'SubsetLatticeElement',
             b: 'SubsetLatticeElement') -> 'SubsetLatticeElement':
        """Return the set union of the given elements."""
        if a.is_top or b.is_top:
            return cls.top()

        return cls(a.value | b.value)

    @property
    def is_const(self) -> bool:
        """True iff this variable has exactly one possible value."""
        return self.is_finite and len(self) == 1

    @property
    def is_finite(self) -> bool:
        """
        True iff this variable has a finite and nonzero number of possible values.
        """
        return not (self.is_top or self.is_bottom)
