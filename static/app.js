document.addEventListener("DOMContentLoaded", function() {
    const chatBox = document.getElementById('chat-box');
    const inputMsg = document.getElementById('message');
    const sendBtn = document.getElementById('send');
    const userList = document.getElementById('user-list');
    // Lấy username từ attribute trong HTML
    const username = document.body.dataset.username;

    // Kết nối Socket.IO
    const socket = io();

    // Thông báo server biết user join
    socket.emit("join_chat", { username });

    // Nhận message từ server (dạng object JSON)
    socket.on("chat_message", function(data) {
        const div = document.createElement("div");
        div.classList.add("msg");

        if (data.sender_id === 0) {
            // Tin hệ thống
            div.classList.add("system");
            div.innerText = `[${data.time}] ${data.message}`;
        } else if (data.username === username) {
            div.classList.add("self");
            div.innerHTML = `[${data.time}] <b>${data.username}</b>: ${data.message}`;
        } else {
            // Tin của người khác
            div.classList.add("other");
            div.innerHTML = `[${data.time}] <b>${data.username}</b>: ${data.message}`;        }

        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    });

    // Gửi tin nhắn
    function sendMessage() {
        const message = inputMsg.value.trim();
        if (message !== "") {
            socket.emit("send_message", { message });
            inputMsg.value = "";
        }
    }

    sendBtn.onclick = sendMessage;

    inputMsg.addEventListener("keypress", function(e) {
        if (e.key === "Enter") sendMessage();
    });
});
