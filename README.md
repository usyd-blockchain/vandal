[![Build Status](https://travis-ci.org/usyd-blockchain/vandal.svg?branch=master)](https://travis-ci.org/usyd-blockchain/vandal)

# Vandal

Vandal is a static program analysis framework for Ethereum smart contract
bytecode, developed at [The University of
Sydney](https://sydney.edu.au/engineering/about/school-of-computer-science.html).
It decompiles an EVM bytecode program to an equivalent intermediate
representation that encodes the program's control flow graph. This
representation removes all stack operations, thereby exposing data dependencies
that are otherwise obscured. This information is then fed, with a Datalog
specification, into the [Souffle](http://souffle-lang.org) analysis engine for
the extraction of program properties.

A more comprehensive description of the Vandal Framework is [available on the
Wiki](https://github.com/usyd-blockchain/vandal/wiki), along with a [getting started guide](https://github.com/usyd-blockchain/vandal/wiki/Getting-Started-with-Vandal).

Vandal is licensed under the [BSD 3-Clause License](/LICENSE).

## Publications

* _Vandal: A Scalable Security Analysis Framework for Smart Contracts_,
 Lexi Brent, Anton Jurisevic, Michael Kong, Eric Liu, Francois
  Gauthier, Vincent Gramoli, Ralph Holz, Bernhard Scholz, Technical Report, School of Computer Science, The University of Sydney, Sydney, Australia, September 2018. [[pdf](https://arxiv.org/pdf/1809.03981.pdf)] [[BibTeX](pubs/Vandal18.bib)]

* _MadMax: Surviving Out-of-Gas Conditions in Ethereum Smart Contracts_,
Neville Grech, Michael Kong, Anton Jurisevic, Lexi Brent, Bernhard Scholz, Yannis Smaragdakis, SPLASH 2018 OOPSLA, Boston, November 2018. [[pdf](pubs/Grech18-OOPSLA.pdf)] [[BibTeX](pubs/Grech18.bib)]

* _A Scalable Method to Analyze Gas Costs, Loops and Related Security Vulnerabilities on the Ethereum Virtual Machine_, Michael Kong, Honours Thesis, November 2017, School of Computer Science, The University of Sydney. [[pdf](pubs/MKong17.pdf)] [[BibTeX](pubs/MKong17.bib)]

## Resources

- [Overview of Vandal](https://github.com/usyd-blockchain/vandal/wiki)
- [Getting Started with Vandal](https://github.com/usyd-blockchain/vandal/wiki/Getting-Started-with-Vandal)
- [Demo: Creating a new analysis specification in Vandal](https://github.com/usyd-blockchain/vandal/wiki/Demo:-Creating-a-new-analysis-specification-in-Vandal)
- [Vandal technical paper](https://arxiv.org/pdf/1809.03981.pdf)
- [Summary of EVM Instructions](https://github.com/usyd-blockchain/vandal/wiki/Summary-of-EVM-Instructions)
