import sys
from os.path import abspath, dirname, join

src_path = join(dirname(abspath(__file__)), "..")
sys.path.insert(0, src_path)

import src.exporter as exporter
import src.dataflow as dataflow
import src.tac_cfg as tac_cfg
import src.settings as settings


# import logging


def vandal_cfg(input):
    # logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    # logging.getLogger().setLevel(logging.INFO)
    # logging.info("asd")
    settings.import_config(settings._CONFIG_LOC_)
    cfg = tac_cfg.TACGraph.from_bytecode(input)

    settings.import_config(settings._CONFIG_LOC_)

    dataflow.analyse_graph(cfg)

    res = exporter.CFGStringExporter(cfg).export()
    return res
