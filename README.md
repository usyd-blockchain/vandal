[![Build Status](https://travis-ci.org/usyd-blockchain/vandal.svg?branch=master)](https://travis-ci.org/usyd-blockchain/vandal)

# Vandal

Vandal is a static program analysis framework for Ethereum smart contract
bytecode. It decompiles EVM bytecode or disassembly to an equivalent
intermediate representation that encodes contract's control flow graph. This
representation removes all stack operations and thereby exposes data
dependencies which are otherwise obscured. This information is then fed, with
a Datalog specification, into an analysis engine for the extraction of program
properties.

Vandal was developed as a platform for detecting potential security
vulnerabilities in compiled contract bytecode, and supports rapid development
and prototyping of new vulnerability specifications written in Datalog.
However, this approach is more general: using Vandal, it is possible to
construct arbitrary program analyses over the intermediate representation of
a contract. Vandal includes a static program analysis library that predefines
many useful Datalog relations.

The main components of Vandal are:
1. Disassembler (Python)
2. Decompiler (Python)
3. Analysis library (Datalog)

The decompiler and disassembler share many of the same modules located in
`src/`. The Datalog analysis library is designed to run on the Souffle Datalog
engine, and is located in `datalog/`.

A more comprehensive description of the Vandal Framework is [available on the
Wiki](https://github.com/usyd-blockchain/vandal/wiki).

### Publications

* _Vandal: A Scalable Security Analysis Framework for Smart Contracts_,
 Lexi Brent, Anton Jurisevic, Michael Kong, Eric Liu, Francois
  Gauthier, Vincent Gramoli, Ralph Holz, Bernhard Scholz, Technical Report, School of Information Technologies, The University of Sydney, Sydney, Australia, September 2018. [[pdf](https://arxiv.org/pdf/1809.03981.pdf)] [[BibTeX](pubs/Vandal18.bib)]

* _MadMax: Surviving Out-of-Gas Conditions in Ethereum Smart Contracts_,
Neville Grech, Michael Kong, Anton Jurisevic, Lexi Brent, Bernhard Scholz, Yannis Smaragdakis, SPLASH 2018 OOPSLA, Boston, November 2018. [[pdf](pubs/Grech18-OOPSLA.pdf)] [[BibTeX](pubs/Grech18.bib)]

* _A Scalable Method to Analyze Gas Costs, Loops and Related Security Vulnerabilities on the Ethereum Virtual Machine_, Michael Kong, Honours Thesis, November 2017, School of Information Technologies, The University of Sydney. [[pdf](pubs/MKong17.pdf)] [[BibTeX](pubs/MKong17.bib)]

## Prerequisites

An installation of **Python 3.5** or later is required, alongside various
packages. The recommended way to install all package dependencies is using
`pip` and our provided `requirements.txt`, like so:

```
$ pip install -r requirements.txt
```

To run the Datalog analysis, Souffle should be installed with the `souffle`
binary in `$PATH`. Installation instructions can be found
[here](https://souffle-lang.github.io/download/).

## Usage

The decompiler and disassembler, respectively, can be invoked as follows:

```
$ bin/decompile examples/dao_hack.hex
$ bin/disassemble -p examples/dao_hack.hex
```

Some cursory information can be obtained by producing verbose debug output:

```
$ bin/decompile -n -v examples/dao_hack.hex
```

For manual inspection of a contract, HTML graph output can be handy:

```
$ bin/decompile -n -v -g graph.html examples/dao_hack.hex
```

This produces an interactive page, `graph.html`. If clicked, each node on this
page displays the code in the basic block it represents, an equivalent
decompiled block of code, and some accompanying information.

For additional usage information, use `--help`:

```
$ bin/decompile --help
$ bin/disassemble --help
```

To run the entire analysis pipeline including Datalog analyses, there is a glue
script called `bin/analyze.sh`:

```
$ mkdir results
$ cd results
$ ../bin/analyze.sh ../examples/use_of_origin.hex ../datalog/demo_analyses.dl
```

The above command will first decompile the given bytecode and then run Souffle
with the specified Datalog specification. In this case, the `demo_analyses.dl`
specification will warn us about the presence of several vulnerabilities.
Souffle will create one CSV file in the current directory for each Datalog
output relation.

```
$ ls -l
total 12K
-rw-rw-r-- 1  0 Nov 27 15:50 checkedCallStateUpdate.csv
-rw-rw-r-- 1  0 Nov 27 15:50 destroyable.csv
-rw-rw-r-- 1  6 Nov 27 15:50 originUsed.csv
-rw-rw-r-- 1  0 Nov 27 15:50 reentrantCall.csv
-rw-rw-r-- 1 18 Nov 27 15:50 uncheckedCall.csv
-rw-rw-r-- 1  6 Nov 27 15:50 unsecuredValueSend.csv
```

Here we can see that `originUsed.csv` is non-zero in size, meaning that at
least one use of the `ORIGIN` operation in this contract has been flagged by
the Datalog analysis. We can see that the contract has also been flagged for
`uncheckedCall` and `unsecuredValueSend`.

### Writing Analyses

As a starting point, you can view the code for our demonstration analyses in
`datalog/demo_analyses.dl`. These are explained in the [Vandal technical
report](https://arxiv.org/abs/1809.03981).

To write your own analyses, we recommend starting by copying `demo_analyses.dl`
to a new file, and then removing the irrelevant Datalog relations. A basic demo
tutorial is [available on the Vandal
Wiki](https://github.com/usyd-blockchain/vandal/wiki/Demo:-Writing-an-Analysis-with-Vandal).

### Decompiler Configuration

Configuration options for Vandal's decompiler can be set in `bin/config.ini`.
A default value and brief description of each option is provided in
`src/default_config.ini`. Any of these settings can also be overridden with the
`-c` command-line flag in a `"key=value"` fashion.

### Decompilation Example

A contract, `loop.sol`:
```javascript
contract TestLoop {
    function test() returns (uint) {
        uint x = 0;
        for (uint i = 0; i < 256; i++) {
            x = x*i + x;
        }
        return x;
    }
}
```

Compiled into runtime code, held in `loop.hex`, then decompiled
and output into an html file:
```
$ solc --bin-runtime loop.sol | tail -n 1 > loop.hex
$ bin/decompile -n -v -c "remove_unreachable=1" -g loop.html loop.hex
```


## Code Documentation

Sphinx is used to generate code documentation for the decompiler. Sphinx source
files are in `doc/source/`. To build clean HTML documentation, run:

```
$ make clean doc
```

from the repository root. The generated documentation will be placed in
`doc/build/html/index.html`.


## Tests

To run all tests, first initialize git submodules:

```
$ git submodule update --init --recursive
$ git pull --recurse-submodules
```

Then, run:

```
$ make test
```

Currently Vandal only contains tests for the decompiler. There are no tests for
the Datalog code.
