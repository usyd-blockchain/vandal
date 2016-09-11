"""cfg.py: Base classes for representing Control Flow Graphs (CFGs)"""

class ControlFlowGraph:
  """Generic Control Flow Graph (CFG)"""
  def __init__(self):
    """List of CFGNode objects"""
    self.blocks = []
    """The root CFGNode object, or None for the empty graph"""
    self.root = None

  def __len__(self):
    return len(self.blocks)

  def __str__(self):
    return "\n".join(str(b) for b in self.blocks)

  def edge_list(self):
    """Returns a list of the CFG's edges in the form (pred, succ)."""
    return [(p,s) for s in p.successors for p in self.blocks]

class CFGNode:
  """
  Represents a single basic block (node) in a control flow graph (CFG),
  including references to its predecessor and successor nodes in the graph
  structure.
  """

  # Separator to be used for string representation of blocks
  __BLOCK_SEP = "\n---"

  def __init__(self, start:int=None, end:int=None):
    """
    Creates a new CFG node containing code lines between the
    specified start index and the specified end index (inclusive).
    """
    self.start = start
    self.end = end
    """List of CodeLines contained in this node"""
    self.lines = []
    """List of CFGNodes which pass control to this node"""
    self.predecessors = []
    """List of CFGNodes which receive control from this node"""
    self.successors = []

  def __len__(self):
    """Returns the number of lines of code contained within this block."""
    return self.end - self.start

  def __str__(self):
    """Returns a string representation of this block and all lines in it."""
    return "\n".join(str(l) for l in self.lines) + self.__BLOCK_SEP

  def __hash__(self):
    return id(self)

  def split(self, start:int) -> 'CFGNode':
    """
    Splits this CFGNode into a new CFGNode, from at the specified
    start line number. Returns the new CFGNode.
    """
    # Create the new block and assign the code line ranges
    new = type(self)(start, self.end)
    self.end = start - 1

    # Split the code lines between the two nodes
    new.lines = self.lines[start-self.start:]
    self.lines = self.lines[:start-self.start]

    return new
