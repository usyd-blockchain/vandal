import pytest

import patterns
import cfg

@pytest.fixture(params=[
  (10, 53),
  (12213, 72728),
  (23832432432224234324324, 1),
  (1, 38947298347983274893274),
  (0, 0),
  (0, 1),
  (1, 0),
])
def basicblock(request):
  """
  Returns: a pair: block, (en, ex) where:
    - block is a valid SubBlock instance
    - (en, ex) are the entry and exit values used to create block
  """
  return SubBlock(*request.param), request.param

@pytest.fixture
def graph():
  """
  Returns: a valid SubCFG instance.
  """
  class SubCFG(cfg.ControlFlowGraph):
    """
    Simple implementation of ControlFlowGraph ABC for testing implemented
    methods.
    """
    def __init__(self):
      super().__init__()
  return SubCFG()

@pytest.fixture(params=[
  (-12312313, -1),
  (99932478932874293434, -128918723982173),
  (0, -213213123123),
  ( -21321314338383423, 0),
  (-1238921738, 89273981273),
  (-1, 1),
  (1, -1),
])
def negative_pairs(request):
  """Returns: a pair (a, b) where at least one of a, b is a negative integer"""
  return request.param

@pytest.fixture(params = [
  [
    [ (1,2), (3,9), (10,100) ], # blocks
    [ (1,3), (3,10), (1,10)  ]  # edges
  ],
  [
    [ (1,25), (35,9999), (26,35) ], # blocks
    [ (1,26) ]  # edges
  ],
  [
    [], # blocks
    []  # edges
  ],
  [
    [ (1,10) ], # blocks
    []  # edges
  ],
])
def blocks_edges(request):
  """Returns: a list of [blocks[], edges[]]"""
  return request.param

class SubBlock(cfg.BasicBlock):
  """
  Simple implementation of BasicBlock ABC for testing its implemented methods
  """
  def __init__(self, entry, exit):
    super().__init__(entry, exit)

#### Tests: ####

class TestBasicBlock:
  def test_invalid_construction(self, negative_pairs):
    en, ex = negative_pairs
    with pytest.raises(ValueError,
                       message="Negative entry/exit val should raise ValueError"):
      b = SubBlock(en, ex)

  def test_construction(self, basicblock):
    b, (en, ex) = basicblock
    assert b.entry == en
    assert b.exit == ex
    assert b.preds == [], "preds must start empty"
    assert b.succs == [], "succs must start empty"
    assert not b.has_unresolved_jump, "has_unresolved_jump must start as False"

  def test_ident(self, basicblock):
    b, param = basicblock
    assert b.ident().startswith("0x"), \
           "ident() must return hex string with '0x' prefix"


class TestControlFlowGraph:
  def test_construction(self, graph):
    assert graph.blocks == []
    assert graph.root is None

  def test_accept(self, graph):
    class SubCFGVisitor(patterns.Visitor):
      """Simple visitor implementation used for testing accept()"""
      def __init__(self):
        self.visited = []
      def visit(self, obj):
        self.visited.append(obj)
    # instantiate our simple visitor and ensure visited[] starts empty
    v = SubCFGVisitor()
    assert len(v.visited) == 0
    # visit our graph
    graph.accept(v)
    assert graph in v.visited, "accept() must visit the graph itself"
    for b in graph.blocks:
      assert b in v.visited, "accept() must visit all blocks in the graph"

  def test_edge_list(self, graph, blocks_edges):
    blocks, edges = blocks_edges
    blocks = {b[0]: SubBlock(*b) for b in blocks}

    assert len(graph.edge_list()) == 0, "graph must start empty"

    # Add blocks to graph and build edge connections
    graph.blocks.extend(blocks.values())
    for e_en, e_ex in edges:
      # Check the edge isn't in the edge_list() already
      assert (e_en, e_ex) not in graph.edge_list()

      # Connect the edge in the corresponding blocks
      pred = blocks[e_en]
      succ = blocks[e_ex]
      if pred not in succ.preds:
        succ.preds.append(pred)
      if succ not in pred.succs:
        pred.succs.append(succ)

      # Now check that the edge we just added is in edge_list()
      edges = [tuple(int(n, 16) for n in e) for e in graph.edge_list()]
      assert (e_en, e_ex) in edges

    assert len(graph.edge_list()) == len(edges), \
           "unexpected number of edges in the graph"

  def test_str(self, graph, blocks_edges):
    blocks = tuple(SubBlock(*b) for b in blocks_edges[0])
    # the graph's str() should contain each block's str(). Test this by:
    # loop over a bunch of blocks, add each to the graph sequentially
    for i, b in enumerate(blocks):
      # check that the block's str() is not in the graph's str() initially:
      assert str(b) not in str(graph)
      # ensure that the str() of each previously-added block in the graph is
      # in the graph's current str():
      for b_prev in blocks[:i]:
        assert str(b_prev) in str(graph)
      # add the block to the graph:
      graph.blocks.append(b)
      # ensure its str() is in the graph's str()
      assert str(b) in str(graph)

  def test_len(self, graph):
    # graph starts out empty
    assert len(graph) == len(graph.blocks) == 0
    # add a block
    graph.blocks.append(SubBlock(1,2))
    assert len(graph) == len(graph.blocks) == 1
    # add another block
    graph.blocks.append(SubBlock(3,4))
    assert len(graph) == len(graph.blocks) == 2
