# Bulk Contract Analysis Scripts

These scripts enable bulk analysis of contract bytecodes scraped from the chain.

## analyse.rb

A "glue" script, runs a given contract through Vandal, then through Souffle,
and produces a single CSV row as output, listing the vulnerabilities detected.

## generate_batches.py

Lists the contents of `DIRECTORY/*_runtime.hex` and divides the list of files
among N txt files to be used as analysis batches

## run_batch.sh

For each line of a given TXT file, runs `analyse.rb` with that line as the path
of the contract to be analysed.

## run_all.sh

For each file in `./batch_*.txt`, runs one instance of `run_batch.sh` in the
background, redirecting stdout and stderr to separate files in the current
working directory.

## How to use

```sh
$ ./generate_batches.py ./sample 5
$ ./run_all.sh
$ tail -f ./*.out ./*.err
```

- You may need to modify `run_batch.sh` to set the path to `analyse.rb` and `spec.dl`.
- You may need to modify `analyse.rb` to set timeouts and the paths to `bin/decompile` and `souffle`.
