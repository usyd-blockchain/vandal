"""patterns.py: abstract base classes for the various design patterns"""

import abc

class Visitor(abc.ABC):
  """
  Visitor design pattern abstract base class.
  """
  @abc.abstractmethod
  def visit(self, guest:object):
    """
    Visits the given object instance.

    Args:
      guest: object instance to be visited.
    """
