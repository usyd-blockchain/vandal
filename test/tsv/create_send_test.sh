#! /bin/bash

if [ $# -ne 1 ]
then
    echo "Creates a checked/unchecked send test with given solidity contract."
    echo "Requirements: solc, disasm, networkx, pydotplus, dot."
    echo ""
    echo "usage: $0 <solidity-contract>"
    exit
fi

filename=$(basename "$1")
filename="${filename%.*}"

# Use directory with filename as output for test case
if [ -d "$filename" ];
then
    echo "Directory already exists. Using ..."
else
    echo "Creating a new directory called $filename/ ..."
    mkdir $filename
fi

# Generate temporary directory with binary output of solidity compiler (bytecode)
echo "Generating bytecode from Solidity compiler ..."
solc --optimize --optimize-runs 300000 --bin -o tempbin $1

# Copy input Solidity contract into new directory
cp $1 $filename

# Generate disasm output and save into new directory
echo "Generating disasm output ..."
for bytecode in tempbin/*.bin
do
    sed -i '' -e '$a\' $bytecode
    disasm < $bytecode > $filename/$filename.dasm
done

# Generate TAC output and save into new directory
echo "Generating TAC output ..."
(cd $filename; ../../../bin/decompile $filename.dasm > $filename.tac)

# Generate .facts files for Souffle in new directory
echo "Generating fact files for Souffle ..."
(cd $filename; ../../../bin/decompile2 $filename.dasm)

# Copy the checked/unchecked send Datalog template with new filename to new directory
echo "Copying over template test ..."
cp checked-send/checked-send.dl $filename/$filename.dl

# Generatae cfg.dot file in new directory
echo "Generating .dot file for graph generation ..."
(cd $filename; ../../../bin/decompile3 $filename.dasm)

# Generate PDF of the control flow graph in new directory
echo "Generating PDF of control flow graph ..."
dot -Tpdf $filename/cfg.dot -o $filename/cfg.pdf

# Remove temporary files
echo "Cleaning up ..."
rm -r tempbin
rm $filename/cfg.dot

echo "Done."
