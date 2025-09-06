
        let sessionId = null;
        let messagesLeft = 10;
        let sessionEnded = false;
        let chatMinimized = false;

        function toggleChat() {
            const widget = document.getElementById('chatWidget');
            const toggleBtn = document.getElementById('toggleBtn');
            const chatBody = document.getElementById('chatBody');

            chatMinimized = !chatMinimized;

            if (chatMinimized) {
                widget.classList.add('minimized');
                chatBody.style.display = 'none';
                toggleBtn.textContent = '+';
            } else {
                widget.classList.remove('minimized');
                chatBody.style.display = 'flex';
                toggleBtn.textContent = '−';
            }
        }

        function closeChat() {
            document.getElementById('chatWidget').style.display = 'none';
        }

        function refreshChat() {
            // Refresh functionality
            location.reload();
        }

        function openDetailsModal() {
            document.getElementById('detailsModal').classList.add('show');
        }

        function closeModal() {
            document.getElementById('detailsModal').classList.remove('show');
        }

        function nextStep() {
            // Validate required fields in step 1
            const fullName = document.getElementById('fullName').value.trim();
            const email = document.getElementById('email').value.trim();
            const international = document.querySelector('input[name="international"]:checked');
            const studentCategory = document.getElementById('studentCategory').value;
            const studentType = document.getElementById('studentType').value;

            if (!fullName || !email || !international || !studentCategory || !studentType) {
                alert('Please fill in all required fields.');
                return;
            }

            // Email validation
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                alert('Please enter a valid email address.');
                return;
            }

            // Move to step 2
            document.getElementById('step1Content').style.display = 'none';
            document.getElementById('step2Content').style.display = 'block';
        }

        function prevStep() {
            document.getElementById('step2Content').style.display = 'none';
            document.getElementById('step1Content').style.display = 'block';
        }

        async function submitDetails() {
            const formData = {
                full_name: document.getElementById('fullName').value.trim(),
                email: document.getElementById('email').value.trim(),
                international: document.querySelector('input[name="international"]:checked').value,
                student_category: document.getElementById('studentCategory').value,
                student_type: document.getElementById('studentType').value,
                grade: document.getElementById('grade').value,
                province: document.getElementById('province').value,
                school_name: document.getElementById('schoolName').value.trim(),
                student_number: document.getElementById('studentNumber').value.trim()
            };

            try {
                const response = await fetch('/api/save_user', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();

                if (data.success) {
                    sessionId = data.session_id;
                    closeModal();
                    enableChat();

                    // Add welcome message with user's name
                    addMessage('bot', `Thanks, ${formData.full_name}! I'm ready to help you with any questions about the University of Kimberly. You have ${messagesLeft} messages in this session. Let's start chatting! 😄`);
                } else {
                    alert('Error saving details: ' + data.error);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error connecting to server. Please try again.');
            }
        }

        function enableChat() {
            document.getElementById('messageInput').disabled = false;
            document.getElementById('sendButton').disabled = false;
            document.getElementById('inputWrapper').classList.remove('disabled');
            document.getElementById('messageInput').placeholder = "Enter your message";
            document.getElementById('messageInput').focus();
        }

        function disableChat() {
            document.getElementById('messageInput').disabled = true;
            document.getElementById('sendButton').disabled = true;
            document.getElementById('inputWrapper').classList.add('disabled');
            document.getElementById('messageInput').placeholder = "Session ended. Refresh to start a new session.";
        }

        function addMessage(sender, content) {
            const messagesContainer = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('message', sender);

            if (sender === 'bot') {
                messageDiv.innerHTML = '<span class="bot-icon">🤖</span>' + content.replace(/\n/g, '<br>');
            } else {
                messageDiv.innerHTML = content.replace(/\n/g, '<br>');
            }

            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function showTypingIndicator() {
            document.getElementById('typingIndicator').style.display = 'block';
            document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
        }

        function hideTypingIndicator() {
            document.getElementById('typingIndicator').style.display = 'none';
        }

        async function sendMessage() {
            const messageInput = document.getElementById('messageInput');
            const message = messageInput.value.trim();

            if (!message || sessionEnded) return;

            // Add user message
            addMessage('user', message);
            messageInput.value = '';
            adjustTextareaHeight();

            // Show typing indicator
            showTypingIndicator();

            try {
                const response = await fetch('/api/send_message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        session_id: sessionId,
                        message: message
                    })
                });

                const data = await response.json();
                hideTypingIndicator();

                if (data.success) {
                    addMessage('bot', data.response);
                    messagesLeft = data.messages_left;

                    if (data.session_ended) {
                        sessionEnded = true;
                        disableChat();
                    }
                } else {
                    if (data.error === 'limit_reached') {
                        addMessage('bot', data.message);
                        sessionEnded = true;
                        disableChat();
                    } else {
                        addMessage('bot', 'Sorry, there was an error processing your message. Please try again.');
                    }
                }
            } catch (error) {
                hideTypingIndicator();
                console.error('Error:', error);
                addMessage('bot', 'Sorry, there was a connection error. Please try again.');
            }
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        function adjustTextareaHeight() {
            const textarea = document.getElementById('messageInput');
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 80) + 'px';
        }

        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('detailsModal');
            if (event.target === modal) {
                closeModal();
            }
        }

        // Close modal with Escape key
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
