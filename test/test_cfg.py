import pytest
import cfg

@pytest.fixture(scope="module", params=[
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


class TestBasicBlock:

  def test_construction(self, basicblock):
    b, (en, ex) = basicblock
    assert b.entry == en
    assert b.exit == ex
    assert b.preds == []
    assert b.succs == []
    assert not b.has_unresolved_jump

  def test_str(self, basicblock):
    b, param = basicblock
    assert type(str(b)) is str

  def test_ident(self, basicblock):
    b, param = basicblock
    assert b.ident().startswith("0x") or
           b.ident().startswith("-0x")


class TestControlFlowGraph:
  def test_construction(self):
    class SubCFG(cfg.ControlFlowGraph):
      pass

    self.g = SubCFG()
    assert self.g.blocks == []
    assert self.g.root is None

  def test_accept(self):
    class SubCFGVisitor:
      def __init__(self):
        self.visited = []
      def visit(obj):
        visited.append(obj)

    v = SubCFGVisitor()
    self.g.accept(v)
    assert self.g in v.visited

  def test_edge_list(self):
    assert len(self.g.edge_list()) == 0

  def test_str(self):
    assert type(str(self.g)) is str
    assert len(str(self.g)) > 0

  def test_len(self):
    assert type(len(self)) is int
    assert len(self.g) == len(self.g.blocks)
