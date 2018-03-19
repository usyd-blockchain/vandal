## Contract Interface Checker ##

Place smart contract interfaces into the `interfaces/` directory.
An interface may take one of two forms:
   * A standard ethereum contract ABI, in which case the filename must end with `.json`.
   * A text file containing function signatures, one per line. These may be either a function signature or an encoded four-byte method ID, as described [here](https://solidity.readthedocs.io/en/develop/abi-spec.html#function-selector-and-argument-encoding). Any lines not recognised as one of these forms will be ignored.

This script requires [eth-utils](https://github.com/ethereum/eth-utils), but it will not be imported if interfaces contain only encoded method IDs.

Place smart contracts into the `contracts/` directory. These should be (solidity) compiled bytecode contracts.

Then run `check_interfaces.py`.
