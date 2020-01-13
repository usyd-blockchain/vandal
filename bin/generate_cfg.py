import src.exporter as exporter
import src.dataflow as dataflow
import src.tac_cfg as tac_cfg
import src.settings as settings


def vandal_cfg(input):
    settings.import_config(settings._CONFIG_LOC_)
    cfg = tac_cfg.TACGraph.from_bytecode(input)

    settings.import_config(settings._CONFIG_LOC_)

    dataflow.analyse_graph(cfg)

    res = exporter.CFGStringExporter(cfg).export()
    return res


