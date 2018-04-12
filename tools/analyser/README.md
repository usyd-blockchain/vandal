# Bulk Contract Analysis Scripts

These scripts enable bulk analysis of contract bytecodes scraped from the chain.

## analyse.rb

A "glue" script, runs a given contract through Vandal, then through Souffle,
and produces a single CSV row as output, listing the vulnerabilities detected.

```
➜ ./analyse.rb --help
Usage: analyse.rb SPEC_FILE BYTECODE_FILE
``

## generate_batches.py

Lists the contents of `DIRECTORY/*_runtime.hex` and divides the list of files
among N txt files to be used as analysis batches

```
➜ ./generate_batches.py --help
Usage: generate_batches.py CONTRACT_DIR NUM_BATCHES
```

## run_batch.sh

For each line of a given TXT file, runs `analyse.rb` with that line as the path
of the contract to be analysed.

```
➜ ./run_batch.sh --help
Usage: run_batch.sh CONTRACT_FILE [DATALOG_SPEC]
Note: this script should generally only be executed by run_all.sh
```

## run_all.sh

For each file in `./batch_*.txt`, runs one instance of `run_batch.sh` in the
background, redirecting stdout and stderr to separate files in the current
working directory.

```
➜ ./run_all.sh --help
Usage: run_all.sh [DATALOG_SPEC]
```

## How to use

```sh
$ ./generate_batches.py ./sample 5
$ ./run_all.sh ./spec.dl
$ tail -f *.out *.err
```

- You may need to modify `analyse.rb` to set timeouts
- `analyse.rb` expects `souffle` to be on the system `$PATH`
