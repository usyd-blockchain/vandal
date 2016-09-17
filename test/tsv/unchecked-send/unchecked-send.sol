contract send {
    function() {
        msg.sender.send(100);
    }
}
