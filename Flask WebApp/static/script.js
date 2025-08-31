$(document).ready(function() {
    $('#chat-toggle').click(function() {
        $('#chat-content').slideToggle('fast');
    });

    $('#send-button').click(function() {
        sendMessage();
    });

    $('#user-input').keypress(function(e) {
        if(e.which == 13) {
            sendMessage();
        }
    });

    function sendMessage() {
        var message = $('#user-input').val();
        if(message.trim() != '') {
            $('#chat-messages').append('<div class="message">' + message + '</div><br>');
            $('#user-input').val('');

            $.ajax({
                url: '/handle_message',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ message: message }),
                success: function(data) {
                    $('#chat-messages').append('<div class="message received">' + data.response + '</div><br>');
                    $('#chat-messages').scrollTop($('#chat-messages')[0].scrollHeight);
                }
            });
        }
     }
});
