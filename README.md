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
Wiki](https://github.com/usyd-blockchain/vandal/wiki), along with a [getting started guide](https://github.com/usyd-blockchain/vandal/wiki/Getting-Started-with-Vandal).

### Getting Started

Please see the [getting started wiki page](https://github.com/usyd-blockchain/vandal/wiki/Getting-Started-with-Vandal).

### Publications

* _Vandal: A Scalable Security Analysis Framework for Smart Contracts_,
 Lexi Brent, Anton Jurisevic, Michael Kong, Eric Liu, Francois
  Gauthier, Vincent Gramoli, Ralph Holz, Bernhard Scholz, Technical Report, School of Computer Science, The University of Sydney, Sydney, Australia, September 2018. [[pdf](https://arxiv.org/pdf/1809.03981.pdf)] [[BibTeX](pubs/Vandal18.bib)]

* _MadMax: Surviving Out-of-Gas Conditions in Ethereum Smart Contracts_,
Neville Grech, Michael Kong, Anton Jurisevic, Lexi Brent, Bernhard Scholz, Yannis Smaragdakis, SPLASH 2018 OOPSLA, Boston, November 2018. [[pdf](pubs/Grech18-OOPSLA.pdf)] [[BibTeX](pubs/Grech18.bib)]

* _A Scalable Method to Analyze Gas Costs, Loops and Related Security Vulnerabilities on the Ethereum Virtual Machine_, Michael Kong, Honours Thesis, November 2017, School of Computer Science, The University of Sydney. [[pdf](pubs/MKong17.pdf)] [[BibTeX](pubs/MKong17.bib)]

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
