// 聊天系统前端交互逻辑
document.addEventListener('DOMContentLoaded', function() {
    // 获取DOM元素
    const messageList = document.getElementById('message-list');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const userIdElement = document.getElementById('user-id');
    const roomIdElement = document.getElementById('room-id');
    const userList = document.getElementById('user-list');
    const statusIndicator = document.getElementById('status-indicator');
    const connectionStatus = document.getElementById('connection-status');
    
    // 获取用户ID和房间ID
    const userId = userIdElement ? userIdElement.value : 'anonymous';
    const roomId = roomIdElement ? roomIdElement.value : 'default';
    
    // WebSocket连接
    let socket = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    let reconnectTimeout = 1000; // 初始重连延迟1秒
    
    // 连接WebSocket
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${roomId}/${userId}`;
        
        // 如果已有连接，先关闭
        if (socket) {
            socket.close();
        }
        
        // 创建新连接
        socket = new WebSocket(wsUrl);
        
        // 连接建立时
        socket.onopen = function(e) {
            console.log('WebSocket连接已建立');
            showSystemMessage('已连接到聊天服务器');
            statusIndicator.className = 'status-indicator';
            connectionStatus.textContent = '已连接';
            reconnectAttempts = 0;
            reconnectTimeout = 1000;
        };
        
        // 接收消息
        socket.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('收到消息:', data);
            
            switch(data.type) {
                case 'chat':
                    addChatMessage(data);
                    break;
                case 'system':
                    showSystemMessage(data.content);
                    break;
                case 'user_list':
                    updateUserList(data.users);
                    break;
                case 'error':
                    showErrorMessage(data.content);
                    break;
                case 'private':
                    addPrivateMessage(data);
                    break;
            }
        };
        
        // 连接关闭
        socket.onclose = function(event) {
            if (event.wasClean) {
                console.log(`连接已关闭，代码=${event.code} 原因=${event.reason}`);
                showSystemMessage(`连接已关闭: ${event.reason}`);
            } else {
                console.error('连接意外断开');
                showSystemMessage('连接意外断开，尝试重新连接...');
            }
            
            statusIndicator.className = 'status-indicator danger';
            connectionStatus.textContent = '已断开';
            
            // 尝试重新连接
            if (reconnectAttempts < maxReconnectAttempts) {
                setTimeout(() => {
                    reconnectAttempts++;
                    connectWebSocket();
                    reconnectTimeout *= 2; // 指数退避重连策略
                }, reconnectTimeout);
            } else {
                showSystemMessage('无法重新连接到服务器，请刷新页面重试');
            }
        };
        
        // 连接错误
        socket.onerror = function(error) {
            console.error('WebSocket错误:', error);
            statusIndicator.className = 'status-indicator danger';
            connectionStatus.textContent = '错误';
        };
    }
    
    // 添加聊天消息到界面
    function addChatMessage(data) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${data.user_id === userId ? 'sent' : 'received'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // 添加发送者信息
        const senderElement = document.createElement('div');
        senderElement.className = 'message-sender';
        senderElement.textContent = data.user_id === userId ? '你' : data.user_id;
        
        // 添加消息内容
        const contentElement = document.createElement('div');
        contentElement.className = 'message-text';
        contentElement.textContent = data.content;
        
        // 添加时间戳
        const timeElement = document.createElement('div');
        timeElement.className = 'message-time';
        const messageTime = new Date(data.timestamp * 1000);
        timeElement.textContent = messageTime.toLocaleTimeString();
        
        // 组装消息
        messageContent.appendChild(senderElement);
        messageContent.appendChild(contentElement);
        messageContent.appendChild(timeElement);
        messageElement.appendChild(messageContent);
        
        messageList.appendChild(messageElement);
        
        // 滚动到底部
        messageList.scrollTop = messageList.scrollHeight;
    }
    
    // 显示系统消息
    function showSystemMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message system';
        messageElement.textContent = message;
        messageList.appendChild(messageElement);
        messageList.scrollTop = messageList.scrollHeight;
    }
    
    // 显示错误消息
    function showErrorMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message system error';
        messageElement.textContent = `错误: ${message}`;
        messageList.appendChild(messageElement);
        messageList.scrollTop = messageList.scrollHeight;
    }
    
    // 添加私信消息
    function addPrivateMessage(data) {
        const messageElement = document.createElement('div');
        messageElement.className = `message private ${data.user_id === userId ? 'sent' : 'received'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // 添加私信标记
        const privateTag = document.createElement('span');
        privateTag.className = 'private-tag';
        privateTag.textContent = '[私信]';
        
        // 添加发送者信息
        const senderElement = document.createElement('div');
        senderElement.className = 'message-sender';
        senderElement.textContent = data.user_id === userId ? '你' : data.user_id;
        senderElement.prepend(privateTag);
        
        // 添加消息内容
        const contentElement = document.createElement('div');
        contentElement.className = 'message-text';
        contentElement.textContent = data.content;
        
        // 添加时间戳
        const timeElement = document.createElement('div');
        timeElement.className = 'message-time';
        const messageTime = new Date(data.timestamp * 1000);
        timeElement.textContent = messageTime.toLocaleTimeString();
        
        // 组装消息
        messageContent.appendChild(senderElement);
        messageContent.appendChild(contentElement);
        messageContent.appendChild(timeElement);
        messageElement.appendChild(messageContent);
        
        messageList.appendChild(messageElement);
        
        // 滚动到底部
        messageList.scrollTop = messageList.scrollHeight;
    }
    
    // 更新用户列表
    function updateUserList(users) {
        // 清空当前列表
        userList.innerHTML = '';
        
        // 添加用户
        users.forEach(user => {
            const userElement = document.createElement('div');
            userElement.className = 'user-item';
            
            const statusElement = document.createElement('span');
            statusElement.className = 'status';
            
            const nameElement = document.createElement('span');
            nameElement.textContent = user;
            
            userElement.appendChild(statusElement);
            userElement.appendChild(nameElement);
            userList.appendChild(userElement);
        });
    }
    
    // 发送消息
    function sendMessage() {
        const message = messageInput.value.trim();
        
        if (message && socket && socket.readyState === WebSocket.OPEN) {
            const messageData = {
                type: 'chat',
                content: message
            };
            
            socket.send(JSON.stringify(messageData));
            messageInput.value = '';
        }
    }
    
    // 事件监听：发送按钮点击
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }
    
    // 事件监听：回车发送
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
    
    // 初始化WebSocket连接
    connectWebSocket();
    
    // 定期发送心跳
    setInterval(function() {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({type: 'ping'}));
        }
    }, 30000);
    
    // 在页面关闭前，尝试正常关闭WebSocket连接
    window.addEventListener('beforeunload', function() {
        if (socket) {
            socket.close(1000, '用户离开页面');
        }
    });
}); 