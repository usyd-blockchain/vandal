"""lattice.py: define lattices for use in meet-over-paths calculations."""

import typing
import functools

class IntLatticeElement:
  """An element of the meet-semilattice defined by augmenting
  the (unordered) set of integers with top and bottom elements.

  Integers are incomparable with one another, while top and bottom
  compare superior and inferior with every other element, respectively."""

  def __init__(self, value:int=None, top:bool=False, bottom:bool=False) -> None:
    """Construct a lattice element with the given value."""
    self.value = value
    self.is_top = top
    self.is_bottom = bottom

    if top:
      self.value = "TOP"
    elif bottom or not self.is_num():
      self.value = "BOTTOM"

  def is_num(self) -> bool:
    """True iff the value of this element is an integer."""
    return isinstance(self.value, int)

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

  def __add__(self, other):
    if self.is_num() and other.is_num():
      return IntLatticeElement(self.value + other.value)
    if self.is_bottom or other.is_bottom:
      return self.bottom()
    return self.top()

  @classmethod
  def top(cls):
    return cls(top=True)

  def bottom(cls):
    return cls(bottom=True)

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
  def meet_all(cls, elements:typing.List['IntLatticeElement']) -> 'IntLatticeElement':
    """Return the infimum of the given iterable of elements."""
    return functools.reduce(
      lambda a, b: cls.meet(a, b),
      elements,
      cls.top()
    )