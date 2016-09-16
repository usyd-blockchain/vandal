contract send {
    function() {
        if (!msg.sender.send(100)) {
            throw;
        }
    }
}
