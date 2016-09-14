"""cfg.py: Base classes for representing Control Flow Graphs (CFGs)"""

import abc
import patterns

class ControlFlowGraph(abc.ABC):
  """Abstract base class for a Control Flow Graph (CFG)"""

  __STR_SEP = "\n-----\n"

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

  def edge_list(self):
    """Returns a list of the CFG's edges in the form (pred, succ)."""
    return [(p.ident(),s.ident()) for p in self.blocks for s in p.succs]

  def accept(self, visitor:patterns.Visitor):
    """
    Visitor design pattern: accepts a Visitor instance and visits every node
    in the CFG in an arbitrary order.

    Args:
      visitor: instance of a Visitor
    """
    for b in self.blocks:
      b.accept(visitor)


class BasicBlock(abc.ABC):
  """
  Abstract base class for a single basic block (node) in a CFG. Each block has
  references to its predecessor and successor nodes in the graph structure.
  """

  _STR_SEP = "---"

  @abc.abstractmethod
  def __init__(self, entry:int=None, exit:int=None):
    """
    Creates a new CFG node containing code operations between the
    specified entry index and the specified exit index (inclusive).
    """

    self.entry = entry
    """Index of the first operation contained in this node."""

    self.exit = exit
    """Index of the last operation contained in this node."""

    self.preds = []
    """List of nodes which pass control to this node (predecessors)."""

    self.succs = []
    """List of nodes which receive control from this node (successors)."""

    self.has_unresolved_jump = False
    """True if the node contains a jump whose destination is computed."""

  def __len__(self):
    """Returns the number of lines of code contained within this block."""
    return self.exit - self.entry

  def __hash__(self):
    return id(self)

  def __str__(self):
    head = "Block {} - {}".format(hex(entry), hex(exit))
    pred = "Predecessors: [{}]".format(", ".join(b.ident() for b in self.preds))
    succ = "Successors: [{}]".format(", ".join(b.ident() for b in self.succs))
    unresolved = "\nHas unresolved jump." if self.has_unresolved_jump else ""
    return "\n".join([head, self._STR_SEP, pred, succ]) + unresolved

  def ident(self) -> str:
    """Returns this block's unique identifier, which is the index of its first
    operation, as a hex string."""
    return hex(self.entry)

  def accept(self, visitor:patterns.Visitor):
    """
    Visitor design pattern: accepts a Visitor instance and visits this node.

    Args:
      visitor: instance of a Visitor
    """
    visitor.visit(self)
