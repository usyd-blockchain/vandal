"""tac_cfg.py: Definitions of Three-Address Code operations and related
objects."""

import typing as t

import opcodes
import cfg
import evm_cfg
import memtypes as mem
import blockparse
import patterns

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

    self.root = next((b for b in self.blocks if b.entry == 0), None)
    """The root block of this CFG. The entry point will always be at index 0, if it exists."""

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
    return cls(blockparse.EVMBlockParser(dasm).parse())

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
    for block in self.blocks:
      block.preds.sort(key=lambda b: b.entry)

  def apply_operations(self, use_sets=False) -> None:
    """
    Propagate and fold constants through the arithmetic TAC instructions
    in this CFG.

    If use_sets is True, folding will also be done on Variables that
    possess multiple possible values, performing operations in all possible
    combinations of values.
    """
    for block in self.blocks:
      for op in block.tac_ops:
        if op.opcode == opcodes.CONST:
          op.lhs.values = op.args[0].values
        elif op.opcode.is_arithmetic() and \
             (op.constant_args() or (op.constrained_args() and use_sets)):
          op.lhs.values = mem.Variable.arith_op(op.opcode.name, op.args).values

  def hook_up_stack_vars(self) -> None:
    """
    Replace all stack MetaVariables will be replaced with the actual
    variables they refer to.
    """
    for block in self.blocks:
      for op in block.tac_ops:
        for i in range(len(op.args)):
          if isinstance(op.args[i], mem.MetaVariable):
            op.args[i] = block.entry_stack.peek(op.args[i].payload)

  def hook_up_jumps(self) -> None:
    """
    Connect all edges in the graph that can be inferred given any constant
    values of jump destinations and conditions.
    Invalid jumps are replaced with THROW instructions.

    This is assumed to be performed after constant propagation and/or folding,
    since edges are deduced from constant-valued jumps.
    """
    for block in self.blocks:
      jumpdests = []
      fallthrough = None
      final_op = block.tac_ops[-1]
      invalid_jump = False
      unresolved = True


      # Append any valid jump destinations to the jumpdest list, returning
      # None if the possible destination set is unconstrained.
      handle_valid_dests = lambda d: \
                                 [jumpdests.append(self.get_op_by_pc(v).block)
                                  for v in d if self.is_valid_jump_dest(v)] \
                                 if not d.is_unconstrained else None

      if final_op.opcode == opcodes.JUMPI:
        dest = final_op.args[0]
        cond = final_op.args[1]

        # If the condition cannot be true, remove the jump.
        if cond.is_false:
          block.tac_ops.pop()
          fallthrough = self.get_block_by_pc(final_op.pc + 1)
          unresolved = False

        # If the condition must be true, the JUMPI behaves like a JUMP.
        elif cond.is_true:
          final_op.opcode = opcodes.JUMP
          final_op.args.pop()

          if (handle_valid_dests(dest) is not None) and len(jumpdests) == 0:
            invalid_jump = True

          unresolved = False

        # Otherwise, the condition can't be resolved, but check the destination>
        else:
          fallthrough = self.get_block_by_pc(final_op.pc + 1)

          # We've already covered the case that both cond and dest are known,
          # so only handle a variable destination
          if (handle_valid_dests(dest) is not None) and len(jumpdests) == 0:
            invalid_jump = True

          if not dest.is_unconstrained:
            unresolved = False

      elif final_op.opcode == opcodes.JUMP:
        dest = final_op.args[0]

        if (handle_valid_dests(dest) is not None) and len(jumpdests) == 0:
          invalid_jump = True

        if not dest.is_unconstrained:
          unresolved = False

      # The final argument is not a JUMP or a JUMPI
      # Note that this case handles THROW and THROWI
      else:
        unresolved = False

        # No terminating jump or a halt; fall through to next block.
        if not final_op.opcode.halts():
          fallthrough = self.get_block_by_pc(block.exit + 1)

      # Block's jump went to an invalid location, replace the jump with a throw
      # Note that a JUMPI could still potentially throw, but not be
      # transformed into a THROWI unless *ALL* its destinations
      # are invalid.
      if invalid_jump:
        block.tac_ops[-1] = TACOp.convert_jump_to_throw(final_op)
      block.has_unresolved_jump = unresolved
      block.succs = [d for d in {*jumpdests, fallthrough} if d is not None]
      block.succs.sort(key=lambda b: b.entry)

    # Having recalculated all the succs, hook up preds
    self.recalc_preds()

  def is_valid_jump_dest(self, pc:int) -> bool:
    """True iff the given program counter refers to a valid jumpdest."""
    op = self.get_op_by_pc(pc)
    return (op is not None) and (op.opcode == opcodes.JUMPDEST)

  def get_block_by_pc(self, pc:int) -> 'TACBasicBlock':
    """Return the block whose span includes the given program counter value."""
    for block in self.blocks:
      if block.entry <= pc <= block.exit:
        return block
    return None

  def get_op_by_pc(self, pc:int) -> 'TACOp':
    """Return the operation with the given program counter, if it exists."""
    for block in self.blocks:
      for op in block.tac_ops:
        if op.pc == pc:
          return op
    return None


class TACBasicBlock(evm_cfg.EVMBasicBlock):
  """A basic block containing both three-address code, and its
  equivalent EVM code, along with information about the transformation
  applied to the stack as a consequence of its execution."""

  def __init__(self, entry_pc:int, exit_pc:int,
               tac_ops:t.Iterable['TACOp'],
               evm_ops:t.Iterable[evm_cfg.EVMOp],
               delta_stack:mem.VariableStack):
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


class TACOp(patterns.Visitable):
  """
  A Three-Address Code operation.
  Each operation consists of an opcode object defining its function,
  a list of argument variables, and the unique program counter address
  of the EVM instruction it was derived from.
  """

  def __init__(self, opcode:opcodes.OpCode, args:t.List[mem.Variable],
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
    return all([arg.is_const for arg in self.args])

  def constrained_args(self) -> bool:
    """True iff none of this operations arguments is value-unconstrained."""
    return all([not arg.is_unconstrained for arg in self.args])

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


class TACAssignOp(TACOp):
  """
  A TAC operation that additionally takes a variable to which
  this operation's result is implicitly bound.
  """

  def __init__(self, lhs:mem.Variable, opcode:opcodes.OpCode,
               args:t.List[mem.Variable], pc:int, block=None,
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

  def __fresh_init(self) -> None:
    """Reinitialise all structures in preparation for converting a block."""

    # A sequence of three-address operations
    self.ops = []

    # The symbolic variable stack we'll be operating on.
    self.stack = mem.VariableStack()

    # The number of TAC variables we've assigned,
    # in order to produce unique identifiers. Typically the same as
    # the number of items pushed to the stack.
    self.stack_vars = 0

  def __new_var(self) -> mem.Variable:
    """Construct and return a new variable with the next free identifier."""
    var = mem.Variable.top(name="V{}".format(self.stack_vars))
    self.stack_vars += 1
    return var

  def convert_block(self, evm_block:evm_cfg.EVMBasicBlock) -> TACBasicBlock:
    """
    Given a EVMBasicBlock, produce an equivalent three-address code sequence
    and return the resulting TACBasicBlock.
    """
    self.__fresh_init()

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

    for op in self.ops:
      op.block = new_block
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
    var = self.__new_var() if op.opcode.push == 1 else None

    # Generate the appropriate TAC operation.
    # Special cases first, followed by the fallback to generic instructions.
    if op.opcode.is_push():
      inst = TACAssignOp(var, opcodes.CONST,
                         [mem.Variable(values=[op.value], name="C")],
                         op.pc, print_name=False)
    elif op.opcode.is_log():
      inst = TACOp(opcodes.LOG, self.stack.pop_many(op.opcode.pop), op.pc)
    elif op.opcode == opcodes.MLOAD:
      inst = TACAssignOp(var, op.opcode, [mem.MLoc32(self.stack.pop())],
                         op.pc, print_name=False)
    elif op.opcode == opcodes.MSTORE:
      args = self.stack.pop_many(2)
      inst = TACAssignOp(mem.MLoc32(args[0]), op.opcode, args[1:],
                         op.pc, print_name=False)
    elif op.opcode == opcodes.MSTORE8:
      args = self.stack.pop_many(2)
      inst = TACAssignOp(mem.MLoc1(args[0]), op.opcode, args[1:],
                         op.pc, print_name=False)
    elif op.opcode == opcodes.SLOAD:
      inst = TACAssignOp(var, op.opcode, [mem.SLoc32(self.stack.pop())],
                         op.pc, print_name=False)
    elif op.opcode == opcodes.SSTORE:
      args = self.stack.pop_many(2)
      inst = TACAssignOp(mem.SLoc32(args[0]), op.opcode, args[1:],
                         op.pc, print_name=False)
    elif var is not None:
      inst = TACAssignOp(var, op.opcode,
                         self.stack.pop_many(op.opcode.pop), op.pc)
    else:
      inst = TACOp(op.opcode, self.stack.pop_many(op.opcode.pop), op.pc)

    # This var must only be pushed after the operation is performed.
    if var is not None:
      self.stack.push(var)
    self.ops.append(inst)
