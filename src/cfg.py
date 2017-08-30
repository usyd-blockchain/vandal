"""cfg.py: Base classes for representing Control Flow Graphs (CFGs)"""

import abc
import typing as t
import logging

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

  def remove_block(self, block:'BasicBlock') -> None:
    """
    Remove the given block from the graph, disconnecting all incident edges.
    """
    if block == self.root:
      self.root = None

    for p in list(block.preds):
      self.remove_edge(p, block)
    for s in list(block.succs):
      self.remove_edge(block, s)

    self.blocks.remove(block)

  def add_block(self, block:'BasicBlock') -> None:
    """
    Add the given block to the graph, assuming it does not already exist.
    """
    if block not in self.blocks:
      self.blocks.append(block)

  def has_edge(self, head:'BasicBlock', tail:'BasicBlock') -> bool:
    """
    True iff the edge between head and tail exists in the graph.
    """
    return tail in head.succs

  def remove_edge(self, head:'BasicBlock', tail:'BasicBlock') -> None:
    """Remove the CFG edge that goes from head to tail."""
    if tail in head.succs:
      head.succs.remove(tail)
    if head in tail.preds:
      tail.preds.remove(head)

  def add_edge(self, head:'BasicBlock', tail:'BasicBlock'):
    """Add a CFG edge that goes from head to tail."""
    if tail not in head.succs:
      head.succs.append(tail)
    if head not in tail.preds:
      tail.preds.append(head)

  def get_blocks_by_pc(self, pc:int) -> t.List['BasicBlock']:
    """Return the blocks whose spans include the given program counter value."""
    blocks = []
    for block in self.blocks:
      if block.entry <= pc <= block.exit:
        blocks.append(block)
    return blocks

  def get_block_by_ident(self, ident:str) -> 'BasicBlock':
    """Return the block with the specified identifier, if it exists."""
    for block in self.blocks:
      if block.ident() == ident:
        return block
    return None

  def recalc_preds(self) -> None:
    """
    Given a cfg where block successor lists are populated,
    also repopulate the predecessor lists, after emptying them.
    """
    for block in self.blocks:
      block.preds = []
    for block in self.blocks:
      for successor in block.succs:
        successor.preds.append(block)

  def transitive_closure(self, origin_addresses:t.Iterable[int]) \
  -> t.Iterable['BasicBlock']:
    """
    Return a list of blocks reachable from the input addresses.

    Args:
        origin_addresses: the input addresses blocks from which are reachable
                          to be returned.
    """

    # Populate the work queue with the origin blocks for the transitive closure.
    queue = []
    for address in origin_addresses:
      for block in self.get_blocks_by_pc(address):
        if block not in queue:
          queue.append(block)
    reached = []

    # Follow all successor edges until we can find no more new blocks.
    while queue:
      block = queue.pop()
      reached.append(block)
      for succ in block.succs:
        if succ not in queue and succ not in reached:
          queue.append(succ)

    return reached

  def remove_unreachable_code(self, origin_addresses:t.Iterable[int]=[0]) \
  -> t.Iterable['BasicBlock']:
    """
    Remove all blocks not reachable from the program entry point.

    NB: if not all jumps have been resolved, unreached blocks may actually
    be reachable.

    Args:
        origin_addresses: default value: [0], entry addresses, blocks from which
                          are unreachable to be deleted.

    Returns:
        An iterable of the blocks which were removed.
    """

    reached = self.transitive_closure(origin_addresses)
    removed = []
    for block in list(self.blocks):
      if block not in reached:
        removed.append(block)
        self.remove_block(block)
    return removed

  def edge_list(self) -> t.Iterable[t.Tuple['BasicBlock', 'BasicBlock']]:
    """
    Returns:
      a list of the CFG's edges, with each edge in the form
      `(pred, succ)` where pred and succ are object references.
    """
    return [(p, s) for p in self.blocks for s in p.succs]

  def sorted_traversal(self, key=lambda b: b.entry, reverse=False) -> t.Generator['BasicBlock', None, None]:
    """
    Generator for a sorted shallow copy of BasicBlocks contained in this graph.

    Args:
      key: A function of one argument that is used to extract a comparison key
        from each block. By default, the comparison key is
        :obj:`BasicBlock.entry`.
      reverse: If set to `True`, then the blocks are sorted as if each
        comparison were reversed. Default is `False`.

    Returns:
      A generator of :obj:`BasicBlock` objects, yielded in order according to
      `key` and `reverse`.
    """
    # Create a new list of sorted blocks and yield from it
    yield from sorted(self.blocks, key=key, reverse=reverse)

  def accept(self, visitor:patterns.Visitor,
             generator:t.Generator['BasicBlock', None, None]=None):
    """
    Visitor design pattern: accepts a Visitor instance and visits every node
    in the CFG in an arbitrary order.

    Args:
      visitor: instance of a Visitor
      generator: generator from which :obj:`BasicBlock` objects will be
        retrieved when recursing. By default the blocks are recursed in
        an arbitrary order.
    """
    super().accept(visitor)

    generator = generator or self.blocks

    if len(self.blocks) > 0 and visitor.can_visit(type(self.blocks[0])):
      for b in generator:
        b.accept(visitor)

  @property
  def has_unresolved_jump(self) -> bool:
    """True iff any block in this cfg contains an unresolved jump."""
    return any(b.has_unresolved_jump for b in self.blocks)


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

    self.ident_suffix = ""
    """
    Extra information to be appended to this block's identifier.
    Used, for example, to differentiate duplicated blocks.
    """

  def __len__(self):
    """Returns the number of lines of code contained within this block."""
    if self.exit is None or self.entry is None:
      return 0
    return self.exit - self.entry

  def __str__(self):
    entry, exit = map(lambda n: hex(n) if n is not None else 'Unknown',
                      (self.entry, self.exit))
    b_id = self.ident() if self.entry is not None else "Unidentified"
    head = "Block {}\n[{}:{}]".format(b_id, entry, exit)
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
    return hex(self.entry) + self.ident_suffix
