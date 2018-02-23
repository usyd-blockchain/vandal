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

"""tac_cfg.py: Definitions of Three-Address Code operations and related
objects."""

import copy
import logging
import typing as t

import networkx as nx

import src.blockparse as blockparse
import src.cfg as cfg
import src.evm_cfg as evm_cfg
import src.memtypes as mem
import src.opcodes as opcodes
import src.patterns as patterns
import src.settings as settings
from src.lattice import SubsetLatticeElement as ssle

POSTDOM_END_NODE = "END"
"""The name of the synthetic end node added for post-dominator calculations."""
UNRES_DEST = "?"
"""The name of the unresolved jump destination auxiliary node."""


class TACGraph(cfg.ControlFlowGraph):
    """
    A control flow graph holding Three-Address Code blocks and
    the edges between them.
    """

    def __init__(self, evm_blocks: t.Iterable[evm_cfg.EVMBasicBlock]):
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
        """
        The root block of this CFG.
        The entry point will always be at index 0, if it exists.
        """

        self.split_node_succs = {}
        """
        A mapping from addresses to addresses storing all successors of a
        block at the time it was split. At merge time these edges can be restored.
        """

        self.function_extractor = None
        """
        A FunctionExtractor object, which encapsulates solidity functions
        and extraction logic.
        """

        # Propagate constants and add CFG edges.
        self.apply_operations()
        self.hook_up_jumps()

    @classmethod
    def from_dasm(cls, dasm: t.Iterable[str]) -> 'TACGraph':
        """
        Construct and return a TACGraph from the given EVM disassembly.

        Args:
          dasm: a sequence of disasm lines, as output from the
                ethereum `dasm` disassembler.
        """
        return cls(blockparse.EVMDasmParser(dasm).parse())

    @classmethod
    def from_bytecode(cls, bytecode: t.Iterable) -> 'TACGraph':
        """
        Construct and return a TACGraph from the given EVM bytecode.

        Args:
          bytecode: a sequence of EVM bytecode, either in a hexadecimal
            string format or a byte array.
        """
        bytecode = ''.join([l.strip() for l in bytecode if len(l.strip()) > 0])
        return cls(blockparse.EVMBytecodeParser(bytecode).parse())

    @property
    def tac_ops(self):
        for block in self.blocks:
            for op in block.tac_ops:
                yield op

    @property
    def last_op(self):
        return max((b.last_op for b in self.blocks),
                   key=lambda o: o.pc)

    @property
    def terminal_ops(self):
        terminals = [op for op in self.tac_ops if op.opcode.possibly_halts()]
        last_op = self.last_op
        if last_op not in terminals:
            return terminals + [last_op]
        return terminals

    def op_edge_list(self) -> t.Iterable[t.Tuple['TACOp', 'TACOp']]:
        """
        Returns:
          a list of the CFG's operation edges, with each edge in the form
          `(pred, succ)` where pred and succ are object references.
        """
        edges = []
        for block in self.blocks:
            intra_edges = list(zip(block.tac_ops[:-1], block.tac_ops[1:]))
            edges += intra_edges
            for succ in block.succs:
                edges.append((block.tac_ops[-1], succ.tac_ops[0]))
        return edges

    def nx_graph(self, op_edges=False) -> nx.DiGraph:
        """
        Return a networkx representation of this CFG.
        Nodes are labelled by their corresponding block's identifier.

        Args:
          op_edges: if true, return edges between instructions rather than blocks.
        """
        g = nx.DiGraph()

        if op_edges:
            g.add_nodes_from(hex(op.pc) for op in self.tac_ops)
            g.add_edges_from((hex(p.pc), hex(s.pc)) for p, s in self.op_edge_list())
            g.add_edges_from((hex(block.last_op.pc), UNRES_DEST)
                             for block in self.blocks if block.has_unresolved_jump)
        else:
            g.add_nodes_from(b.ident() for b in self.blocks)
            g.add_edges_from((p.ident(), s.ident()) for p, s in self.edge_list())
            g.add_edges_from((block.ident(), UNRES_DEST) for block in self.blocks
                             if block.has_unresolved_jump)
        return g

    def immediate_dominators(self, post: bool = False, op_edges=False) \
        -> t.Dict[str, str]:
        """
        Return the immediate dominator mapping of this graph.
        Each node is mapped to its unique immediately dominating node.
        This mapping defines a tree with the root being its own immediate dominator.

        Args:
          post: if true, return post-dominators instead, with an auxiliary node
                  END with edges from all terminal nodes in the CFG.
          op_edges: if true, return edges between instructions rather than blocks.

        Returns:
          dict: str -> str, maps from node identifiers to node identifiers.
        """
        nx_graph = self.nx_graph(op_edges).reverse() if post \
            else self.nx_graph(op_edges)

        # Logic here is not quite robust when op_edges is true, but correct
        # whenever there is a unique entry node, and no graph-splitting.
        start = POSTDOM_END_NODE if post else self.root.ident()

        if post:
            if op_edges:
                terminal_edges = [(POSTDOM_END_NODE, hex(op.pc))
                                  for op in self.terminal_ops]
            else:
                terminal_edges = [(POSTDOM_END_NODE, op.block.ident())
                                  for op in self.terminal_ops]
            nx_graph.add_node(POSTDOM_END_NODE)
            nx_graph.add_edges_from(terminal_edges)

        doms = nx.algorithms.dominance.immediate_dominators(nx_graph, start)
        idents = [b.ident() for b in self.blocks]

        if not op_edges:
            for d in [d for d in doms if d not in idents]:
                del doms[d]

        # TODO: determine whether to remove non-terminal END-postdominators
        #       and turn terminal ones into self-postdominators

        return doms

    def dominators(self, post: bool = False, op_edges=False) \
        -> t.Dict[str, t.Set[str]]:
        """
        Return the dominator mapping of this graph.
        Each block is mapped to the set of blocks that dominate it; its ancestors
        in the dominator tree.

        Args
          post: if true, return postdominators instead.
          op_edges: if true, return edges between instructions rather than blocks.

        Returns:
          dict: str -> [str], a map block identifiers to block identifiers.
        """

        idoms = self.immediate_dominators(post, op_edges)
        doms = {d: set() for d in idoms}

        for d in doms:
            prev = d
            while prev not in doms[d]:
                doms[d].add(prev)
                prev = idoms[prev]

        return doms

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

    def hook_up_jumps(self) -> bool:
        """
        Connect all edges in the graph that can be inferred given any constant
        values of jump destinations and conditions.
        Invalid jumps are replaced with THROW instructions.

        This is assumed to be performed after constant propagation and/or folding,
        since edges are deduced from constant-valued jumps.

        Note that the global mutate_jumps and generate_throws settings should
        likely be true only in the final iteration of a dataflow analysis, at which
        point as much jump destination information as possible has been propagated
        around. If these are used too early, they may prevent valid edges from
        being added later on.

        Returns:
            True iff any edges in the graph were modified.
        """

        # Hook up all jumps, modified will be true if any jump in the graph
        # was changed. Did not use any() and a generator due to lazy-eval,
        # which would be incorrect behaviour.
        modified = False
        for block in self.blocks:
            modified |= block.hook_up_jumps()
        return modified

    def add_missing_split_edges(self):
        """
        If this graph has had its nodes split, if new edges are inferred,
        we need to join them up to all copies of a node, but the split
        paths should remain separate, so only add such edges if parallel ones
        don't already exist on some split path.

        Returns true iff some new edge was added to the graph.
        """
        modified = False

        for pred_address in self.split_node_succs:
            preds = self.get_blocks_by_pc(pred_address)
            s_lists = [node.succs for node in preds]
            succs = set(s for s_list in s_lists for s in s_list)
            for succ in self.split_node_succs[pred_address]:
                if succ not in succs:
                    for pred in preds:
                        if not self.has_edge(pred, succ):
                            self.add_edge(pred, succ)
                            modified = True

        return modified

    def is_valid_jump_dest(self, pc: int) -> bool:
        """True iff the given program counter refers to a valid jumpdest."""
        ops = self.get_ops_by_pc(pc)
        return (len(ops) != 0) and any(op.opcode == opcodes.JUMPDEST for op in ops)

    def get_ops_by_pc(self, pc: int) -> 'TACOp':
        """Return the operations with the given program counter, if any exist."""
        ops = []

        for block in self.get_blocks_by_pc(pc):
            for op in block.tac_ops:
                if op.pc == pc:
                    ops.append(op)

        return ops

    def clone_ambiguous_jump_blocks(self) -> bool:
        """
        If block terminates in a jump with an ambiguous (but constrained)
        jump destination, then find its most recent ancestral confluence point
        and split the path of blocks between into parallel paths, one for each
        predecessor of the block at the confluence point.

        Returns:
            True iff some block was cloned.
        """

        split_occurred = False
        modified = True
        skip = set()

        while modified:
            modified = False

            for block in self.blocks:

                if not self.__split_block_is_splittable(block, skip):
                    continue

                # We satisfy the conditions for attempting a split.
                path = [block]
                curr_block = block
                cycle = False

                # Find the actual path to be split.
                while len(curr_block.preds) == 1:
                    curr_block = curr_block.preds[0]

                    if curr_block not in path:
                        path.append(curr_block)
                    else:
                        # We are in a cycle, break out
                        cycle = True
                        break

                path_preds = list(curr_block.preds)

                # If there's a cycle within the path, die
                # IDEA: See what happens if we copy these cycles
                if cycle or len(path_preds) == 0:
                    continue
                if any(pred in path for pred in path_preds):
                    continue

                # We have identified a splittable path, now split it

                # Remove the old path from the graph.
                skip |= self.__split_remove_path(path)
                # Note well that this deletion will remove all edges to successors
                # of elements of this path, so we can lose information.

                # Generate new paths from the old path, and hook them up properly.
                skip |= self.__split_copy_path(path, path_preds)

                modified = True
                split_occurred = True

        return split_occurred

    def __split_block_is_splittable(self, block, skip):
        """
        True when the given block satisfies the conditions for being the final node
        in a fissionable path. This will be the start point from which the path
        itself will be constructed, following CFG edges backwards until some
        ancestor with multiple predecessors is reached.
        """
        # Don't split on blocks we only just generated; some will
        # certainly satisfy the fission condition.
        if block in skip:
            return False

        # If the block does not end in a jump, don't start a split here.
        if block.last_op.opcode not in [opcodes.JUMP, opcodes.JUMPI]:
            return False

        # We will only split if there were actually multiple jump destinations
        # defined in multiple different ancestral blocks.
        dests = block.last_op.args[0].value
        if dests.is_const or dests.def_sites.is_const \
            or (dests.is_top and dests.def_sites.is_top):
            return False

        return True

    def __split_remove_path(self, path):
        """
        Resect the given path of nodes from the graph, and add its successors
        to the split_node_succs mapping in anticipation of the path's members
        being duplicated and reinserted into the graph.
        Return the set of blocks that need to be added to the skip list.
        """
        skip = set()
        for b in path:
            # Save the edges of each block in case they can't be re-inferred.
            # They will be added back in at a later stage.
            if b.entry not in self.split_node_succs:
                self.split_node_succs[b.entry] = [s for s in sorted(b.succs)]
            else:
                new_list = self.split_node_succs[b.entry]
                new_list += [s for s in sorted(b.succs) if s not in new_list]
                self.split_node_succs[b.entry] = new_list

            skip.add(b)
            self.remove_block(b)

        return skip

    def __split_copy_path(self, path, path_preds):
        """
        Duplicate the given path once for each block in path_preds,
        with each pred being the sole parent of the head of each duplicated path.
        Return the set of blocks that need to be added to the skip list.
        """
        # copy the path
        path_copies = [[copy.deepcopy(b) for b in path]
                       for _ in range(len(path_preds))]

        # Copy the nodes properly in the split node succs mapping.
        for i, b in enumerate(path):
            for a in self.split_node_succs:
                node_copies = [c[i] for c in path_copies]
                if b in self.split_node_succs[a]:
                    self.split_node_succs[a].remove(b)
                    self.split_node_succs[a] += node_copies

        # hook up each pred to a path individually.
        for i, p in enumerate(path_preds):
            self.add_edge(p, path_copies[i][-1])
            for b in path_copies[i]:
                b.ident_suffix += "_" + p.ident()

        # Connect the paths up within themselves
        for path_copy in path_copies:
            for i in range(len(path_copy) - 1):
                self.add_edge(path_copy[i + 1], path_copy[i])

        skip = set()
        # Add the new paths to the graph.
        for c in path_copies:
            for b in c:
                skip.add(b)
                self.add_block(b)

        return skip

    def merge_duplicate_blocks(self,
                               ignore_preds: bool = False,
                               ignore_succs: bool = False) -> None:
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

        # We'll keep on merging until there's nothing left to be merged.
        # At present, the equivalence relation is such that all equivalent
        # blocks should be merged in one pass, but it may be necessary in future
        # to worry about new merge candidates being produced after merging.
        while modified:
            modified = False

            # A list of lists of blocks to be merged.
            groups = []

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

            # Ignore blocks that are in groups by themselves.
            groups = [g for g in groups if len(g) > 1]

            if len(groups) > 0:
                modified = True

            # Merge each group into a single new block.
            for i, group in enumerate(groups):

                # Join all stacks in merged blocks.
                entry_stack = mem.VariableStack.join_all([b.entry_stack for b in group])
                entry_stack.metafy()
                exit_stack = mem.VariableStack.join_all([b.exit_stack for b in group])
                exit_stack.metafy()

                # Collect all predecessors and successors of the merged blocks.
                preds = set()
                succs = set()
                for b in group:
                    preds |= set(b.preds)
                    succs |= set(b.succs)

                # Produce the disjunction of other informative fields within the group.
                symbolic_overflow = any([b.symbolic_overflow for b in group])
                has_unresolved_jump = any([b.has_unresolved_jump for b in group])

                # Construct the new merged block itself.
                # Its identifier will end in an identifying number unless its entry
                # address is unique in the graph.
                new_block = copy.deepcopy(group[0])
                new_block.entry_stack = entry_stack
                new_block.exit_stack = exit_stack
                new_block.preds = list(sorted(preds))
                new_block.succs = list(sorted(succs))
                new_block.ident_suffix = "_" + str(i)
                new_block.symbolic_overflow = symbolic_overflow
                new_block.has_unresolved_jump = has_unresolved_jump

                # Make sure block references inside ops and variables are redirected.
                new_block.reset_block_refs()

                # Add the new block to the graph and connect its edges up properly,
                # while also removing all merged blocks and incident edges.
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
                # then everything it was split from has been merged.
                # It no longer needs an ident suffix to disambiguate it and its entry in
                # he split successors mapping can be removed, along with the edges
                # inferred from that mapping connected up.
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

    def merge_contiguous(self, pred: 'TACBasicBlock', succ: 'TACBasicBlock') -> 'TACBasicBlock':
        """
        Merge two blocks in the cfg if they are contiguous.
        Pred should have a lower address than succ, and they should have
        zero out- and in-degree respectively.

        Args:
            pred: earlier block to merge
            succ: later block to merge

        Returns:
            The resulting merged block.
        """

        # Do not merge the blocks if they cannot be merged.
        if succ.entry != (pred.exit + 1) or len(pred.succs) != 0 or len(succ.preds) != 0:
            err_str = "Attempted to merge unmergeable blocks {} and {}.".format(pred.ident(), succ.ident())
            logging.error(err_str)
            raise RuntimeError(err_str)

        # Construct the merged block.
        tac_ops = pred.tac_ops + succ.tac_ops
        evm_ops = pred.evm_ops + succ.evm_ops
        delta_stack = pred.delta_stack.copy()
        delta_stack.pop_many(pred.delta_stack.empty_pops)
        delta_stack.push_many(reversed(succ.delta_stack.value))
        merged = TACBasicBlock(pred.entry, succ.exit,
                               tac_ops, evm_ops,
                               delta_stack, self)
        merged.entry_stack = pred.entry_stack.copy()
        merged.has_unresolved_jump = succ.has_unresolved_jump
        merged.ident_suffix = pred.ident_suffix + pred.ident_suffix

        # Update the CFG edges.
        self.add_block(merged)
        for b in pred.preds:
            self.add_edge(b, merged)
        for b in succ.succs:
            self.add_edge(merged, b)
        self.remove_block(pred)
        self.remove_block(succ)

        return merged

    def merge_unreachable_blocks(self, origin_addresses: t.Iterable[int] = [0]) \
        -> t.Iterable[t.Iterable['TACBasicBlock']]:
        """
        Merge all unreachable blocks with contiguous addresses into a single
        block. Will only merge blocks if they have no intervening edges.
        Assumes that blocks have unique entry and exit addresses.

        Args:
            origin_addresses: default value: [0], entry addresses, blocks
                              from which are unreachable to be merged.

        Returns:
            An iterable of the groups of blocks which were merged.
        """
        reached = self.transitive_closure(origin_addresses)

        # Sort the unreached ones for more-efficient merging.
        unreached = sorted([b for b in self.blocks if b not in reached], key=lambda b: b.entry)
        if len(unreached) == 0:
            return []

        # Collect the contiguous runs of blocks.
        groups = []
        group = [unreached[0]]
        for b in unreached[1:]:
            # Add the next block to the merge list only if
            # it is contiguous and has no incident edges.
            prev = group[-1]
            if b.entry == (prev.exit + 1) and len(prev.succs) == 0 and len(b.preds) == 0:
                group.append(b)
                continue

            # Singleton groups don't need to be merged
            if len(group) > 1:
                groups.append(group)

            # Start the next group
            group = [b]

        if len(group) > 1:
            groups.append(group)

        # Merge the blocks in each run.
        merged = []
        for g in groups:
            block = g[0]
            for n in g[1:]:
                block = self.merge_contiguous(block, n)
            merged.append(block)

        return groups

    def prop_vars_between_blocks(self) -> None:
        """
        If some entry stack variable is defined in exactly one place, fetch the
        appropriate variable from its source block and substitute it in, along with
        all occurrences of that stack variable in operations and the exit stack.
        """

        for block in self.blocks:
            for i in range(len(block.entry_stack)):
                stack = block.entry_stack
                if stack.value[i].def_sites.is_const:
                    # Fetch variable from def site.
                    location = next(iter(stack.value[i].def_sites))
                    old_var = stack.value[i]
                    new_var = None
                    for op in location.block.tac_ops:
                        if op.pc == location.pc:
                            new_var = op.lhs

                    # Reassign the entry stack position.
                    stack.value[i] = new_var

                    # Reassign exit stack occurrences
                    for j in range(len(block.exit_stack)):
                        if block.exit_stack.value[j] is old_var:
                            block.exit_stack.value[j] = new_var

                    # Reassign occurrences on RHS of operations
                    for o in block.tac_ops:
                        for j in range(len(o.args)):
                            if o.args[j].value is old_var:
                                o.args[j].var = new_var

    def make_stack_names_unique(self) -> None:
        """
        If two variables on the same entry stack share a name but are not the
        same variable, then make the names unique.
        The renaming will propagate through to all occurrences of that var.
        """

        for block in self.blocks:
            # Group up the variables by their names
            variables = sorted(block.entry_stack.value, key=lambda x: x.name)
            if len(variables) == 0:
                continue
            groups = [[variables[0]]]
            for i in range(len(variables))[1:]:
                v = variables[i]
                # When the var name in the name-sorted list changes, start a new group.
                if v.name != variables[i - 1].name:
                    groups.append([v])
                else:
                    # If the variable has already been processed, it only needs to
                    # be renamed once.
                    appeared = False
                    for prev_var in groups[-1]:
                        if v is prev_var:
                            appeared = True
                            break
                    if not appeared:
                        groups[-1].append(v)

            # Actually perform the renaming operation on any groups longer than 1
            for group in groups:
                if len(group) < 2:
                    continue
                for i in range(len(group)):
                    group[i].name += str(i)

    def extract_functions(self):
        """
        Attempt to extract solidity functions from this contract.
        Call this after having already called prop_vars_between_blocks() on cfg.
        """
        import src.function as function
        fe = function.FunctionExtractor(self)
        fe.extract()
        self.function_extractor = fe


class TACBasicBlock(evm_cfg.EVMBasicBlock):
    """
    A basic block containing both three-address code, and its
    equivalent EVM code, along with information about the transformation
    applied to the stack as a consequence of its execution.
    """

    def __init__(self, entry_pc: int, exit_pc: int,
                 tac_ops: t.List['TACOp'],
                 evm_ops: t.List[evm_cfg.EVMOp],
                 delta_stack: mem.VariableStack,
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

    def accept(self, visitor: patterns.Visitor) -> None:
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

        new_block.fallthrough = self.fallthrough
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

    @property
    def last_op(self) -> 'TACOp':
        """Return the last TAC operation in this block if it exists."""
        if len(self.tac_ops):
            return self.tac_ops[-1]
        return None

    @last_op.setter
    def last_op(self, op):
        """
        Set the last TAC operation in this block, if there is one.
        Append if one doesn't exist.
        """
        if len(self.tac_ops):
            self.tac_ops[-1] = op
        else:
            self.tac_ops.append(op)

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

    def build_exit_stack(self) -> bool:
        """
        Apply the transformation in this block's delta stack to construct its
        exit stack from its entry stack.

        Returns:
            True iff a symbolic overflow occurred.
        """
        overflow = False

        # If variables were obtained from deeper than there are extant
        # stack items, the program is possibly popping from an empty stack.
        if settings.die_on_empty_pop \
            and (len(self.entry_stack) < self.delta_stack.empty_pops):
            logging.error("Popped empty stack in %s.", self.ident())
            raise RuntimeError("Popped empty stack in {}.".format(self.ident()))

        # If executing this block would overflow the stack, maybe skip it.
        delta = len(self.delta_stack) - self.delta_stack.empty_pops
        if (len(self.entry_stack) + delta) > self.exit_stack.max_size:
            self.symbolic_overflow = True
            if settings.skip_stack_on_overflow:
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
        if self.last_op.opcode in [opcodes.JUMP, opcodes.JUMPI]:
            dest = self.last_op.args[0].value
            site_vars = [d.get_instruction().lhs for d in dest.def_sites]
            non_top_vars = [v for v in site_vars if not v.is_top]

            existing_dests = [s.entry for s in sorted(self.succs)]

            # join all values to obtain possible jump dests
            # add jumps to those locations if they are valid and don't already exist
            for d in mem.Variable.join_all(non_top_vars):
                if d in existing_dests or not self.cfg.is_valid_jump_dest(d):
                    continue
                for b in self.cfg.get_blocks_by_pc(d):
                    self.cfg.add_edge(self, b)

            self.has_unresolved_jump = (len(non_top_vars) == 0)

    def hook_up_jumps(self) -> bool:
        """
        Connect this block up to any successors that can be inferred
        from this block's jump condition and destination.
        An invalid jump will be replaced with a THROW instruction.

        Returns:
            True iff this block's successor list was modified.
        """
        jumpdests = {}
        # A mapping from a jump dest to all the blocks addressed at that dest

        fallthrough = []
        last_op = self.last_op
        invalid_jump = False
        unresolved = True
        remove_non_fallthrough = False
        remove_fallthrough = False

        if last_op.opcode == opcodes.JUMPI:
            dest = last_op.args[0].value
            cond = last_op.args[1].value

            # If the condition cannot be true, remove the jump.
            if settings.mutate_jumps and cond.is_false:
                self.tac_ops.pop()
                fallthrough = self.cfg.get_blocks_by_pc(last_op.pc + 1)
                unresolved = False
                remove_non_fallthrough = True

            # If the condition must be true, the JUMPI behaves like a JUMP.
            elif settings.mutate_jumps and cond.is_true:
                last_op.opcode = opcodes.JUMP
                last_op.args.pop()

                if self.__handle_valid_dests(dest, jumpdests) and len(jumpdests) == 0:
                    invalid_jump = True

                unresolved = False
                remove_fallthrough = True

            # Otherwise, the condition can't be resolved (it may be either true or false), but check the destination>
            else:
                fallthrough = self.cfg.get_blocks_by_pc(last_op.pc + 1)

                # We've already covered the case that both cond and dest are known,
                # so only handle a variable destination
                if self.__handle_valid_dests(dest, jumpdests) and len(jumpdests) == 0:
                    invalid_jump = True

                if not dest.is_unconstrained:
                    unresolved = False

        elif last_op.opcode == opcodes.JUMP:
            dest = last_op.args[0].value

            if self.__handle_valid_dests(dest, jumpdests) and len(jumpdests) == 0:
                invalid_jump = True

            if not dest.is_unconstrained:
                unresolved = False

        # The final argument is not a JUMP or a JUMPI
        # Note that this case handles THROW and THROWI
        else:
            unresolved = False

            # No terminating jump or a halt; fall through to next block.
            if not last_op.opcode.halts():
                fallthrough = self.cfg.get_blocks_by_pc(self.exit + 1)

        # Block's jump went to an invalid location, replace the jump with a throw
        # Note that a JUMPI could still potentially throw, but not be
        # transformed into a THROWI unless *ALL* its destinations
        # are invalid.
        if settings.generate_throws and invalid_jump:
            self.last_op = TACOp.convert_jump_to_throw(last_op)
        self.has_unresolved_jump = unresolved

        for address, block_list in list(jumpdests.items()):
            to_add = [d for d in block_list if d in self.succs]
            if len(to_add) != 0:
                jumpdests[address] = to_add

        to_add = [d for d in fallthrough if d in self.succs]
        if len(to_add) != 0:
            fallthrough = to_add

        old_succs = list(sorted(self.succs))
        new_succs = {d for dl in list(jumpdests.values()) + [fallthrough] for d in dl}
        if fallthrough:
            self.fallthrough = fallthrough[0]

        for s in old_succs:
            if s not in new_succs and s.entry in jumpdests:
                self.cfg.remove_edge(self, s)

        for s in new_succs:
            if s not in self.succs:
                self.cfg.add_edge(self, s)

        if settings.mutate_jumps:
            fallthrough = self.cfg.get_blocks_by_pc(last_op.pc + 1)
            if remove_non_fallthrough:
                for d in self.succs:
                    if d not in fallthrough:
                        self.cfg.remove_edge(self, d)
            if remove_fallthrough:
                for d in fallthrough:
                    self.cfg.remove_edge(self, d)

        return set(old_succs) != set(self.succs)

    def __handle_valid_dests(self, d: mem.Variable,
                             jumpdests: t.Dict[int, 'TACBasicBlock']):
        """
        Append any valid jump destinations in d to its jumpdest list,
        returning False iff the possible destination set is unconstrained.
        A jump must be considered invalid if it has no valid destinations.
        """
        if d.is_unconstrained:
            return False

        for v in d:
            if self.cfg.is_valid_jump_dest(v):
                jumpdests[v] = [op.block for op in self.cfg.get_ops_by_pc(v)]

        return True

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
            elif op.opcode.is_arithmetic():
                if op.constant_args() or (op.constrained_args() and use_sets):
                    rhs = [arg.value for arg in op.args]
                    op.lhs.values = mem.Variable.arith_op(op.opcode.name, rhs).values
                elif not op.lhs.is_unconstrained:
                    op.lhs.widen_to_top()


class TACOp(patterns.Visitable):
    """
    A Three-Address Code operation.
    Each operation consists of an opcode object defining its function,
    a list of argument variables, and the unique program counter address
    of the EVM instruction it was derived from.
    """

    def __init__(self, opcode: opcodes.OpCode, args: t.List['TACArg'],
                 pc: int, block=None):
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
        if self.opcode in [opcodes.MSTORE, opcodes.MSTORE8, opcodes.SSTORE]:
            if self.opcode == opcodes.MSTORE:
                lhs = "M[{}]".format(self.args[0])
            elif self.opcode == opcodes.MSTORE8:
                lhs = "M8[{}]".format(self.args[0])
            else:
                lhs = "S[{}]".format(self.args[0])

            return "{}: {} = {}".format(hex(self.pc), lhs,
                                        " ".join([str(arg) for arg in self.args[1:]]))
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

    def __init__(self, lhs: mem.Variable, opcode: opcodes.OpCode,
                 args: t.List['TACArg'], pc: int, block=None,
                 print_name: bool = True):
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
        if self.opcode in [opcodes.SLOAD, opcodes.MLOAD]:
            if self.opcode == opcodes.SLOAD:
                rhs = "S[{}]".format(self.args[0])
            else:
                rhs = "M[{}]".format(self.args[0])

            return "{}: {} = {}".format(hex(self.pc), self.lhs.identifier, rhs)
        arglist = ([str(self.opcode)] if self.print_name else []) \
                  + [str(arg) for arg in self.args]
        return "{}: {} = {}".format(hex(self.pc), self.lhs.identifier,
                                    " ".join(arglist))

    def __deepcopy__(self, memodict={}):
        """
        Return a copy of this TACAssignOp, deep copying the args and vars,
        but leaving block references unchanged.
        """
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

    def __init__(self, var: mem.Variable = None, stack_var: mem.MetaVariable = None):
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
    def from_var(cls, var: mem.Variable):
        if isinstance(var, mem.MetaVariable):
            return cls(stack_var=var)
        return cls(var=var)


class TACLocRef:
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
        """Return the TACOp referred to by this TACLocRef, if it exists."""
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

    def __init__(self):
        # A sequence of three-address operations
        self.ops = []

        # The symbolic variable stack we'll be operating on.
        self.stack = mem.VariableStack()

        # Entry address of the current block being converted
        self.block_entry = None

        # The number of TAC variables we've assigned,
        # in order to produce unique identifiers. Typically the same as
        # the number of items pushed to the stack.
        # We increment it so that variable names will be globally unique.
        self.stack_vars = 0

    def __fresh_init(self, evm_block: evm_cfg.EVMBasicBlock) -> None:
        """Reinitialise all structures in preparation for converting a block."""
        self.ops = []
        self.stack = mem.VariableStack()
        self.block_entry = evm_block.evm_ops[0].pc \
            if len(evm_block.evm_ops) > 0 else None

    def __new_var(self) -> mem.Variable:
        """Construct and return a new variable with the next free identifier."""

        # Generate the new variable, numbering it by the implicit stack location
        # it came from.
        var = mem.Variable.top(name="V{}".format(self.stack_vars),
                               def_sites=ssle([TACLocRef(None, self.block_entry)]))
        self.stack_vars += 1
        return var

    def convert_block(self, evm_block: evm_cfg.EVMBasicBlock) -> TACBasicBlock:
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

    def __handle_evm_op(self, op: evm_cfg.EVMOp) -> None:
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

    def __gen_instruction(self, op: evm_cfg.EVMOp) -> None:
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
        elif op.opcode.is_missing():
            args = [TACArg(var=mem.Variable(values=[op.value], name="C"))]
            inst = TACOp(op.opcode, args, op.pc)
        elif op.opcode.is_log():
            args = [TACArg.from_var(var) for var in self.stack.pop_many(op.opcode.pop)]
            inst = TACOp(opcodes.LOG, args, op.pc)
        elif op.opcode == opcodes.MLOAD:
            args = [TACArg.from_var(self.stack.pop())]
            inst = TACAssignOp(new_var, op.opcode, args, op.pc)
        elif op.opcode == opcodes.MSTORE:
            args = [TACArg.from_var(var) for var in self.stack.pop_many(opcodes.MSTORE.pop)]
            inst = TACOp(op.opcode, args, op.pc)
        elif op.opcode == opcodes.MSTORE8:
            args = [TACArg.from_var(var) for var in self.stack.pop_many(opcodes.MSTORE8.pop)]
            inst = TACOp(op.opcode, args, op.pc)
        elif op.opcode == opcodes.SLOAD:
            args = [TACArg.from_var(self.stack.pop())]
            inst = TACAssignOp(new_var, op.opcode, args, op.pc)
        elif op.opcode == opcodes.SSTORE:
            args = [TACArg.from_var(var) for var in self.stack.pop_many(opcodes.SSTORE.pop)]
            inst = TACOp(op.opcode, args, op.pc)
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
