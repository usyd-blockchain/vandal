# BSD 3-Clause License
#
# Copyright (c) 2016, 2017, The University of Sydney. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""memtypes.py: Symbolic representations of ways of storing information
in the ethereum machine."""

import abc
import copy
import typing as t
from itertools import zip_longest, dropwhile

from src.lattice import LatticeElement, SubsetLatticeElement as ssle

VAR_DEFAULT_NAME = "Var"
"""The fallback name when creating a fresh variable."""
VAR_RESULT_NAME = "Res"
"""The name to apply to variables resulting from an arithmetic operation."""


class Location(abc.ABC):
    """A generic storage location: variables, memory, static storage."""

    @property
    def identifier(self) -> str:
        """Return the string identifying this object."""
        return str(self)

    @property
    def is_const(self) -> bool:
        """True if the set of possible values this Location stores is known."""
        return False

    @property
    def is_unconstrained(self) -> bool:
        """
        True iff this variable could take on all possible values.
        """
        return self.values.is_top

    @property
    def values(self) -> ssle:
        """
        Return the set of values this location may contain.
        Generically, this set is unconstrained.
        """
        return ssle.top()


class Variable(ssle, Location):
    """
    A symbolic variable whose value is supposed to be
    the result of some TAC operation. Its size is 32 bytes.
    """

    SIZE = 32
    """Variables are 32 bytes in size."""

    CARDINALITY = 2 ** (SIZE * 8)
    """
    The number of distinct values this variable could contain.
    The maximum integer representable by this Variable is then CARDINALITY - 1.
    """

    def __init__(self, values: t.Iterable = None, name: str = VAR_DEFAULT_NAME,
                 def_sites: ssle = ssle.bottom()):
        """
        Args:
          values: the set of values this variable could take.
          name: the name that uniquely identifies this variable.
          def_sites: a set of locations (TACLocRefs) where this variable
                     was possibly defined.
        """

        # Make sure the input values are not out of range.
        mod = [] if values is None else [v % self.CARDINALITY for v in values]
        super().__init__(value=mod)
        self.name = name
        self.def_sites = def_sites

    def __deepcopy__(self, memodict={}):
        if self.is_top:
            return type(self).top(self.name, copy.deepcopy(self.def_sites, memodict))
        if self.is_bottom:
            return type(self).bottom(self.name, copy.deepcopy(self.def_sites, memodict))

        return type(self)(copy.deepcopy(self.value, memodict),
                          self.name,
                          copy.deepcopy(self.def_sites, memodict))
        # Note: type(self) dynamically obtains the Variable class.
        #       Hence, no explicit Variable constructor reference required.

    @property
    def values(self) -> ssle:
        """The value set this Variable contains."""
        return self

    @values.setter
    def values(self, vals: t.Iterable):
        """
        Set this Variable's value set, ensuring that they are all in range.

        Args:
          vals: an iterable of values that this Variable will hold
        """
        self.value = ssle(v % self.CARDINALITY for v in vals).value

    @property
    def identifier(self) -> str:
        """Return the string identifying this object."""
        return self.name

    @property
    def is_true(self) -> bool:
        """
        True iff all values contained in this variable are nonzero.
        N.B. is_true is not the inverse of is_false, as Variables are not bivalent.
        """
        if not self.is_finite:
            return False
        return not any(c == 0 for c in self)

    @property
    def is_false(self) -> bool:
        """
        True iff all values contained in this variable are zero.
        N.B. is_false is not the inverse of is_true, as Variables are not bivalent.
        """
        if not self.is_finite:
            return False
        return not any(c != 0 for c in self)

    def __str__(self):
        if self.is_unconstrained:
            return self.identifier
        if self.is_const:
            return hex(self.const_value)
        val_str = ", ".join(hex(val) for val in sorted(self.value))
        return "{{{}}}".format(val_str)

    def __repr__(self):
        return "<{0} object {1}, {2}>".format(
            self.__class__.__name__,
            hex(id(self)),
            self.__str__()
        )

    def __eq__(self, other):
        return self.value == other

    def __hash__(self):
        if self.is_top:
            return hash(self.TOP_SYMBOL) ^ hash(self.name)
        else:
            # frozenset because plain old sets are unhashable
            return hash(frozenset(self.value)) ^ hash(self.name)

    @classmethod
    def meet(cls, a: 'Variable', b: 'Variable') -> 'Variable':
        """
        Return a Variable whose values and def sites are the
        intersections of the inputs value and def site sets.
        """
        vals = ssle.meet(a, b)
        sites = ssle.meet(a.def_sites, b.def_sites)
        if vals.is_top:
            return cls.top(def_sites=sites)
        return cls(values=vals, def_sites=sites)

    @classmethod
    def join(cls, a: 'Variable', b: 'Variable') -> 'Variable':
        """
        Return a Variable whose values and def sites are the
        unions of the inputs value and def site sets.
        """
        vals = ssle.join(a, b)
        sites = ssle.join(a.def_sites, b.def_sites)
        if vals.is_top:
            return cls.top(def_sites=sites)
        return cls(values=vals, def_sites=sites)

    @classmethod
    def top(cls, name=VAR_DEFAULT_NAME, def_sites: ssle = ssle.bottom()) -> 'Variable':
        """
        Return a Variable with Top value, and optionally set its name.

        Args:
          name: the name of the new variable.
          def_sites: a set of locations where this variable was possibly defined.
        """
        result = cls(name=name, def_sites=def_sites)
        result.value = cls._top_val()
        return result

    @classmethod
    def bottom(cls, name=VAR_DEFAULT_NAME, def_sites: ssle = ssle.bottom()) -> 'Variable':
        """
        Return a Variable with Bottom value, and optionally set its name.

        Args:
          name: the name of the new variable.
          def_sites: a set of locations where this variable was possibly defined.
        """
        return cls(values=cls._bottom_val(), name=name, def_sites=def_sites)

    @property
    def const_value(self):
        """If this variable is constant, return its value."""
        if not self.is_const:
            return None
        return next(iter(self))

    def complement(self) -> 'Variable':
        """
        Return the signed two's complement interpretation of this constant's values.
        """
        return type(self)(values=self.value.map(self.twos_comp),
                          name=VAR_RESULT_NAME)

    @classmethod
    def twos_comp(cls, v: int) -> int:
        """
        Return the signed two's complement interpretation of the given integer.
        """
        return v - cls.CARDINALITY if v & (cls.CARDINALITY >> 1) else v

    # EVM arithmetic operations follow.
    # For comparison operators, "True" and "False" are represented by Constants
    # with the value 1 and 0 respectively.
    # Op function names should be identical to the opcode names themselves.

    @classmethod
    def arith_op(cls, opname: str, args: t.Iterable['Variable'],
                 name=VAR_RESULT_NAME) -> 'Variable':
        """
        Apply the named arithmetic operation to the given Variables' values
        in all permutations, and return a Variable containing the result.

        Args:
          opname: the EVM operation to apply.
          args: a sequence of Variables whose length matches the
                arity of the specified operation.
          name: the name of the result Variable.
        """
        result = ssle.cartesian_map(getattr(cls, opname), args)
        return cls(values=result, name=name)

    @classmethod
    def ADD(cls, l: int, r: int) -> int:
        """Return the sum of the inputs."""
        return l + r

    @classmethod
    def MUL(cls, l: int, r: int) -> int:
        """Return the product of the inputs."""
        return l * r

    @classmethod
    def SUB(cls, l: int, r: int) -> int:
        """Return the difference of the inputs."""
        return l - r

    @classmethod
    def DIV(cls, l: int, r: int) -> int:
        """Return the quotient of the inputs."""
        return 0 if (r == 0) else (l // r)

    @classmethod
    def SDIV(cls, l: int, r: int) -> int:
        """Return the signed quotient of the inputs."""
        l_val, r_val = cls.twos_comp(l), cls.twos_comp(r)
        sign = 1 if ((l_val * r_val) >= 0) else -1
        return 0 if (r_val == 0) else (sign * (abs(l_val) // abs(r_val)))

    @classmethod
    def MOD(cls, v: int, m: int) -> int:
        """Modulo operator."""
        return 0 if (m == 0) else (v % m)

    @classmethod
    def SMOD(cls, v: int, m: int) -> int:
        """Signed modulo operator. The output takes the sign of v."""
        v_val, m_val = cls.twos_comp(v), cls.twos_comp(m)
        sign = 1 if (v_val >= 0) else -1
        return 0 if (m == 0) else (sign * (abs(v_val) % abs(m_val)))

    @classmethod
    def ADDMOD(cls, l: int, r: int, m: int) -> int:
        """Modular addition: return (l + r) modulo m."""
        return 0 if (m == 0) else ((l + r) % m)

    @classmethod
    def MULMOD(cls, l: int, r: int, m: int) -> int:
        """Modular multiplication: return (l * r) modulo m."""
        return 0 if (m == 0) else ((l * r) % m)

    @classmethod
    def EXP(cls, b: int, e: int) -> int:
        """Exponentiation: return b to the power of e."""
        return b ** e

    @classmethod
    def SIGNEXTEND(cls, b: int, v: int) -> int:
        """
        Return v, but with the high bit of its b'th byte extended all the way
        to the most significant bit of the output.
        """
        pos = 8 * (b + 1)
        mask = int("1" * ((cls.SIZE * 8) - pos) + "0" * pos, 2)
        val = 1 if (v & (1 << (pos - 1))) > 0 else 0

        return (v & mask) if (val == 0) else (v | ~mask)

    @classmethod
    def LT(cls, l: int, r: int) -> int:
        """Less-than comparison."""
        return 1 if (l < r) else 0

    @classmethod
    def GT(cls, l: int, r: int) -> int:
        """Greater-than comparison."""
        return 1 if (l > r) else 0

    @classmethod
    def SLT(cls, l: int, r: int) -> int:
        """Signed less-than comparison."""
        return 1 if (cls.twos_comp(l) < cls.twos_comp(r)) else 0

    @classmethod
    def SGT(cls, l: int, r: int) -> int:
        """Signed greater-than comparison."""
        return 1 if (cls.twos_comp(l) > cls.twos_comp(r)) else 0

    @classmethod
    def EQ(cls, l: int, r: int) -> int:
        """Equality comparison."""
        return 1 if (l == r) else 0

    @classmethod
    def ISZERO(cls, v: int) -> int:
        """1 if the input is zero, 0 otherwise."""
        return 1 if (v == 0) else 0

    @classmethod
    def AND(cls, l: int, r: int) -> int:
        """Bitwise AND."""
        return l & r

    @classmethod
    def OR(cls, l: int, r: int) -> int:
        """Bitwise OR."""
        return l | r

    @classmethod
    def XOR(cls, l: int, r: int) -> int:
        """Bitwise XOR."""
        return l ^ r

    @classmethod
    def NOT(cls, v: int) -> int:
        """Bitwise NOT."""
        return ~v

    @classmethod
    def BYTE(cls, b: int, v: int) -> int:
        """Return the b'th byte of v."""
        return (v >> ((cls.SIZE - b) * 8)) & 0xFF

    @classmethod
    def SHL(cls, b: int, v: int) -> int:
        """Bitwise shift left."""
        return v << b

    @classmethod
    def SHR(cls, b: int, v: int) -> int:
        """Bitwise shift right."""
        return v >> b

    @classmethod
    def SAR(cls, b: int, v: int) -> int:
        """Arithmetic shift right."""
        return cls.twos_comp(v) >> b

class MetaVariable(Variable):
    """A Variable to stand in for Variables."""

    def __init__(self, name: str, payload=None, def_sites: ssle = ssle.bottom()):
        """
        Args:
          name: the name of the new MetaVariable
          payload: some information to carry along with this MetaVariable.
          def_sites: a set of locations where this variable was possibly defined.
        """
        super().__init__(values=self._bottom_val(), name=name, def_sites=def_sites)

        self.value = self._top_val()
        """
        The value of this MetaVariable.
        MetaVariables are taken to have unconstrained value sets.
        """

        self.payload = payload

    def __str__(self):
        return self.identifier

    def __deepcopy__(self, memodict={}):
        return type(self)(self.name,
                          self.payload,
                          copy.deepcopy(self.def_sites, memodict))


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

    DEFAULT_MAX = 1024
    """
    The default maximum size of a variable stack.
    Any further elements pushed to a stack that is at its capacity are discarded.
    """

    DEFAULT_MIN_MAX_SIZE = 20
    """The minimum maximum size of a variable stack."""

    def __init__(self, state: t.Iterable[Variable] = None,
                 max_size=DEFAULT_MAX, min_max_size=DEFAULT_MIN_MAX_SIZE):
        super().__init__([] if state is None else list(state))

        self.empty_pops = 0
        """The number of times the stack was popped while empty."""

        self.min_max_size = min_max_size
        """
        The minimum size of this variable stack's maximum size.
        Taking the meet of two stacks produces a stack whose maximum size is the
        smaller of the two, but at least as large as this value.
        """

        self.max_size = max_size
        """
        The maximum size of this variable stack before it overflows.
        Pushing to a full stack has no effect.
        """
        self.set_max_size(max_size)

    def __iter__(self):
        """Iteration occurs from head of stack downwards."""
        return iter(reversed(self.value))

    def __str__(self):
        return "[{}]".format(", ".join(str(v) for v in self.value))

    def __len__(self):
        return len(self.value)

    def __eq__(self, other):
        return len(self) == len(other) and \
               all(v1 == v2 for v1, v2 in
                   zip(reversed(self.value), reversed(other.value)))

    def copy(self) -> 'VariableStack':
        """
        Produce a copy of this stack, without deep copying
        the variables it contains.
        """
        new_stack = type(self)()
        new_stack.value = copy.copy(self.value)
        new_stack.empty_pops = self.empty_pops
        new_stack.max_size = self.max_size
        return new_stack

    def metafy(self) -> None:
        """
        Turn all unconstrained variables into metavariables whose labels
        are their current stack position.
        """
        for i in range(len(self)):
            var = self.value[-(i + 1)]
            if var.is_unconstrained:
                self.value[-(i + 1)] = self.__new_metavar(i, def_sites=var.def_sites)

    @staticmethod
    def __new_metavar(n: int, def_sites: ssle = ssle.bottom()) -> MetaVariable:
        """Return a MetaVariable with the given payload and a corresponding name."""
        return MetaVariable(name="S{}".format(n), payload=n, def_sites=def_sites)

    def peek(self, n: int = 0) -> Variable:
        """Return the n'th element from the top without popping anything."""
        if n >= len(self):
            return self.__new_metavar(n - len(self) + self.empty_pops)
        return self.value[-(n + 1)]

    def push(self, var: Variable) -> None:
        """Push a variable to the stack."""
        if len(self.value) < self.max_size:
            self.value.append(var)

    def pop(self) -> Variable:
        """
        Pop a variable off our symbolic stack if one exists, otherwise
        generate a variable from past the bottom.
        """
        if len(self.value):
            return self.value.pop()
        else:
            self.empty_pops += 1
            return self.__new_metavar(self.empty_pops - 1)

    def push_many(self, vs: t.Iterable[Variable]) -> None:
        """
        Push a sequence of elements onto the stack.
        Low index elements are pushed first.
        """
        for v in vs:
            self.push(v)

    def pop_many(self, n: int) -> t.List[Variable]:
        """
        Pop and return n items from the stack.
        First-popped elements inhabit low indices.
        """
        return [self.pop() for _ in range(n)]

    def dup(self, n: int) -> None:
        """Place a copy of stack[n-1] on the top of the stack."""
        items = self.pop_many(n)
        duplicated = [items[-1]] + items
        self.push_many(reversed(duplicated))

    def swap(self, n: int) -> None:
        """Swap stack[0] with stack[n]."""
        items = self.pop_many(n)
        swapped = [items[-1]] + items[1:-1] + [items[0]]
        self.push_many(reversed(swapped))

    def set_max_size(self, n: int) -> None:
        """Set this stack's maximum capacity."""
        new_size = max(self.min_max_size, n)
        self.max_size = new_size
        self.value = self.value[-new_size:]

    @classmethod
    def meet(cls, a: 'VariableStack', b: 'VariableStack') -> 'VariableStack':
        """
        Return the meet of the given stacks, taking the element-wise meets of their
        contained Variables from the top down.
        """

        pairs = zip_longest(reversed(a.value), reversed(b.value),
                            fillvalue=Variable.bottom())
        max_size = a.max_size if a.max_size < b.max_size else b.max_size
        return cls(dropwhile(lambda x: x.is_bottom,
                             [Variable.meet(*p) for p in pairs][::-1]),
                   max_size)

    @classmethod
    def join(cls, a: 'VariableStack', b: 'VariableStack') -> 'VariableStack':
        """
        Return the join of the given stacks, taking the element-wise joins of their
        contained Variables from the top down.
        """

        pairs = zip_longest(reversed(a.value), reversed(b.value),
                            fillvalue=Variable.bottom())
        max_size = a.max_size if a.max_size > b.max_size else b.max_size
        return cls([Variable.join(*p) for p in pairs][::-1], max_size)

    @classmethod
    def join_all(cls, elements: t.Iterable['VariableStack']) -> 'VariableStack':
        """
        Return the common meet of the given sequence; an empty sequence
        yields an empty stack.
        """
        return super().join_all(elements, initial=VariableStack())
