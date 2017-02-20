var contractABI = web3.eth.contract();
contractABI.abi = [];

var code = "346000576101c2600081600f8239f360606040526000357c0100000000000000000000000000000000000000000000000000000000900480632530c9051461004f57806341c0e1b51461007b578063604a6fa91461008a5761004d565b005b61006560048080359060200190919050506100c7565b6040518082815260200191505060405180910390f35b610088600480505061012e565b005b6100976004805050610099565b005b33600060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908302179055505b565b60006000600066038d7ea4c6800090506001915081506001935083508382141561011f573373ffffffffffffffffffffffffffffffffffffffff16600082604051809050600060405180830381858888f19350505050505b839250610127565b5050919050565b600060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff1614156101bf57600060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16ff5b5b56";

var instance = contractABI.new({from:web3.eth.accounts[0], data: code, gas: 3000000}, function(e, contract){
    if(!e) {

      if(!contract.address) {
        console.log("Contract transaction send: TransactionHash: " + contract.transactionHash + " waiting to be mined...");

      } else {
        console.log("Contract mined! Address: " + contract.address);
        console.log(contract);
      }

    }
});
