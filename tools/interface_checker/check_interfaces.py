import sys
from os import listdir
from os.path import abspath, dirname, join
import re
import json

src_path = join(dirname(abspath(__file__)), "../../")
sys.path.insert(0, src_path)

import src.dataflow as dataflow
import src.tac_cfg as tac_cfg
import src.settings as settings

INTERFACES_DIR = "interfaces"
CONTRACTS_DIR = "contracts"

func_re = re.compile("(\w|$)+\([^()]*\)")
sig_re = re.compile("(0x)?[0-9A-Fa-f]{8}")

def ensure_0x(string):
    if string.startswith("0x"):
        return string
    return "0x" + string

interfaces = {}

# Import eth-utils only if required.
import_eth_utils = False
for interface_file in listdir(INTERFACES_DIR):
    if interface_file.startswith('.'):
        continue
    with open(join(INTERFACES_DIR, interface_file), 'r') as f:
        for line in f:
            func_name = line.strip()
            if func_re.fullmatch(func_name) is not None or \
               func_re.fullmatch(func_name) is not None:
                   import_eth_utils = True
                   break
    if import_eth_utils:
        break
if import_eth_utils:
    from eth_utils import function_signature_to_4byte_selector as encode_sig
    from eth_utils import function_abi_to_4byte_selector as encode_abi

# Read Solidity function interfaces.
print("Reading interfaces...")
for interface_file in listdir(INTERFACES_DIR):
    if interface_file.startswith('.'):
        continue
    print("  - {}".format(interface_file))
    with open(join(INTERFACES_DIR, interface_file), 'r') as f:
        interface = {}
        # Handle a json contract ABI.
        if interface_file.endswith(".json"):
            abi = json.load(f)
            for func in [func for func in abi if func['type'] == 'function']:
                interface[func['name']] = ensure_0x(encode_abi(func).hex())
        # Otherwise just take a file with signatures listed line by line.
        else:
            for line in f:
                func_name = line.strip()
                func_match = func_re.fullmatch(func_name)
                sig_match = sig_re.fullmatch(func_name)
                
                # Handle either the unencoded string or the four-byte selector
                if func_match is not None:
                    interface[func_name] = ensure_0x(encode_sig(func_name).hex())
                elif sig_match is not None:
                    interface[func_name] = ensure_0x(func_name)
        interfaces[interface_file] = interface
print()

# Perform a minimal decompile and extract functions.
settings.import_config()
settings.extract_functions = True
settings.mark_functions = False
settings.max_iterations = 0
settings.analytics = False
settings.merge_unreachable = False
settings.remove_unreachable = False

for contract_file in listdir(CONTRACTS_DIR):
    with open(join(CONTRACTS_DIR, contract_file), 'r') as f:
        print("{}".format(contract_file), end="")
        cfg = tac_cfg.TACGraph.from_bytecode(f)
        dataflow.analyse_graph(cfg)
        sigs = [func.signature for func in cfg.function_extractor.public_functions]

        # Pad any short signatures with leading zeroes until eight nibbles long.
        for i in range(len(sigs)):
            sig = sigs[i]
            if len(sig) < 10:
                sigs[i] = ensure_0x("0"*(10 - len(sig)) + sig[2:])

        conforming = []
        for interface, interface_sigs in interfaces.items():
            if all(sig in sigs for sig in interface_sigs.values()):
                conforming.append(interface)
        
        if conforming:
            print(" conforms to {}.".format(", ".join(conforming)))
        else:
            print(": no matching interface provided.")

