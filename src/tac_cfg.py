"""tac_cfg.py: Definitions of Three-Address Code operations and related
objects."""

import typing as t
from itertools import zip_longest, dropwhile

import opcodes
import cfg
import evm_cfg
import memtypes as mem
import blockparse
import patterns
from lattice import LatticeElement

class TACGraph(cfg.ControlFlowGraph):
  """
  A control flow graph holding Three-Address Code blocks and
  the edges between them.
  """

  def __init__(self, evm_blocks:t.Iterable[evm_cfg.EVMBasicBlock]):
    """
    Args:
      evm_blocks: an iterable of EVMBasicBlocks to convert into TAC form.

    Note that no edges will exist in the graph until:
      * Some constant folding and propagation has been performed.
      * The jumps have been rechecked.
    """
    super().__init__()

    # Convert the input EVM blocks to TAC blocks.
    destack = Destackifier()

    self.blocks = [destack.convert_block(b) for b in evm_blocks]
    """The sequence of TACBasicBlocks contained in this graph."""

    self.root = next((b for b in self.blocks if b.entry == 0), None)
    """The root block of this CFG. The entry point will always be at index 0, if it exists."""

  @classmethod
  def from_dasm(cls, dasm:t.Iterable[str]) -> 'TACGraph':
    return cls(blockparse.EVMBlockParser(dasm).parse())

  def recalc_preds(self):
    """
    Given a cfg where block successor lists are populated,
    also repopulate the predecessor lists, after emptying them.
    """
    for block in self.blocks:
      block.preds = []
    for block in self.blocks:
      for successor in block.succs:
        successor.preds.append(block)

  def recheck_jumps(self):
    """
    Connect all edges in the graph that can be inferred given any constant
    values of jump destinations and conditions.
    Invalid jumps are replaced with THROW instructions.

    This is assumed to be performed after constant propagation and/or folding,
    since edges are deduced from constant-valued jumps.
    """
    for block in self.blocks:
      jumpdest = None
      fallthrough = None
      final_op = block.tac_ops[-1]
      invalid_jump = False
      unresolved = True

      if final_op.opcode == opcodes.JUMPI:
        dest = final_op.args[0]
        cond = final_op.args[1]

        # If the condition is constant, there is only one jump destination.
        if cond.is_const:
          # If the condition can never be true, remove the jump.
          if cond.const_value == 0:
            block.tac_ops.pop()
            fallthrough = self.get_block_by_pc(final_op.pc + 1)
            unresolved = False
          # If the condition is always true, the JUMPI behaves like a JUMP.
          # Check that the dest is constant and/or valid
          elif dest.is_const:
            final_op.opcode = opcodes.JUMP
            final_op.args.pop()
            if self.is_valid_jump_dest(dest.const_value):
              jumpdest = self.get_op_by_pc(dest.const_value).block
            else:
              invalid_jump = True
            unresolved = False
          # Otherwise, the jump has not been resolved.
        elif dest.is_const:
          # We've already covered the case that both cond and dest are const
          # So only handle a variable condition
          unresolved = False
          fallthrough = self.get_block_by_pc(final_op.pc + 1)
          if self.is_valid_jump_dest(dest.const_value):
            jumpdest = self.get_op_by_pc(dest.const_value).block
          else:
            invalid_jump = True

      elif final_op.opcode == opcodes.JUMP:
        dest = final_op.args[0]
        if dest.is_const:
          unresolved = False
          if self.is_valid_jump_dest(dest.const_value):
            jumpdest = self.get_op_by_pc(dest.const_value).block
          else:
            invalid_jump = True

      else:
        unresolved = False

        # No terminating jump or a halt; fall through to next block.
        if not final_op.opcode.halts():
          fallthrough = self.get_block_by_pc(block.exit + 1)

      # Block's jump went to an invalid location, replace the jump with a throw
      if invalid_jump:
        block.tac_ops[-1] = TACOp.convert_jump_to_throw(final_op)
      block.has_unresolved_jump = unresolved
      block.succs = [d for d in {jumpdest, fallthrough} if d is not None]

    # Having recalculated all the succs, hook up preds
    self.recalc_preds()

  def is_valid_jump_dest(self, pc:int) -> bool:
    """True iff the given program counter is a proper jumpdest."""
    op = self.get_op_by_pc(pc)
    return (op is not None) and (op.opcode == opcodes.JUMPDEST)

  def get_block_by_pc(self, pc:int):
    """Return the block whose span includes the given program counter value."""
    for block in self.blocks:
      if block.entry <= pc <= block.exit:
        return block
    return None

  def get_op_by_pc(self, pc:int):
    """Return the operation with the given program counter, if it exists."""
    for block in self.blocks:
      for op in block.tac_ops:
        if op.pc == pc:
          return op
    return None


class TACBasicBlock(evm_cfg.EVMBasicBlock):
  """A basic block containing both three-address code, and its
  equivalent EVM code, along with information about the transformation
  applied to the stack as a consequence of its execcution."""

  def __init__(self, entry: int, exit: int,
               tac_ops: t.Iterable['TACOp'],
               evm_ops: t.Iterable[evm_cfg.EVMOp],
               delta_stack: 'VariableStack'):
    """
    Args:
      entry: The pc of the first byte in the source EVM block
      exit: The pc of the last byte in the source EVM block
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
      instruction, but an argument of a POP.
      The range of pc values spanned by all blocks in the CFG should be a
      continuous range from 0 to the maximum value with no gaps between blocks.

      If the input stack state is known, obtain the exit stack state by
      popping off delta_stack.empty_pops items and add the delta_stack items
      to the top.
    """

    super().__init__(entry, exit, evm_ops)

    self.tac_ops = tac_ops
    """A sequence of TACOps whose execution is equivalent to the source EVM
       code"""

    self.delta_stack = delta_stack
    """
    A stack describing the stack state changes caused by running this block.
    Variables named Sn symbolically denote the variable that was n places
    from the top of the stack at entry to this block.
    """

    self.exit_stack = VariableStack()
    """A member that should hold the complete stack state after execution."""

  def __str__(self):
    super_str = super().__str__()
    op_seq = "\n".join(str(op) for op in self.tac_ops)
    stack_pops = "Stack pops: {}".format(self.delta_stack.empty_pops)
    stack_adds = "Stack additions: {}".format(str(self.delta_stack))
    return "\n".join([super_str, self._STR_SEP, op_seq, self._STR_SEP,
                      stack_pops, stack_adds])

  def accept(self, visitor:patterns.Visitor):
    """
    Accepts a visitor and visits itself and all TACOps in the block.

    Args:
      visitor: an instance of :obj:`patterns.Visitor` to accept.
    """
    super().accept(visitor)

    if visitor.can_visit(TACOp) or visitor.can_visit(TACAssignOp):
      for tac_op in self.tac_ops:
        visitor.visit(tac_op)


class TACOp:
  """
  A Three-Address Code operation.
  Each operation consists of an opcode object defining its function,
  a list of argument variables, and the unique program counter address
  of the EVM instruction it was derived from.
  """

  def __init__(self, opcode:opcodes.OpCode, args:t.Iterable[mem.Variable],
               pc:int, block=None):
    """
    Args:
      opcode: the operation being performed.
      args: variables or constants that are operated upon.
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
  def convert_jump_to_throw(cls, op: 'TACOp') -> 'TACOp':
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
               args:t.Iterable[mem.Variable], pc:int, block=None,
               print_name=True):
    """
    Args:
      lhs: The variable that will receive the result of this operation.
      opcode: The operation being performed.
      args: Variables or constants that are operated upon.
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
    return "{}: {} = {}".format(hex(self.pc), self.lhs.identifier, " ".join(arglist))


class Destackifier:
  """Converts EVMBasicBlocks into corresponding TAC operation sequences.

  Most instructions get mapped over directly, except:
      POP: generates no TAC op, but pops the symbolic stack;
      PUSH: generates a CONST TAC assignment operation;
      DUP, SWAP: these simply permute the symbolic stack, generate no ops;
      LOG0 ... LOG4: all translated to a generic LOG instruction
  """

  def __fresh_init(self) -> None:
    """Reinitialise all structures in preparation for converting a block."""

    # A sequence of three-address operations
    self.ops = []

    # The symbolic variable stack we'll be operating on.
    self.stack = VariableStack()

    # The number of TAC variables we've assigned,
    # in order to produce unique identifiers. Typically the same as
    # the number of items pushed to the stack.
    self.stack_vars = 0

  def __new_var(self) -> mem.Variable:
    """Construct and return a new variable with the next free identifier."""
    var = mem.Variable(name="V{}".format(self.stack_vars))
    self.stack_vars += 1
    return var

  def convert_block(self, evm_block:evm_cfg.EVMBasicBlock) -> TACBasicBlock:
    """
    Given a EVMBasicBlock, convert its instructions to Three-Address Code
    and return the resulting TACBasicBlock.
    """
    self.__fresh_init()

    for op in evm_block.evm_ops:
      self.__handle_evm_op(op)

    entry = evm_block.evm_ops[0].pc if len(evm_block.evm_ops) > 0 else -1
    exit = evm_block.evm_ops[-1].pc + evm_block.evm_ops[-1].opcode.push_len() \
           if len(evm_block.evm_ops) > 0 else -1

    new_block = TACBasicBlock(entry, exit, self.ops, evm_block.evm_ops,
                              self.stack)

    for op in self.ops:
      op.block = new_block
    return new_block

  def __handle_evm_op(self, op:evm_cfg.EVMOp) -> None:
    """
    Convert a line to its corresponding instruction, if there is one,
    and manipulate the stack in any needful way.
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
      inst = TACAssignOp(var, opcodes.CONST, [mem.Variable([op.value], "C")],
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


class VariableStack(LatticeElement):
  """
  A stack that holds TAC variables.
  It is also a lattice, so meet and join are defined, and they operate
  element-wise from the top of the stack down.

  The stack is taken to be of infinite capacity, with empty slots extending
  indefinitely downwards. An empty stack slot is interpreted as a Variable
  with Bottom value, for the purposes of the lattice definition.
  Thus an empty stack would be this lattice's Bottom, and a stack "filled" with
  Top Variables would be its Top.
  We therefore have a bounded lattice, but we don't need the extra complexity
  associated with the BoundedLatticeElement class.
  """

  def __init__(self, state: t.Iterable[mem.Variable]=None):
    super().__init__([] if state is None else list(state))

    self.empty_pops = 0
    """The number of times the stack was popped while empty."""

  def __iter__(self):
    """Iteration occurs from head of stack downwards."""
    return iter(reversed(self.value))

  def __str__(self):
    return "[{}]".format(",".join(str(v) for v in self.value))

  def push(self, var: mem.Variable) -> None:
    """Push a variable to the stack."""
    self.value.append(var)

  def pop(self) -> mem.Variable:
    """
    Pop a variable off our symbolic stack if one exists, otherwise
    generate a variable from past the bottom.
    """
    if len(self.value):
      return self.value.pop()
    else:
      res = mem.MetaVariable(name="S{}".format(self.empty_pops),
                             payload=self.empty_pops)
      self.empty_pops += 1
      return res

  def push_many(self, vars: t.Iterable[mem.Variable]) -> None:
    """
    Push a sequence of elements onto the stack.
    Low index elements are pushed first.
    """
    for v in vars:
      self.push(v)

  def pop_many(self, n:int) -> t.Iterable[mem.Variable]:
    """
    Pop and return n items from the stack.
    First-popped elements inhabit low indices.
    """
    return [self.pop() for _ in range(n)]

  def dup(self, n:int) -> None:
    """Place a copy of stack[n-1] on the top of the stack."""
    items = self.pop_many(n)
    duplicated = [items[-1]] + items
    self.push_many(reversed(duplicated))

  def swap(self, n:int) -> None:
    """Swap stack[0] with stack[n]."""
    items = self.pop_many(n)
    swapped = [items[-1]] + items[1:-1] + [items[0]]
    self.push_many(reversed(swapped))

  @classmethod
  def meet(cls, a: 'VariableStack', b: 'VariableStack') -> 'VariableStack':
    pairs = zip_longest(reversed(a.value), reversed(b.value),
                                  fillvalue=mem.Variable.bottom())
    return cls(dropwhile(lambda x: x.is_bottom,
                         [mem.Variable.meet(*p) for p in pairs][::-1]))

  @classmethod
  def join(cls, a: 'VariableStack', b: 'VariableStack') -> 'VariableStack':
    pairs = zip_longest(reversed(a.value), reversed(b.value),
                                  fillvalue=mem.Variable.bottom())
    return cls([mem.Variable.join(*p) for p in pairs][::-1])

  @classmethod
  def join_all(cls, elements: t.Iterable['VariableStack']) -> 'VariableStack':
    return super().join_all(elements, initial=VariableStack())
