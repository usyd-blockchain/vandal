from os.path import dirname, join, abspath
import sys
import glob

import pytest

src_path = join(dirname(abspath(__file__)), "../src")
sys.path.insert(0, src_path)

DISASM_TEST_PROGS = "disasm/*.dasm"
DISASM_TEST_PROGS = join(dirname(abspath(__file__)), DISASM_TEST_PROGS)

@pytest.fixture(params=list(glob.glob(DISASM_TEST_PROGS)))
def cfg(request):
  from tac_cfg import TACGraph
  import blockparse
  import optimise
  with open(request.param) as f:
    disasm = f.read()
  cfg = TACGraph.from_dasm(fileinput.input())
  optimise.fold_constants(cfg)
  cfg.recheck_jumps()
  yield cfg
