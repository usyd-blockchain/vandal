#!/usr/bin/env bats

load test_helper

# REPOROOT

# module (use as prefix in @test messages)
M="decompile:"

# module path
MP="bin/decompile"

@test "$M check --help success" {
    run $MP --help
}

@test "$M produces CFG visualisation and TSV exports for $HEX_INPUT/dao_hack.hex" {
    GRAPH_OUTFILE="graph.pdf"
    TSV_OUTFILES="block.facts def.facts use.facts edge.facts entry.facts exit.facts op.facts value.facts dom.facts imdom.facts pdom.facts impdom.facts"
    TSV_OUTDIR="tsv"

    rm -f $GRAPH_OUTFILE
    rm -rf $TSV_OUTDIR

    [ ! -f $GRAPH_OUTFILE ]
    [ ! -d $TSV_OUTDIR ]

    run $MP -g $GRAPH_OUTFILE -t $TSV_OUTDIR -d -b $HEX_INPUT/dao_hack.hex

    [ -s $GRAPH_OUTFILE ]
    [ -d $TSV_OUTDIR ]

    for f in $TSV_OUTFILES
    do
        [ -s $TSV_OUTDIR/$f ]
    done

    # clean up generated files
    rm $GRAPH_OUTFILE
    rm -rf $TSV_OUTDIR
}
