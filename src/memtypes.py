"""memtypes.py: Symbolic representations of ways of storing information
in the ethereum machine."""

from .lattice import SubsetLatticeElement as ssle

class Variable:
  """A symbolic variable whose value is supposed to be
  the result of some TAC operation. Its size is 32 bytes."""

  SIZE = 32
  """Variables are 32 bytes in size."""

  CARDINALITY = 2**(SIZE * 8)
  """
  The number of distinct values this variable could contain.
  The maximum integer representable by this Variable is then CARDINALITY - 1.
  """

  def __init__(self, ident:str, values:ssle=ssle.top()):
    """
    Args:
      ident: the name that uniquely identifies this variable.
      value: the set of values this variable could take.
    """
    self.ident = ident
    self.values = values

  def __str__(self):
    if
    return self.ident

  def __repr__(self):
    return "<{0} object {1}, {2}>".format(
      self.__class__.__name__,
      hex(id(self)),
      self.__str__()
    )

  def __eq__(self, other):
    return self.ident == other.ident

  # This needs to be a hashable type, in order to be used as a dict key;
  # Defining __eq__ requires us to redefine __hash__.
  def __hash__(self):
    return hash(self.ident)

  @property
  def is_const(self) -> bool:
    """
    True iff this variable has exactly one possible value.
    """
    return len(self.value) == 1

  @property
  def is_unconstrained(self) -> bool:
    """
    True iff this variable could take on all possible values.
    """
    return self.values.is_top


class Constant(Variable):
  """A specialised variable whose value is a constant integer."""

  def __init__(self, value:int):
    self.value = value % self.CARDINALITY

  def __str__(self):
    return hex(self.value)

  def __eq__(self, other):
    return self.value == other.value

  # This needs to be a hashable type, in order to be used as a dict key;
  # Defining __eq__ requires us to redefine __hash__.
  def __hash__(self):
    return self.value

  @property
  def is_const(self) -> bool:
    """True if this Variable is a Constant."""
    return True

  def twos_compl(self) -> int:
    """
    Return the signed two's complement interpretation of this constant's value.
    """
    if self.value & (self.CARDINALITY - 1):
      return self.CARDINALITY - self.value

  # EVM arithmetic operations.
  # Each takes in two Constant arguments, and returns a new Constant
  # whose value is the result of applying the operation to the argument values.
  # For comparison operators, "True" and "False" are represented by Constants
  # with the value 1 and 0 respectively.
  # These names should be identical to the opcode names themselves.

  @classmethod
  def ADD(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Return the sum of the inputs."""
    return cls((l.value + r.value))

  @classmethod
  def MUL(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Return the product of the inputs."""
    return cls((l.value * r.value))

  @classmethod
  def SUB(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Return the difference of the inputs."""
    return cls((l.value - r.value))

  @classmethod
  def DIV(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Return the quotient of the inputs."""
    return cls(0 if r.value == 0 else l.value // r.value)

  @classmethod
  def SDIV(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Return the signed quotient of the inputs."""
    l_val, r_val = l.twos_compl(), r.twos_compl()
    sign = 1 if l_val * r_val >= 0 else -1
    return cls(0 if r_val == 0 else sign * (abs(l_val) // abs(r_val)))

  @classmethod
  def MOD(cls, v: 'Constant', m: 'Constant') -> 'Constant':
    """Modulo operator."""
    return cls(0 if m.value == 0 else v.value % m.value)

  @classmethod
  def SMOD(cls, v: 'Constant', m: 'Constant') -> 'Constant':
    """Signed modulo operator. The output takes the sign of v."""
    v_val, m_val = v.twos_compl(), m.twos_compl()
    sign = 1 if v_val >= 0 else -1
    return cls(0 if m.value == 0 else sign * (abs(v_val) % abs(m_val)))

  @classmethod
  def ADDMOD(cls, l: 'Constant', r: 'Constant', m: 'Constant') -> 'Constant':
    """Modular addition: return (l + r) modulo m."""
    return cls(0 if m.value == 0 else (l.value + r.value) % m.value)

  @classmethod
  def MULMOD(cls, l: 'Constant', r: 'Constant', m: 'Constant') -> 'Constant':
    """Modular multiplication: return (l * r) modulo m."""
    return cls(0 if m.value == 0 else (l.value * r.value) % m.value)

  @classmethod
  def EXP(cls, b: 'Constant', e: 'Constant') -> 'Constant':
    """Exponentiation: return b to the power of e."""
    return cls(b.value ** e.value)

  @classmethod
  def SIGNEXTEND(cls, b: 'Constant', v: 'Constant') -> 'Constant':
    """
    Return v, but with the high bit of its b'th byte extended all the way
    to the most significant bit of the output.
    """
    pos = 8 * (b.value + 1)
    mask = int("1"*((cls.SIZE * 8) - pos) + "0"*pos, 2)
    val = 1 if (v.value & (1 << (pos - 1))) > 0 else 0

    return cls((v.value & mask) if val == 0 else (v.value | ~mask))

  @classmethod
  def LT(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Less-than comparison."""
    return cls(1 if l.value < r.value else 0)

  @classmethod
  def GT(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Greater-than comparison."""
    return cls(1 if l.value > r.value else 0)

  @classmethod
  def SLT(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Signed less-than comparison."""
    return cls(1 if l.twos_compl() < r.twos_compl() else 0)

  @classmethod
  def SGT(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Signed greater-than comparison."""
    return cls(1 if l.twos_compl() > r.twos_compl() else 0)

  @classmethod
  def EQ(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Equality comparison."""
    return cls(1 if l.value == r.value else 0)

  @classmethod
  def ISZERO(cls, v: 'Constant') -> 'Constant':
    """1 if the input is zero, 0 otherwise."""
    return cls(1 if v.value == 0 else 0)

  @classmethod
  def AND(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Bitwise AND."""
    return cls(l.value & r.value)

  @classmethod
  def OR(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Bitwise OR."""
    return cls(l.value | r.value)

  @classmethod
  def XOR(cls, l: 'Constant', r: 'Constant') -> 'Constant':
    """Bitwise XOR."""
    return cls(l.value ^ r.value)

  @classmethod
  def NOT(cls, v: 'Constant') -> 'Constant':
    """Bitwise NOT."""
    return cls(~v.value)

  @classmethod
  def BYTE(cls, b: 'Constant', v: 'Constant') -> 'Constant':
    """Return the b'th byte of v."""
    return cls((v >> ((self.SIZE - b)*8)) & 0xFF)


class Location:
  """A generic storage location."""

  def __init__(self, space_id:str, size:int, address:Variable):
    """
    Construct a location from the name of the space,
    and the size of the storage location in bytes.

    Args:
      space_id: The identifier of an address space.
      size: Size of this location in bytes.
      address: Either a variable or a constant indicating the location.
    """
    self.space_id = space_id
    self.size = size
    self.address = address

  def __str__(self):
    return "{}[{}]".format(self.space_id, self.address)

  def __repr__(self):
    return "<{0} object {1}, {2}>".format(
      self.__class__.__name__,
      hex(id(self)),
      self.__str__()
    )

  def __eq__(self, other):
    return (self.space_id == other.space_id) \
           and (self.address == other.address) \
           and (self.size == other.size)

  # This needs to be a hashable type, in order to be used as a dict key;
  # Defining __eq__ requires us to redefine __hash__.
  def __hash__(self):
    return hash(self.space_id) ^ hash(self.size) ^ hash(self.address)

  @property
  def is_const(self) -> bool:
    """
    True if this variable is an instance of Constant.
    Neater and more meaningful than using isinstance().
    """
    return False


class MLoc(Location):
  """A symbolic memory region 32 bytes in length."""
  def __init__(self, address:Variable):
    super().__init__("M", 32, address)


class MLocByte(Location):
  """ A symbolic one-byte cell from memory."""
  def __init__(self, address:Variable):
    super().__init__("M1", 1, address)


class SLoc(Location):
  """A symbolic one word static storage location."""
  def __init__(self, address:Variable):
    super().__init__("S", 32, address)



