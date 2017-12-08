## Running creation bytecode on a private blockchain

1. convert runtime to creation bytecode using converter.py;
2. create the contract itself:
```
var contractABI = web3.eth.contract();
contractABI.abi = [];
var code = (insert converted code here)

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
```
3. make an account: `geth --dev account new`;
4. start geth, `geth --dev console`;
5. unlock the account `personal.unlockAccount(eth.accounts[0])`;
6. create contract with loadScript(<path to above script shit>);
7. transactions are sent with `eth.call` (if you want return data) and `eth.sendTransaction` (if you want to send money);
`eth.sendTransaction({from: eth.accounts[0], to: '0xeeda88dbb20bccb3efc588abdc5e8c2d964ce483', gas: 300000, gasPrice: 1, data: '0xa9059cbb', value: 10000}, console.log)`
`web3.eth.call({from: eth.accounts[0], to: '0xeeda88dbb20bccb3efc588abdc5e8c2d964ce483', gas: 3000000, gasPrice: 1, data: '0xa9059cbb', value: 100000}, console.log);`
8. mine the block, `miner.start()` and `miner.stop()`

