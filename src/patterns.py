"""patterns.py: abstract base classes for the various design patterns"""

import abc
import inspect

class Visitable(abc.ABC):
  """
  Provides an interface for an object which can accept a :obj:`Visitor`.
  """
  def accept(self, visitor:'Visitor'):
    """
    Accepts a :obj:`Visitor` and calls :obj:`Visitor.visit`

    Args:
      visitor: the :obj:`Visitor` to accept
    """
    visitor.visit(self)


class Visitor(abc.ABC):
  """
  Visitor design pattern abstract base class.
  """
  @abc.abstractmethod
  def visit(self, target:Visitable, *args, **kwargs):
    """
    Visits the given object.

    Args:
      target: object to visit.
    """


class DynamicVisitor(Visitor):
  """
  Visitor base class which dynamically calls a specialised visit method based
  on the target's type at runtime.

  Example:
    Subclassing :obj:`DynamicVisitor`::

      class PrinterDynamicVisitor(DynamicVisitor):
        def visit_str(self, string:str):
          print(string)

        def visit_int(self, integer:int):
          print("{:08b}".format(integer))

        def visit_object(self, obj:object):
          print(obj)

      pdv = PrinterDynamicVisitor()
      pdv.visit("hello")
      pdv.visit(5)
  """

  def __init__(self):
    super().__init__()

    # Don't allow instantiation of DynamicVisitor itself
    if type(self) is DynamicVisitor:
      raise NotImplementedError("DynamicVisitor must be sub-classed")

  def visit(self, target:Visitable, *args, **kwargs):
    """
    Dispatches to a method called visit_TYPE where TYPE is the dynamic type
    (or the nearest parent type) of the `target`.

    Args:
      target: object to visit.
      *args: arguments to be passed to the type-specific visit method.
      **kwargs: optional/keyword arguments to be passed to the type-specific
        visit method.
    """
    # Try all the type names in the target's MRO
    for base in inspect.getmro(type(target)):
      visit_name = "visit_{}".format(base.__name__)

      # If we found a matching visit_TYPE method, call it
      if hasattr(self, visit_name):
        visit_method = getattr(self, visit_name)
        return visit_method(target, *args, **kwargs)

    # If no matching visit_TYPE method exists, call _no_visit_found
    return self._no_visit_found(target, *args, **kwargs)

  def _no_visit_found(self, target, *args, **kwargs):
    """
    Called when no matching visit_TYPE method exists for the target's type.
    Raises a TypeError by default and should be overridden if different
    behaviour is desired by a derived class.

    Args:
      target: object passed to :obj:`visit`
      *args: arguments passed to :obj:`visit`
      **kwargs: keyword arguments passed to :obj:`visit`

    Raises:
      TypeError
    """
    raise TypeError("could not find a visit method for target type {}"
                    .format(type(target).__name__))
