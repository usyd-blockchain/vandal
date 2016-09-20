import cfg

class SubBlock(cfg.BasicBlock):
  def __init__(self, entry, exit):
    super().__init__(entry, exit)

class TestBasicBlock:
  # TODO: Make this a fixture
  b = SubBlock(1,5)

  def test_construction(self):
    assert self.b.entry == 1
    assert self.b.exit == 5
    assert self.b.preds == []
    assert self.b.succs == []
    assert not self.b.has_unresolved_jump

  def test_str(self):
    assert type(str(self.b)) == str

  def test_ident(self):
    assert self.b.ident().startswith("0x")


class SubCFG(cfg.ControlFlowGraph):
  def __init__(self):
    super().__init__()

class TestControlFlowGraph:
  g = SubCFG()

  def test_construction(self):
    pass
