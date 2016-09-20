#! /bin/bash

# ------------------ #
# Usage instructions #
# ------------------ #

if [ $# -ne 1 ]
then
    echo "Creates a checked/unchecked send test with given solidity contract."
    echo "Requirements: solc, disasm, networkx, pydotplus, dot."
    echo ""
    echo "usage: $0 <solidity-contract>"
    exit
fi


# --------------------- #
# Generate helper files #
# --------------------- #

format="%-50s...\n"
filename=$(basename "$1")
filename="${filename%.*}"

# Use directory with filename as output for test case
if [ -d "$filename" ];
then
    printf $format "Directory already exists, overwriting instead"
else
    printf $format "Creating a new directory called $filename/"
    mkdir $filename
fi

# Generate supporting folders
printf $format "Creating directories for logical relations"
(cd $filename; mkdir lib; mkdir facts)

# Generate temporary directory with binary output of solidity compiler (bytecode)
printf $format "Generating bytecode from Solidity compiler"
solc --bin-runtime -o tempbin $1

# Copy input Solidity contract into new directory
cp $1 $filename

# Generate disasm output and save into new directory
printf $format "Generating disasm output"
for bytecode in tempbin/*
do
    sed -i '' -e '$a\' $bytecode
    disasm < $bytecode > $filename/$filename.dasm
done

# Generate TAC output and .dot file for visual graph and save into new directory
printf $format "Generating TAC output and .dot file for graph generation"
(cd $filename; ../../../bin/decompile --print --graph --file $filename.dasm > $filename.tac)

# Generate .facts files for Souffle in new directory
printf $format "Generating fact files for Souffle"
(cd $filename/facts; ../../../../bin/decompile --tsv --file ../$filename.dasm)

# Copy the checked/unchecked send Datalog template with new filename to new directory
printf $format "Copying over analysis library"
cp checked-send/lib/* $filename/lib/

# Generate PDF of the control flow graph in new directory
printf $format "Generating PDF of control flow graph"
dot -Tpdf $filename/cfg.dot -o $filename/cfg.pdf


# --------- #
# Run tests #
# --------- #
printf $format "Running tests via Souffle"
(cd $filename; souffle -D- -Ffacts lib/checked-send.dl > results.txt)


# -------- #
# Clean up #
# -------- #

# Remove temporary files
printf $format "Cleaning up"
rm -r tempbin
rm $filename/cfg.dot

echo "Done."
