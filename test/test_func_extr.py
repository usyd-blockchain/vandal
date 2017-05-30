import pytest
import func_extr
import tac_cfg
import dataflow
import os

dir_path = os.path.dirname(os.path.realpath(__file__))

# Format: filename, start blocks, end blocks
@pytest.fixture(scope="module",
                params=[
  ('/hex/basic_example.hex', ["0xce", "0x44", "0x75", "0x42"], ["0x5f", "0xeb", "0x90", "0x42"], 5),
  ('/hex/example_two.hex', ["0x96", "0x2a", "0x4c", "0x28"], ["0x28", "0x7d", "0x3a"], 5),
  ('/hex/recursion.hex', ["0x93", "0x2a", "0x28", "0x4c"], ["0x28", "0xb1", "0x3a"], 5),
  ('/hex/mutual_recursion.hex', ["0xa2", "0xc5", "0x2a", "0x4c", "0x28"], ["0x28", "0x3a", "0xc0"], 6)
])

def funcs(request):
  """
  Returns: a FunExtract object extracted from a file, 
  """
  f = open(dir_path + request.param[0], 'r')
  cfg = tac_cfg.TACGraph.from_bytecode(f.read(), False)
  dataflow.analyse_graph(cfg, -1, -1)
  funcs = func_extr.FunExtract(cfg)
  funcs.extract()
  return (funcs, request.param[1], request.param[2], request.param[3])

### TESTS ###

class TestFunctionExtraction:

  def test_function_construction(self):
    func = func_extr.Function()
    assert func.body == []
    assert func.mapping == {}
    assert func.end_block == None
    assert func.start_block == None

  def test_function_body_length(self, funcs):
    fun_extr = funcs[0]
    functions = fun_extr.export(False)
    # Check has identified all four functions
    assert len(functions.split("Function")) == funcs[3]

  def test_function_start_blocks(self, funcs):
    fun_extr = funcs[0]
    start_blocks = funcs[1]
    for f in fun_extr.functions:
      assert f.start_block.ident() in start_blocks


  def test_function_end_blocks(self, funcs):
    fun_extr = funcs[0]
    end_blocks = funcs[2]
    for f in fun_extr.functions:
      assert f.end_block.ident() in end_blocks

  # Tests on helper functions within the func_extr module

  def test_find_CALLDATALOAD(self, funcs):
    fun_extr = funcs[0]
    calldataload_block = fun_extr.find_calldataload()
    # CALLDATALOAD block will be 0x0 or one of its successors
    start_block = fun_extr.tac.get_block_by_ident("0x0")
    poss_blocks = [start_block]
    for b in start_block.succs:
      poss_blocks.append(b)
    assert calldataload_block in poss_blocks

  def test_find_private_func_start(self, funcs):
    func_extr = funcs[0]
    start_blocks = funcs[1]
    for b in start_blocks:
      block = func_extr.tac.get_block_by_ident(b)
      # Public function starts have one predecessor
      if len(block.preds) > 1:
        assert func_extr.is_private_func_start(block) is not None
      else:
        assert func_extr.is_private_func_start(block) is None
    # 0x0 Can never be a private function start
    assert func_extr.is_private_func_start(func_extr.tac.get_block_by_ident("0x0")) is None

  def test_reachable(self, funcs):
    func_extr = funcs[0]
    # Check 0x0 can reach every block and no block can reach 0x0
    start_block = func_extr.tac.get_block_by_ident("0x0")
    for block in func_extr.tac.blocks:
      # check not part of uncompleted graph
      if len(block.preds) != 0 and len(block.succs) != 0:
        assert func_extr.reachable(start_block, [block])
      if block != start_block:
        assert func_extr.reachable(block, [start_block]) == False

