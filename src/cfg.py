"""cfg.py: Base classes for representing Control Flow Graphs (CFGs)"""

import abc
import typing as T

import patterns

class ControlFlowGraph(patterns.Visitable):
  """Abstract base class for a Control Flow Graph (CFG)"""

  __STR_SEP = "\n\n-----\n\n"

  @abc.abstractmethod
  def __init__(self):
    """Create a new empty ControlFlowGraph"""

    self.blocks = []
    """List of BasicBlock objects"""

    self.root = None
    """The root BasicBlock object, or None for the empty graph"""

  def __len__(self):
    return len(self.blocks)

  def __str__(self):
    return self.__STR_SEP.join(str(b) for b in self.blocks)

  def edge_list(self) -> T.Iterable[T.Tuple['BasicBlock', 'BasicBlock']]:
    """
    Returns:
      a list of the CFG's edges, with each edge in the form
        ( pred, succ )
    """
    return [(p, s) for p in self.blocks for s in p.succs]

  def accept(self, visitor:patterns.Visitor):
    """
    Visitor design pattern: accepts a Visitor instance and visits every node
    in the CFG in an arbitrary order.

    Args:
      visitor: instance of a Visitor
    """
    super().accept(visitor)

    if visitor.can_visit(BasicBlock):
      for b in self.blocks:
        b.accept(visitor)


class BasicBlock(patterns.Visitable):
  """
  Abstract base class for a single basic block (node) in a CFG. Each block has
  references to its predecessor and successor nodes in the graph structure.

  A BasicBlock must contain exactly one entry point at the start and
  exactly one exit point at the end, with no branching in between.
  That is, program flow must be linear/sequential within a basic block.

  Args:
    entry (int, default None): entry index.
    exit (int, default None): exit index.

  Raises:
    ValueError: if entry or exit is a negative int.
  """

  _STR_SEP = "---"

  @abc.abstractmethod
  def __init__(self, entry:int=None, exit:int=None):
    if entry is not None and entry < 0:
      raise ValueError("entry must be a positive integer or zero")

    if exit is not None and exit < 0:
      raise ValueError("exit must be a positive integer or zero")

    self.entry = entry
    """Index of the first operation contained in this node."""

    self.exit = exit
    """Index of the last operation contained in this node."""

    self.preds = []
    """List of nodes which pass control to this node (predecessors)."""

    self.succs = []
    """List of nodes which receive control from this node (successors)."""

    self.has_unresolved_jump = False
    """True if the node contains a jump whose destination is a variable."""

  def __len__(self):
    """Returns the number of lines of code contained within this block."""
    return self.exit - self.entry

  def __str__(self):
    entry, exit = map(lambda n: hex(n) if n is not None else 'Unknown',
                      (self.entry, self.exit))
    head = "Block [{}:{}]".format(entry, exit)
    pred = "Predecessors: [{}]".format(", ".join(b.ident() for b in self.preds))
    succ = "Successors: [{}]".format(", ".join(b.ident() for b in self.succs))
    unresolved = "\nHas unresolved jump." if self.has_unresolved_jump else ""
    return "\n".join([head, self._STR_SEP, pred, succ]) + unresolved

  def ident(self) -> str:
    """
    Returns this block's unique identifier, which is its entry value.

    Raises:
      ValueError if the block's entry is None.
    """
    if self.entry is None:
      raise ValueError("Can't compute ident() for block with unknown entry")
    return hex(self.entry)
