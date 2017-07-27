pragma solidity ^0.4.11;

contract Clamper {
    function fill(uint lim) returns (uint) {
        assembly {
            let i := 1
            let cond := 1
            incr:
                i := add (i, 0x1)
                1
                cond := lt(i, 0x100)
                jumpi(incr, cond)
            pop
        }
        return lim;
    }
}
