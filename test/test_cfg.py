import pytest

import patterns
import cfg

@pytest.fixture(params=[
  (1,5),
  (12213,72728),
  (-12312313,-1),
  (99932478932874293434,-128918723982173),
])
def basicblock(request):
  class SubBlock(cfg.BasicBlock):
    def __init__(self, entry, exit):
      super().__init__(entry, exit)
  return SubBlock(*request.param), request.param

@pytest.fixture
def graph(request):
  class SubCFG(cfg.ControlFlowGraph):
    def __init__(self):
      super().__init__()
  return SubCFG()

#### Tests: ####

class TestBasicBlock:
  def test_construction(self, basicblock):
    b, (en, ex) = basicblock
    assert b.entry == en
    assert b.exit == ex
    assert b.preds == [], "preds must start empty"
    assert b.succs == [], "succs must start empty"
    assert not b.has_unresolved_jump, "has_unresolved_jump must start as False"

  def test_str(self, basicblock):
    b, param = basicblock
    assert type(str(b)) is str, "__str__ must return a string"

  def test_ident(self, basicblock):
    b, param = basicblock
    assert (b.ident().startswith("0x") or
            b.ident().startswith("-0x")), "ident() must return hex string"


class TestControlFlowGraph:
  def test_construction(self, graph):
    assert graph.blocks == []
    assert graph.root is None

  def test_accept(self, graph):
    class SubCFGVisitor(patterns.Visitor):
      def __init__(self):
        self.visited = []
      def visit(obj):
        visited.append(obj)

    v = SubCFGVisitor()
    assert len(v.visited) == 0
    graph.accept(v)
    # TODO

  def test_edge_list(self, graph):
    assert len(graph.edge_list()) == 0

  def test_str(self, graph):
    assert type(str(graph)) is str

  def test_len(self, graph):
    assert type(len(graph)) is int
    assert len(graph) == len(graph.blocks)
