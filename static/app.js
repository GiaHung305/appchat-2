document.addEventListener("DOMContentLoaded", function() {
    const chatBox = document.getElementById('chat-box');
    const inputMsg = document.getElementById('message');
    const sendBtn = document.getElementById('send');
    const userList = document.getElementById('user-list');
    const roomTitle = document.getElementById('room-title');
    
    // Lấy username từ attribute trong HTML
    const username = document.body.dataset.username;
    let currentReceiverId = null;
    let currentGroupId = null;
    let currentRoom = "global"; // theo dõi room hiện tại
    
    // Kết nối Socket.IO
    const socket = io();

    // Thông báo server biết user join
    socket.emit("join_chat", { username });

    // Thêm click handler
    userList.querySelectorAll("li[data-room]").forEach(li => {
        li.addEventListener("click", () => {
            // reset active
            userList.querySelectorAll("li").forEach(el => el.classList.remove("active"));
            li.classList.add("active");

            // reset trạng thái
            currentReceiverId = null;
            currentGroupId = null;
            currentRoom = li.dataset.room;

            // Cập nhật title
            if (li.dataset.userId) {
                currentReceiverId = parseInt(li.dataset.userId);
                roomTitle.textContent = `Chat riêng với ${li.textContent.replace('👤 ', '')}`;
            } else if (li.dataset.groupId) {
                currentGroupId = parseInt(li.dataset.groupId);
                socket.emit("join_group", { group_id: currentGroupId });
                roomTitle.textContent = li.textContent.replace('👥 ', '');
            } else {
                roomTitle.textContent = "Phòng chung";
            }

            // clear chat box
            chatBox.innerHTML = "";

            // Fetch lịch sử tin nhắn
            let url = "/messages";
            if (currentReceiverId) {
                url += "?receiver_id=" + currentReceiverId;
            } else if (currentGroupId) {
                url += "?group_id=" + currentGroupId;
            }

            fetch(url)
                .then(res => res.json())
                .then(data => {
                    data.forEach(msg => {
                        const msgEl = renderMessage(msg, username);
                        chatBox.appendChild(msgEl);
                    });
                    chatBox.scrollTop = chatBox.scrollHeight;
                });
        });
    });

    // Render tin nhắn mới
    function renderMessage(data, currentUser) {
        const div = document.createElement("div");
        div.classList.add("msg");

        // Escape nội dung trước khi render
        const safeMsg = escapeHtml(data.message);

        if (data.sender_id === 0) {
            div.classList.add("system");
            div.innerHTML = `<div class="bubble">[${data.time}] ${safeMsg}</div>`;
        } else if (data.username === currentUser) {
            div.classList.add("self");
            div.innerHTML = `<div class="bubble">[${data.time}] <b>${data.username}</b>: ${safeMsg}</div>`;
        } else {
            div.classList.add("other");
            div.innerHTML = `<div class="bubble">[${data.time}] <b>${data.username}</b>: ${safeMsg}</div>`;
        }

        return div;
    }

    // Escape HTML để tránh XSS
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Nhận message từ server - CHỈ HIỂN THỊ KHI ĐÚNG ROOM
    socket.on("chat_message", function(data) {
        // Kiểm tra xem tin nhắn có thuộc room hiện tại không
        const shouldDisplay = checkMessageBelongsToCurrentRoom(data);
        
        if (shouldDisplay) {
            const msgEl = renderMessage(data, username);
            chatBox.appendChild(msgEl);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    });

    // Kiểm tra tin nhắn có thuộc room hiện tại không
    function checkMessageBelongsToCurrentRoom(data) {
        // Tin nhắn system luôn hiển thị ở phòng chung
        if (data.sender_id === 0 && currentRoom === "global") {
            return true;
        }

        // Nếu đang ở phòng chung
        if (currentRoom === "global") {
            // Chỉ hiển thị tin nhắn không có receiver_id và group_id cụ thể
            // (tin nhắn phòng chung sẽ không có metadata này)
            return !data.receiver_id && !data.group_id;
        }

        // Nếu đang ở chat riêng
        if (currentReceiverId) {
            // Hiển thị tin nhắn giữa mình và người đó
            return (data.sender_id === currentReceiverId) || 
                   (data.receiver_id === currentReceiverId);
        }

        // Nếu đang ở group
        if (currentGroupId) {
            return data.group_id === currentGroupId;
        }

        return false;
    }

    // Gửi tin nhắn
    function sendMessage() {
        const message = inputMsg.value.trim();
        if (message !== "") {
            socket.emit("send_message", { 
                message: message,
                receiver_id: currentReceiverId,
                group_id: currentGroupId
            });
            inputMsg.value = "";
        }
    }

    sendBtn.onclick = sendMessage;

    inputMsg.addEventListener("keypress", function(e) {
        if (e.key === "Enter") sendMessage();
    });
});