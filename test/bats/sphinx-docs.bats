#!/usr/bin/env bats

load test_helper

# REPOROOT

# module (use as prefix in @test messages)
M="sphinx (make clean doc):"

# module path
MP="make clean doc"

# test decompilation of each *.hex example
@test "$M testing successful documentation generation" {
    run $MP
    assert_success
    refute_output --partial "failed to import"
    refute_output --partial "ERROR:"
    refute_output --partial "reference to nonexisting document"
}
