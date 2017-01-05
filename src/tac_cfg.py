"""tac_cfg.py: Definitions of Three-Address Code operations and related
objects."""

import typing as t
import copy

import opcodes
import cfg
import evm_cfg
import memtypes as mem
import blockparse
import patterns
from lattice import SubsetLatticeElement as ssle


class TACGraph(cfg.ControlFlowGraph):
  """
  A control flow graph holding Three-Address Code blocks and
  the edges between them.
  """

  def __init__(self, evm_blocks:t.Iterable[evm_cfg.EVMBasicBlock]):
    """
    Construct a TAC control flow graph from a given sequence of EVM blocks.
    Immediately after conversion, constants will be propagated and folded
    through arithmetic operations, and CFG edges will be connected up, wherever
    they can be inferred.

    Args:
      evm_blocks: an iterable of EVMBasicBlocks to convert into TAC form.
    """
    super().__init__()

    # Convert the input EVM blocks to TAC blocks.
    destack = Destackifier()

    self.blocks = [destack.convert_block(b) for b in evm_blocks]
    """The sequence of TACBasicBlocks contained in this graph."""
    for b in self.blocks:
      b.cfg = self

    self.root = next((b for b in self.blocks if b.entry == 0), None)
    """The root block of this CFG. The entry point will always be at index 0, if it exists."""

    self.split_node_succs = {}
    """
    A mapping from addresses to addresses storing all successors of a
    block at the time it was split. At merge time these edges can be restored.
    """

    # Propagate constants and add CFG edges.
    self.apply_operations()
    self.hook_up_jumps()

  @classmethod
  def from_dasm(cls, dasm:t.Iterable[str]) -> 'TACGraph':
    """
    Construct and return a TACGraph from the given EVM disassembly.

    Args:
      dasm: a sequence of disasm lines, as output from the
            ethereum `dasm` disassembler.
    """
    return cls(blockparse.EVMDasmParser(dasm).parse())

  @classmethod
  def from_bytecode(cls, bytecode:t.Iterable, strict:bool=False) -> 'TACGraph':
    """
    Construct and return a TACGraph from the given EVM bytecode.

    Args:
      bytecode: a sequence of EVM bytecode, either in a hexidecimal
        string format or a byte array.
    """
    bytecode = ''.join([l.strip() for l in bytecode if len(l.strip()) > 0])
    return cls(blockparse.EVMBytecodeParser(bytecode).parse(strict))

  def apply_operations(self, use_sets=False) -> None:
    """
    Propagate and fold constants through the arithmetic TAC instructions
    in this CFG.

    If use_sets is True, folding will also be done on Variables that
    possess multiple possible values, performing operations in all possible
    combinations of values.
    """
    for block in self.blocks:
      block.apply_operations(use_sets)

  def hook_up_stack_vars(self) -> None:
    """
    Replace all stack MetaVariables will be replaced with the actual
    variables they refer to.
    """
    for block in self.blocks:
      block.hook_up_stack_vars()

  def hook_up_def_site_jumps(self) -> None:
    """
    Add jumps to blocks with unresolved jumps if they can be inferred
    from the jump variable's definition sites.
    """
    for block in self.blocks:
      block.hook_up_def_site_jumps()

  def hook_up_jumps(self,
                    mutate_jumps:bool=False,
                    generate_throws:bool=False) -> bool:
    """
    Connect all edges in the graph that can be inferred given any constant
    values of jump destinations and conditions.
    Invalid jumps are replaced with THROW instructions.

    This is assumed to be performed after constant propagation and/or folding,
    since edges are deduced from constant-valued jumps.

    Note that mutate_jumps and generate_throws should likely be true only in
    the final iteration of a dataflow analysis, at which point as much
    jump destination information as possible has been propagated around.
    If these are used too early, they may prevent valid edges from being added
    later on.

    Args:
       mutate_jumps: JUMPIs with known conditions become JUMPs (or are deleted)
       generate_throws: JUMP and JUMPI instructions with invalid destinations
                        become THROW and THROWIs

    Returns:
        True iff any edges in the graph were modified.
    """

    modified = False

    for block in self.blocks:
      modified |= block.hook_up_jumps(mutate_jumps=mutate_jumps,
                                      generate_throws=generate_throws)

    return modified

  def add_missing_split_edges(self):
    """
    If this graph has had its nodes split, if new edges are inferred,
    we need to join them up to all copies of a node, but the split
    paths should remain separate, so only add such edges if parallel ones
    don't already exist.
    """
    for pred_address in self.split_node_succs:
      preds = self.get_blocks_by_pc(pred_address)
      s_lists = [node.succs for node in preds]
      succs = set(s for succ_list in s_lists for s in succ_list)
      for succ in self.split_node_succs[pred_address]:
        if succ not in succs:
          for pred in preds:
            self.add_edge(pred, succ)

  def is_valid_jump_dest(self, pc:int) -> bool:
    """True iff the given program counter refers to a valid jumpdest."""
    ops = self.get_ops_by_pc(pc)
    return (len(ops) != 0) and any(op.opcode == opcodes.JUMPDEST for op in ops)

  def get_ops_by_pc(self, pc:int) -> 'TACOp':
    """Return the operations with the given program counter, if any exist."""
    ops = []

    for block in self.get_blocks_by_pc(pc):
      for op in block.tac_ops:
        if op.pc == pc:
          ops.append(op)

    return ops

  def clone_ambiguous_jump_blocks(self) -> None:
    """
    If block terminates in a jump with an ambiguous (but constrained)
    jump destination, then find its most recent ancestral confluence point
    and split the chain of blocks between into parallel chains, one for each
    predecessor of the block at the confluence point.
    """

    modified = True
    skip = set()

    while modified:
      modified = False

      for block in self.blocks:

        # Don't split on blocks we only just generated; some will
        # certainly satisfy the fission condition.
        if block in skip:
          continue

        if len(block.tac_ops) == 0:
          continue

        final_op = block.tac_ops[-1]

        if final_op.opcode not in [opcodes.JUMP, opcodes.JUMPI]:
          continue

        # We will only split if there were actually multiple jump destinations
        # defined in multiple different blocks.
        dests = final_op.args[0].value
        if dests.is_const or dests.def_sites.is_const \
            or (dests.is_top and dests.def_sites.is_top):
          continue

        # We satisfy the conditions for attempting a split.
        chain = [block]
        curr_block = block
        cycle = False

        while len(curr_block.preds) == 1:
          curr_block = curr_block.preds[0]

          if curr_block not in chain:
            chain.append(curr_block)
          else:
            # We are in a cycle, break out
            cycle = True
            break

        chain_preds = list(curr_block.preds)

        if cycle or len(chain_preds) == 0:
          continue

        # If there's a cycle within the chain, die
        # TODO See what happens if we copy these cycles
        if any(pred in chain for pred in chain_preds):
          continue

        # We have identified a splittable chain, now split it

        # Remove the old chain from the graph.
        # Note well that this deletion will remove all edges to successors
        # of elements of this chain, so we can lose information.
        for b in chain:
          # Save the edges of each block in case they can't be reinferred.
          # They will be added back in at a later stage.
          if b.entry not in self.split_node_succs:
            self.split_node_succs[b.entry] = [s for s in b.succs]
          else:
            new_list = self.split_node_succs[b.entry]
            new_list += [s for s in b.succs if s not in new_list]
            self.split_node_succs[b.entry] = new_list

          skip.add(b)
          self.remove_block(b)

        # copy the chains
        chain_copies = [[copy.deepcopy(b) for b in chain]
                  for _ in range(len(chain_preds))]

        # Copy the nodes properly in the split node succs mapping.
        for i, b in enumerate(chain):
          for a in self.split_node_succs:
            node_copies = [c[i] for c in chain_copies]
            if b in self.split_node_succs[a]:
              self.split_node_succs[a].remove(b)
              self.split_node_succs[a] += node_copies


        # hook up each pred to a chain individually.
        for i, p in enumerate(chain_preds):
          self.add_edge(p, chain_copies[i][-1])
          for b in chain_copies[i]:
            b.ident_suffix += "_" + p.ident()

        # Connect the chains up within themselves
        for chain_copy in chain_copies:
          for i in range(len(chain_copy) - 1):
            self.add_edge(chain_copy[i+1], chain_copy[i])

        # Add the new chains to the graph.
        for c in chain_copies:
          for b in c:
            skip.add(b)
            self.add_block(b)

        modified = True

  def merge_duplicate_blocks(self,
                             ignore_preds:bool=False,
                             ignore_succs:bool=False) -> None:
    """
    Blocks with the same addresses are merged if they have the same
    in and out edges.

    Input blocks will have their stacks joined, while pred and succ lists
    are the result of the the union of the input lists.

    It is assumed that the code of the duplicate blocks will be the same,
    which is to say that they can only differ by their entry/exit stacks,
    and their incident CFG edges.

    Args:
        ignore_preds: blocks will be merged even if their predecessors differ.
        ignore_succs: blocks will be merged even if their successors differ.
    """

    # Define an equivalence relation over basic blocks.
    # Blocks deemed equivalent by this function will be merged.
    def blocks_equal(a, b):
      if a.entry != b.entry:
        return False
      if not ignore_preds and set(a.preds) != set(b.preds):
        return False
      if not ignore_succs and set(a.succs) != set(b.succs):
        return False
      return True

    modified = True

    while modified:
      modified = False

      groups = []
      merged_blocks = []

      # Group equivalent blocks together into lists.
      for block in self.blocks:
        grouped = False
        for group in groups:
          if blocks_equal(block, group[0]):
            grouped = True
            group.append(block)
            break
        if not grouped:
          groups.append([block])

      # Remove blocks that are in groups by themselves.
      groups = [g for g in groups if len(g) > 1]

      if len(groups) > 0:
        modified = True

      # Merge each group into a single new block.
      for i, group in enumerate(groups):
        entry_stack = mem.VariableStack.join_all([b.entry_stack for b in group])
        entry_stack.metafy()
        exit_stack = mem.VariableStack.join_all([b.exit_stack for b in group])
        exit_stack.metafy()
        symbolic_overflow = any([b.symbolic_overflow for b in group])
        has_unresolved_jump = any([b.has_unresolved_jump for b in group])
        preds = set()
        succs = set()
        for b in group:
          preds |= set(b.preds)
          succs |= set(b.succs)

        new_block = copy.deepcopy(group[0])
        new_block.entry_stack = entry_stack
        new_block.exit_stack = exit_stack
        new_block.preds = list(preds)
        new_block.succs = list(succs)
        new_block.ident_suffix = "_" + str(i)
        new_block.symbolic_overflow = symbolic_overflow
        new_block.has_unresolved_jump = has_unresolved_jump

        merged_blocks.append(new_block)

        new_block.reset_block_refs()
        self.add_block(new_block)

        for pred in preds:
          self.add_edge(pred, new_block)
          for b in group:
            self.remove_edge(pred, b)
        for succ in succs:
          self.add_edge(new_block, succ)
          for b in group:
            self.remove_edge(b, succ)
        for b in group:
          self.remove_block(b)

        # If this block no longer has any duplicates in the graph,
        # then it no longer needs an ident suffix to disambiguate it.
        if len(self.get_blocks_by_pc(new_block.entry)) == 1:
          new_block.ident_suffix = ""

          for a in self.split_node_succs:
            s_list = self.split_node_succs[a]
            for g in [g for g in group if g in s_list]:
              s_list.remove(g)

          if new_block.entry in self.split_node_succs:
            for succ in self.split_node_succs[new_block.entry]:
              if succ not in new_block.succs:
                new_block.succs.append(succ)
            del self.split_node_succs[new_block.entry]

      # Recondition the graph, having merged everything.
      for block in self.blocks:
        block.build_entry_stack()
        block.build_exit_stack()
        block.hook_up_stack_vars()
        block.apply_operations()
        block.hook_up_jumps()


class TACBasicBlock(evm_cfg.EVMBasicBlock):
  """A basic block containing both three-address code, and its
  equivalent EVM code, along with information about the transformation
  applied to the stack as a consequence of its execution."""

  def __init__(self, entry_pc:int, exit_pc:int,
               tac_ops:t.Iterable['TACOp'],
               evm_ops:t.Iterable[evm_cfg.EVMOp],
               delta_stack:mem.VariableStack,
               cfg=None):
    """
    Args:
      entry_pc: The pc of the first byte in the source EVM block
      exit_pc: The pc of the last byte in the source EVM block
      tac_ops: A sequence of TACOps whose execution is equivalent to the source
               EVM code.
      evm_ops: the source EVM code.
      delta_stack: A stack describing the change in the stack state as a result
                   of running this block.
                   This stack contains the new items inhabiting the top of
                   stack after execution, along with the number of items
                   removed from the stack.
      cfg: The TACGraph to which this block belongs.

      Entry and exit variables should span the entire range of values enclosed
      in this block, taking care to note that the exit address may not be an
      instruction, but an argument of a PUSH.
      The range of pc values spanned by all blocks in a CFG should be a
      continuous range from 0 to the maximum value with no gaps between blocks.

      If the input stack state is known, obtain the exit stack state by
      popping off delta_stack.empty_pops items and add the delta_stack items
      to the top.
    """

    super().__init__(entry_pc, exit_pc, evm_ops)

    self.tac_ops = tac_ops
    """A sequence of TACOps whose execution is equivalent to the source EVM
       code"""

    self.delta_stack = delta_stack
    """
    A stack describing the stack state changes caused by running this block.
    MetaVariables named Sn symbolically denote the variable that was n places
    from the top of the stack at entry to this block.
    """

    self.entry_stack = mem.VariableStack()
    """Holds the complete stack state before execution of the block."""

    self.exit_stack = mem.VariableStack()
    """Holds the complete stack state after execution of the block."""

    self.symbolic_overflow = False
    """
    Indicates whether a symbolic stack overflow has occurred in dataflow
    analysis of this block.
    """

    self.cfg = cfg
    """The TACGraph to which this block belongs."""

  def __str__(self):
    super_str = super().__str__()
    op_seq = "\n".join(str(op) for op in self.tac_ops)
    entry_stack = "Entry stack: {}".format(str(self.entry_stack))
    stack_pops = "Stack pops: {}".format(self.delta_stack.empty_pops)
    stack_adds = "Stack additions: {}".format(str(self.delta_stack))
    exit_stack = "Exit stack: {}".format(str(self.exit_stack))
    return "\n".join([super_str, self._STR_SEP, op_seq, self._STR_SEP,
                      entry_stack, stack_pops, stack_adds, exit_stack])

  def accept(self, visitor:patterns.Visitor) -> None:
    """
    Accepts a visitor and visits itself and all TACOps in the block.

    Args:
      visitor: an instance of :obj:`patterns.Visitor` to accept.
    """
    super().accept(visitor)

    if visitor.can_visit(TACOp) or visitor.can_visit(TACAssignOp):
      for tac_op in self.tac_ops:
        visitor.visit(tac_op)

  def __deepcopy__(self, memodict={}):
    """Return a copy of this block."""

    new_block = TACBasicBlock(self.entry, self.exit,
                              copy.deepcopy(self.tac_ops, memodict),
                              [copy.copy(op) for op in self.evm_ops],
                              copy.deepcopy(self.delta_stack, memodict))

    new_block.has_unresolved_jump = self.has_unresolved_jump
    new_block.symbolic_overflow = self.symbolic_overflow
    new_block.entry_stack = copy.deepcopy(self.entry_stack, memodict)
    new_block.exit_stack = copy.deepcopy(self.exit_stack, memodict)
    new_block.preds = copy.copy(self.preds)
    new_block.succs = copy.copy(self.succs)
    new_block.ident_suffix = self.ident_suffix
    new_block.cfg = self.cfg

    new_block.reset_block_refs()

    return new_block

  def reset_block_refs(self) -> None:
    """Update all operations and new def sites to refer to this block."""

    for op in self.evm_ops:
      op.block = self
    for op in self.tac_ops:
      op.block = self
      if isinstance(op, TACAssignOp) and isinstance(op.lhs, mem.Variable):
        for site in op.lhs.def_sites:
          site.block = self

  def build_entry_stack(self) -> bool:
    """
    Construct this block's entry stack by joining all predecessor stacks.

    Returns:
        True iff the new stack is different from the old one.
    """
    old_stack = self.entry_stack
    pred_stacks = [pred.exit_stack for pred in self.preds]
    self.entry_stack = mem.VariableStack.join_all(pred_stacks)
    self.entry_stack.set_max_size(old_stack.max_size)
    self.entry_stack.metafy()

    return old_stack != self.entry_stack

  def build_exit_stack(self, die_on_empty_pop:bool=False,
                             skip_on_overflow:bool=True) -> bool:
    """
    Apply the transformation in this block's delta stack to construct its
    exit stack from its entry stack.

    Args:
      die_on_empty_pop: raise an exception if an empty stack is popped.
      skip_on_overflow: do not apply the changes to the exit stack
                        if a symbolic overflow occurred.

    Returns:
        True iff a symbolic overflow occurred.
    """
    overflow = False

    # If variables were obtained from deeper than there are extant
    # stack items, the program is possibly popping from an empty stack.
    if die_on_empty_pop \
       and (len(self.entry_stack) < self.delta_stack.empty_pops):
      raise RuntimeError("Popped empty stack in {}.".format(self.ident()))

    # If executing this block would overflow the stack, maybe skip it.
    delta = len(self.delta_stack) - self.delta_stack.empty_pops
    if (len(self.entry_stack) + delta) > self.exit_stack.max_size:
      self.symbolic_overflow = True
      if skip_on_overflow:
        return True
      overflow = True

    # Construct the new exit stack from the entry and delta stacks.
    exit_stack = self.entry_stack.copy()

    # Build a mapping from MetaVariables to the Variables they correspond to.
    metavar_map = {}
    for var in self.delta_stack:
      if isinstance(var, mem.MetaVariable):
        # Here we know the stack is full enough, given we've already checked it,
        # but we'll get a MetaVariable if we try grabbing something off the end.
        metavar_map[var] = exit_stack.peek(var.payload)

    # Construct the exit stack itself.
    exit_stack.pop_many(self.delta_stack.empty_pops)
    for var in list(self.delta_stack)[::-1]:
      if isinstance(var, mem.MetaVariable):
        exit_stack.push(metavar_map[var])
      else:
        exit_stack.push(var)

    self.exit_stack = exit_stack

    return overflow

  def hook_up_stack_vars(self) -> None:
    """
    Replace all stack MetaVariables will be replaced with the actual
    variables they refer to.
    """
    for op in self.tac_ops:
      for i in range(len(op.args)):
        if isinstance(op.args[i], TACArg):
          stack_var = op.args[i].stack_var
          if stack_var is not None:
            # If the required argument is past the end, don't replace the metavariable
            # as we would thereby lose information.
            if stack_var.payload < len(self.entry_stack):
              op.args[i].var = self.entry_stack.peek(stack_var.payload)

  def hook_up_def_site_jumps(self) -> None:
    """
    Add jumps to this block if they can be inferred from its jump variable's
    definition sites.
    """
    final_op = self.tac_ops[-1]
    if final_op.opcode in [opcodes.JUMP, opcodes.JUMPI]:
      dest = final_op.args[0].value
      vars = [d.get_instruction().lhs for d in dest.def_sites]
      non_top_vars = [v for v in vars if not v.is_top]

      existing_dests = [s.entry for s in self.succs]

      # join all values to obtain possible jump dests
      # add jumps to those locations if they are valid and don't already exist
      for d in mem.Variable.join_all(non_top_vars):
        if d in existing_dests or not self.cfg.is_valid_jump_dest(d):
          continue
        for b in self.cfg.get_blocks_by_pc(d):
          self.cfg.add_edge(self, b)

      # Jump still unresolved if some value was top or if empty successors
      # note that no_succs should hopefully cover the case where a variable
      # has no def sites (i.e. the variable defining it was popped from an
      # empty stack).
      had_top = (len(vars) - len(non_top_vars)) > 0
      no_succs = len(self.succs) == 0
      self.has_unresolved_jump = had_top or no_succs

  def hook_up_jumps(self,
                    mutate_jumps:bool=False,
                    generate_throws:bool=False) -> bool:
   """
   Connect this block up to any successors that can be inferred
   from this block's jump condition and destination.
   An invalid jump will be replaced with a THROW instruction.

   Args:
       mutate_jumps: JUMPIs with known conditions become JUMPs (or are deleted)
       generate_throws: JUMP and JUMPI instructions with invalid destinations
                        become THROW and THROWIs

   Returns:
       True iff this block's successor list was modified.
   """
   jumpdests = {}
   # A mapping from a jump dest to all the blocks addressed at that dest

   fallthrough = []
   final_op = self.tac_ops[-1]
   invalid_jump = False
   unresolved = True

   def handle_valid_dests(d):
     """
     Append any valid jump destinations to the jumpdest list,
     returning False iff the possible destination set is unconstrained.
     A jump must be considered invalid if it has no valid destinations.
     """
     if d.is_unconstrained:
       return False

     for v in d:
       if self.cfg.is_valid_jump_dest(v):
         jumpdests[v] = [op.block for op in self.cfg.get_ops_by_pc(v)]

     return True

   if final_op.opcode == opcodes.JUMPI:
     dest = final_op.args[0].value
     cond = final_op.args[1].value

     # If the condition cannot be true, remove the jump.
     if mutate_jumps and cond.is_false:
       self.tac_ops.pop()
       fallthrough = self.cfg.get_blocks_by_pc(final_op.pc + 1)
       unresolved = False

     # If the condition must be true, the JUMPI behaves like a JUMP.
     elif mutate_jumps and cond.is_true:
       final_op.opcode = opcodes.JUMP
       final_op.args.pop()

       if handle_valid_dests(dest) and len(jumpdests) == 0:
         invalid_jump = True

       unresolved = False

     # Otherwise, the condition can't be resolved, but check the destination>
     else:
       fallthrough = self.cfg.get_blocks_by_pc(final_op.pc + 1)

       # We've already covered the case that both cond and dest are known,
       # so only handle a variable destination
       if handle_valid_dests(dest) and len(jumpdests) == 0:
         invalid_jump = True

       if not dest.is_unconstrained:
         unresolved = False

   elif final_op.opcode == opcodes.JUMP:
     dest = final_op.args[0].value

     if handle_valid_dests(dest) and len(jumpdests) == 0:
       invalid_jump = True

     if not dest.is_unconstrained:
       unresolved = False

   # The final argument is not a JUMP or a JUMPI
   # Note that this case handles THROW and THROWI
   else:
     unresolved = False

     # No terminating jump or a halt; fall through to next block.
     if not final_op.opcode.halts():
       fallthrough = self.cfg.get_blocks_by_pc(self.exit + 1)

   # Block's jump went to an invalid location, replace the jump with a throw
   # Note that a JUMPI could still potentially throw, but not be
   # transformed into a THROWI unless *ALL* its destinations
   # are invalid.
   if generate_throws and invalid_jump:
     self.tac_ops[-1] = TACOp.convert_jump_to_throw(final_op)
   self.has_unresolved_jump = unresolved

   for address, block_list in list(jumpdests.items()):
     to_add = [d for d in block_list if d in self.succs]
     if len(to_add) != 0:
       jumpdests[address] = to_add

   to_add = [d for d in fallthrough if d in self.succs]
   if len(to_add) != 0:
     fallthrough = to_add

   old_succs = list(self.succs)
   new_succs = {d for dl in list(jumpdests.values()) + [fallthrough] for d in dl}

   for s in old_succs:
     if s not in new_succs and s.entry in jumpdests:
       self.cfg.remove_edge(self, s)

   for s in new_succs:
     if s not in self.succs:
       self.cfg.add_edge(self, s)

   return set(old_succs) != set(self.succs)

  def apply_operations(self, use_sets=False) -> None:
    """
    Propagate and fold constants through the arithmetic TAC instructions
    in this block.

    If use_sets is True, folding will also be done on Variables that
    possess multiple possible values, performing operations in all possible
    combinations of values.
    """
    for op in self.tac_ops:
      if op.opcode == opcodes.CONST:
        op.lhs.values = op.args[0].value.values
      elif op.opcode.is_arithmetic() and \
           (op.constant_args() or (op.constrained_args() and use_sets)):
        rhs = [var.value for var in op.args]
        op.lhs.values = mem.Variable.arith_op(op.opcode.name, rhs).values


class TACOp(patterns.Visitable):
  """
  A Three-Address Code operation.
  Each operation consists of an opcode object defining its function,
  a list of argument variables, and the unique program counter address
  of the EVM instruction it was derived from.
  """

  def __init__(self, opcode:opcodes.OpCode, args:t.List['TACArg'],
               pc:int, block=None):
    """
    Args:
      opcode: the operation being performed.
      args: Variables that are operated upon.
      pc: the program counter at the corresponding instruction in the
          original bytecode.
      block: the block this operation belongs to. Defaults to None.
    """
    self.opcode = opcode
    self.args = args
    self.pc = pc
    self.block = block

  def __str__(self):
    return "{}: {} {}".format(hex(self.pc), self.opcode,
                              " ".join([str(arg) for arg in self.args]))

  def __repr__(self):
    return "<{0} object {1}, {2}>".format(
      self.__class__.__name__,
      hex(id(self)),
      self.__str__()
    )

  def constant_args(self) -> bool:
    """True iff each of this operations arguments is a constant value."""
    return all([arg.value.is_const for arg in self.args])

  def constrained_args(self) -> bool:
    """True iff none of this operations arguments is value-unconstrained."""
    return all([not arg.value.is_unconstrained for arg in self.args])

  @classmethod
  def convert_jump_to_throw(cls, op:'TACOp') -> 'TACOp':
    """
    Given a jump, convert it to a throw, preserving the condition var if JUMPI.
    Otherwise, return the given operation unchanged.
    """
    if op.opcode not in [opcodes.JUMP, opcodes.JUMPI]:
      return op
    elif op.opcode == opcodes.JUMP:
      return cls(opcodes.THROW, [], op.pc, op.block)
    elif op.opcode == opcodes.JUMPI:
      return cls(opcodes.THROWI, [op.args[1]], op.pc, op.block)

  def __deepcopy__(self, memodict={}):
    new_op = type(self)(self.opcode,
                        copy.deepcopy(self.args, memodict),
                        self.pc,
                        self.block)
    return new_op


class TACAssignOp(TACOp):
  """
  A TAC operation that additionally takes a variable to which
  this operation's result is implicitly bound.
  """

  def __init__(self, lhs:mem.Variable, opcode:opcodes.OpCode,
               args:t.List['TACArg'], pc:int, block=None,
               print_name:bool=True):
    """
    Args:
      lhs: The Variable that will receive the result of this operation.
      opcode: The operation being performed.
      args: Variables that are operated upon.
      pc: The program counter at this instruction in the original bytecode.
      block: The block this operation belongs to.
      print_name: Some operations (e.g. CONST) don't need to print their
                  name in order to be readable.
    """
    super().__init__(opcode, args, pc, block)
    self.lhs = lhs
    self.print_name = print_name

  def __str__(self):
    arglist = ([str(self.opcode)] if self.print_name else []) \
              + [str(arg) for arg in self.args]
    return "{}: {} = {}".format(hex(self.pc), self.lhs.identifier,
                                " ".join(arglist))

  def __deepcopy__(self, memodict={}):
    new_op = type(self)(copy.deepcopy(self.lhs, memodict),
                        self.opcode,
                        copy.deepcopy(self.args, memodict),
                        self.pc,
                        self.block,
                        self.print_name)
    return new_op


class TACArg:
  """
  Contains information held in an argument to a TACOp.
  In particular, a TACArg may hold both the current value of an argument,
  if it exists; along with the entry stack position it came from, if it did.
  This allows updated/refined stack data to be propagated into the body
  of a TACBasicBlock.
  """

  def __init__(self, var:mem.Variable=None, stack_var:mem.MetaVariable=None):
    self.var = var
    """The actual variable this arg contains."""
    self.stack_var = stack_var
    """The stack position this variable came from."""

  def __str__(self):
    return str(self.value)

  @property
  def value(self):
    """
    Return this arg's value if it has one, otherwise return its stack variable.
    """

    if self.var is None:
      if self.stack_var is None:
        raise ValueError("TAC Argument has no value.")
      else:
        return self.stack_var
    else:
      return self.var

  @classmethod
  def from_var(cls, var:mem.Variable):
    if isinstance(var, mem.MetaVariable):
      return cls(stack_var=var)
    return cls(var=var)


class TACPCRef:
  """Contains a reference to a program counter within a particular block."""

  def __init__(self, block, pc):
    self.block = block
    """The block that contains the referenced instruction."""
    self.pc = pc
    """The program counter of the referenced instruction."""

  def __deepcopy__(self, memodict={}):
    return type(self)(self.block, self.pc)

  def __str__(self):
    return "{}.{}".format(self.block.ident(), hex(self.pc))

  def __eq__(self, other):
    return self.block == other.block and self.pc == other.pc

  def __hash__(self):
    return hash(self.block) ^ hash(self.pc)

  def get_instruction(self):
    """Return the TACOp referred to by this TACPCRef, if it exists."""
    for i in self.block.tac_ops:
      if i.pc == self.pc:
        return i
    return None


class Destackifier:
  """Converts EVMBasicBlocks into corresponding TACBasicBlocks.

  Most instructions get mapped over directly, except:
      POP: generates no TAC op, but pops the symbolic stack;
      PUSH: generates a CONST TAC assignment operation;
      DUP, SWAP: these simply permute the symbolic stack, generate no ops;
      LOG0 ... LOG4: all translated to a generic LOG instruction

  Additionally, there is a NOP TAC instruction that does nothing, to represent
  a block containing EVM instructions with no corresponding TAC code.
  """

  def __fresh_init(self, evm_block:evm_cfg.EVMBasicBlock) -> None:
    """Reinitialise all structures in preparation for converting a block."""

    # A sequence of three-address operations
    self.ops = []

    # The symbolic variable stack we'll be operating on.
    self.stack = mem.VariableStack()

    # The number of TAC variables we've assigned,
    # in order to produce unique identifiers. Typically the same as
    # the number of items pushed to the stack.
    self.stack_vars = 0

    # Entry address of the current block being converted
    self.block_entry = evm_block.evm_ops[0].pc \
                       if len(evm_block.evm_ops) > 0 else None

  def __new_var(self) -> mem.Variable:
    """Construct and return a new variable with the next free identifier."""
    var = mem.Variable.top(name="V{}".format(self.stack_vars),
                           def_sites=ssle([TACPCRef(None, self.block_entry)]))
    self.stack_vars += 1
    return var

  def convert_block(self, evm_block:evm_cfg.EVMBasicBlock) -> TACBasicBlock:
    """
    Given a EVMBasicBlock, produce an equivalent three-address code sequence
    and return the resulting TACBasicBlock.
    """
    self.__fresh_init(evm_block)

    for op in evm_block.evm_ops:
      self.__handle_evm_op(op)

    entry = evm_block.evm_ops[0].pc if len(evm_block.evm_ops) > 0 else None
    exit = evm_block.evm_ops[-1].pc + evm_block.evm_ops[-1].opcode.push_len() \
           if len(evm_block.evm_ops) > 0 else None

    # If the block is empty, append a NOP before continuing.
    if len(self.ops) == 0:
      self.ops.append(TACOp(opcodes.NOP, [], entry))

    new_block = TACBasicBlock(entry, exit, self.ops, evm_block.evm_ops,
                              self.stack)

    # Link up new ops and def sites to the block that contains them.
    new_block.reset_block_refs()

    return new_block

  def __handle_evm_op(self, op:evm_cfg.EVMOp) -> None:
    """
    Produce from an EVM line its corresponding TAC instruction, if there is one,
    appending it to the current TAC sequence, and manipulate the stack in any
    needful way.
    """

    if op.opcode.is_swap():
      self.stack.swap(op.opcode.pop)
    elif op.opcode.is_dup():
      self.stack.dup(op.opcode.pop)
    elif op.opcode == opcodes.POP:
      self.stack.pop()
    else:
      self.__gen_instruction(op)

  def __gen_instruction(self, op:evm_cfg.EVMOp) -> None:
    """
    Given a line, generate its corresponding TAC operation,
    append it to the op sequence, and push any generated
    variables to the stack.
    """

    inst = None
    # All instructions that push anything push exactly
    # one word to the stack. Assign that symbolic variable here.
    new_var = self.__new_var() if op.opcode.push == 1 else None

    # Set this variable's def site
    if new_var is not None:
      for site in new_var.def_sites:
        site.pc = op.pc

    # Generate the appropriate TAC operation.
    # Special cases first, followed by the fallback to generic instructions.
    if op.opcode.is_push():
      args = [TACArg(var=mem.Variable(values=[op.value], name="C"))]
      inst = TACAssignOp(new_var, opcodes.CONST, args, op.pc, print_name=False)
    elif op.opcode.is_log():
      args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
      inst = TACOp(opcodes.LOG, args, op.pc)
    elif op.opcode == opcodes.MLOAD:
      args = [mem.MLoc32(TACArg.from_var(self.stack.pop()))]
      inst = TACAssignOp(new_var, op.opcode, args, op.pc, print_name=False)
    elif op.opcode == opcodes.MSTORE:
      args = [TACArg.from_var(var) for var in self.stack.pop_many(2)]
      inst = TACAssignOp(mem.MLoc32(args[0]), op.opcode, args[1:],
                         op.pc, print_name=False)
    elif op.opcode == opcodes.MSTORE8:
      args = [TACArg.from_var(var) for var in self.stack.pop_many(2)]
      inst = TACAssignOp(mem.MLoc1(args[0]), op.opcode, args[1:],
                         op.pc, print_name=False)
    elif op.opcode == opcodes.SLOAD:
      args = [mem.SLoc32(TACArg.from_var(self.stack.pop()))]
      inst = TACAssignOp(new_var, op.opcode, args, op.pc, print_name=False)
    elif op.opcode == opcodes.SSTORE:
      args = [TACArg.from_var(var) for var in self.stack.pop_many(2)]
      inst = TACAssignOp(mem.SLoc32(args[0]), op.opcode, args[1:],
                         op.pc, print_name=False)
    elif new_var is not None:
      args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
      inst = TACAssignOp(new_var, op.opcode, args, op.pc)
    else:
      args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
      inst = TACOp(op.opcode, args, op.pc)

    # This var must only be pushed after the operation is performed.
    if new_var is not None:
      self.stack.push(new_var)
    self.ops.append(inst)
