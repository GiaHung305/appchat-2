document.addEventListener("DOMContentLoaded", function() {
    const chatBox = document.getElementById('chat-box');
    const inputMsg = document.getElementById('message');
    const sendBtn = document.getElementById('send');

    // Mở WebSocket, server sẽ lấy username từ cookie httponly
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/chat`);
    ws.onmessage = function(event) {
    const msg = document.createElement('div');
    msg.classList.add("msg");

    // Nếu là thông báo hệ thống (⚡ hoặc ⚠️)
    if(event.data.startsWith("⚡") || event.data.startsWith("⚠️")) {
        msg.classList.add("system");
    }

    msg.innerHTML = event.data;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
}


    ws.onclose = function() {
        const msg = document.createElement('div');
        msg.classList.add("system");
        msg.innerHTML = "⚠️ Bạn đã rời phòng hoặc kết nối bị mất";
        chatBox.appendChild(msg);
    }

    // Gửi tin nhắn khi nhấn nút
    sendBtn.onclick = function() {
        const message = inputMsg.value.trim();
        if (message !== '') {
            ws.send(message);
            inputMsg.value = '';
        }
    }

    // Gửi tin nhắn khi nhấn Enter
    inputMsg.addEventListener("keypress", function(e) {
        if (e.key === "Enter") sendBtn.click();
    });
});
