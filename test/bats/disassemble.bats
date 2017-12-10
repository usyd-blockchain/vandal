#!/usr/bin/env bats

load test_helper

# REPOROOT

# module (use as prefix in @test messages)
M="disassemble:"

# module path
MP="bin/disassemble"

@test "$M check --help success" {
    run $MP --help
}
