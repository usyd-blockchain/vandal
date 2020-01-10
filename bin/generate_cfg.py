import src.exporter as exporter
import src.dataflow as dataflow
import src.tac_cfg as tac_cfg
import src.settings as settings

class Block:
    def __init__(self):
        self.pc = None
        self.pre = []
        self.next = []


def load_edges(runtime_bin):
    edges = {}
    res = vandal_cfg(runtime_bin).strip().split('\n')
    print(res)
    # temp_block = None
    #
    # i = 0
    #
    # while i < len(res):
    #     if res[i].startswith('Block'):
    #         temp_block = Block()


def vandal_cfg(input):
    settings.import_config(settings._CONFIG_LOC_)
    cfg = tac_cfg.TACGraph.from_bytecode(input)

    settings.import_config(settings._CONFIG_LOC_)

    dataflow.analyse_graph(cfg)

    return exporter.CFGStringExporter(cfg).export()

bin_dir = '../../../samples/Ballot.runbin'

load_edges(open(bin_dir,'r').read())
