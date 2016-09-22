"""lattice.py: define lattices for use in meet-over-paths calculations."""

import typing
import functools
import abc


class BoundedLatticeElement(abc.ABC):
  @abc.abstractmethod
  def __init__(self, value, top:bool=False, bottom:bool=False):
    """Construct a lattice element with the given value."""
    self.value = value
    self.is_top = top
    self.is_bottom = bottom

    if top:
      self.value = "⊤"
    elif bottom or not self.is_num():
      self.value = "⊥"

  def __eq__(self, other) -> bool:
    return self.value == other.value

  def __str__(self) -> str:
    return str(self.value)

  def __repr__(self) -> str:
    return "<{0} object {1}, {2}>".format(
      self.__class__.__name__,
      hex(id(self)),
      self.__str__()
    )

  @classmethod
  def top(cls):
    return cls(top=True)

  @classmethod
  def bottom(cls):
    return cls(bottom=True)

  @abc.abstractclassmethod
  def meet(cls, a:'BoundedLatticeElement',
           b:'BoundedLatticeElement') -> 'BoundedLatticeElement':
    """Return the infimum of the given elements."""

  @classmethod
  def meet_all(cls, elements:typing.Iterable['BoundedLatticeElement']) \
    -> 'BoundedLatticeElement':
    """Return the infimum of the given iterable of elements."""
    return functools.reduce(
      lambda a, b: cls.meet(a, b),
      elements,
      cls.top()
    )

  @abc.abstractclassmethod
  def join(cls, a:'BoundedLatticeElement',
           b:'BoundedLatticeElement') -> 'BoundedLatticeElement':
    """Return the infimum of the given elements."""

  @classmethod
  def join_all(cls, elements:typing.Iterable['BoundedLatticeElement']) \
    -> 'BoundedLatticeElement':
    """Return the supremum of the given iterable of elements."""
    return functools.reduce(
      lambda a, b: cls.join(a, b),
      elements,
      cls.bottom()
    )


class IntLatticeElement(BoundedLatticeElement):
  """An element of the meet-semilattice defined by augmenting
  the (unordered) set of integers with top and bottom elements.

  Integers are incomparable with one another, while top and bottom
  compare superior and inferior with every other element, respectively."""

  def __init__(self, value:int=None, top:bool=False, bottom:bool=False) -> None:
    super().__init__(value, top, bottom)

  def is_num(self) -> bool:
    """True iff the value of this element is an integer."""
    return isinstance(self.value, int)

  def __add__(self, other):
    if self.is_num() and other.is_num():
      return IntLatticeElement(self.value + other.value)
    if self.is_bottom or other.is_bottom:
      return self.bottom()
    return self.top()

  @classmethod
  def meet(cls, a:'IntLatticeElement', b:'IntLatticeElement') -> 'IntLatticeElement':
    """Return the infimum of the given elements."""

    if a.is_bottom or b.is_bottom:
      return cls.bottom()

    if a.is_top:
      return b
    if b.is_top:
      return a
    if a.value == b.value:
      return a

    return cls.bottom()

  @classmethod
  def join(cls, a:'IntLatticeElement', b:'IntLatticeElement') -> 'IntLatticeElement':
    """Return the supremum of the given elements."""

    if a.is_top or b.is_top:
      return cls.top()

    if a.is_bottom:
      return b
    if b.is_bottom:
      return a
    if a.value == b.value:
      return a

    return cls.bottom()

