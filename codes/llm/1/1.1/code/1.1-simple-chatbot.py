# ai_assistant.py
# Python 3.9+ 版本
# 依赖: pip install openai python-dotenv streamlit streamlit-chat

import os
import json
import time
from datetime import datetime
import streamlit as st
import openai
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置页面配置
st.set_page_config(
    page_title="Python AI助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 应用标题和CSS样式
st.markdown("""
<style>
    .main-header {text-align: center; font-size: 2.5rem; margin-bottom: 1rem;}
    .subheader {text-align: center; font-size: 1.2rem; margin-bottom: 2rem; color: #888;}
    .chat-message {padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; line-height: 1.5;}
    .user-message {background-color: #e6f7ff; border-left: 5px solid #1890ff;}
    .assistant-message {background-color: #f6ffed; border-left: 5px solid #52c41a;}
    .error-message {background-color: #fff2f0; border-left: 5px solid #ff4d4f;}
    .info-box {background-color: #f0f2f5; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;}
    .footer {text-align: center; margin-top: 2rem; color: #888; font-size: 0.8rem;}
    .stButton>button {width: 100%;}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">Python AI助手</h1>', unsafe_allow_html=True)
st.markdown('<p class="subheader">基于大型语言模型的智能对话系统</p>', unsafe_allow_html=True)

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")

if "settings" not in st.session_state:
    st.session_state.settings = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": True
    }

# 获取API密钥
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    api_key = st.sidebar.text_input("OpenAI API密钥", type="password")
    if not api_key:
        st.sidebar.error("请输入有效的OpenAI API密钥")
        st.sidebar.info("如何获取API密钥：\n1. 访问 [OpenAI网站](https://platform.openai.com/)\n2. 注册或登录账号\n3. 在个人设置中找到'API Keys'选项\n4. 创建新的密钥")
        st.stop()

# 设置OpenAI客户端
openai.api_key = api_key

# 侧边栏 - 设置和会话管理
with st.sidebar:
    st.header("🛠️ 设置")
    
    # 模型选择
    model_options = ["gpt-3.5-turbo", "gpt-4", "gpt-3.5-turbo-16k"]
    selected_model = st.selectbox("选择模型", model_options, index=model_options.index(st.session_state.settings["model"]))
    st.session_state.settings["model"] = selected_model
    
    # 参数调整
    st.session_state.settings["temperature"] = st.slider("温度 (创造性)", 0.0, 1.0, st.session_state.settings["temperature"], 0.1,
                                                       help="较高的值使输出更加随机和创造性，较低的值使输出更加确定和集中")
    st.session_state.settings["max_tokens"] = st.slider("最大回复长度", 100, 4000, st.session_state.settings["max_tokens"], 100,
                                                     help="控制AI回复的最大长度")
    
    st.session_state.settings["stream"] = st.checkbox("流式输出", st.session_state.settings["stream"],
                                                  help="启用后可以看到AI逐字回复")
    
    st.divider()
    st.header("💾 会话管理")
    
    # 新建会话
    if st.button("➕ 新建会话"):
        st.session_state.messages = []
        st.session_state.current_conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.success("已创建新会话")
        st.experimental_rerun()
    
    # 保存当前会话
    if st.button("💾 保存当前会话") and st.session_state.messages:
        try:
            conversation_data = {
                "id": st.session_state.current_conversation_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "messages": st.session_state.messages
            }
            
            # 添加到历史记录
            st.session_state.conversation_history.append(conversation_data)
            
            # 保存到文件
            os.makedirs("conversations", exist_ok=True)
            with open(f"conversations/{st.session_state.current_conversation_id}.json", "w") as f:
                json.dump(conversation_data, f, indent=2)
            
            st.success("会话已保存")
        except Exception as e:
            st.error(f"保存失败: {str(e)}")
    
    # 显示历史会话
    if st.session_state.conversation_history:
        st.divider()
        st.subheader("历史会话")
        for conv in reversed(st.session_state.conversation_history):
            if st.button(f"{conv['timestamp']} ({len(conv['messages'])}条消息)", key=f"history_{conv['id']}"):
                st.session_state.messages = conv['messages']
                st.session_state.current_conversation_id = conv['id']
                st.experimental_rerun()

# 主界面 - 聊天区
chat_container = st.container()

with chat_container:
    # 显示聊天历史
    for idx, message in enumerate(st.session_state.messages):
        role = message["role"]
        content = message["content"]
        
        if role == "user":
            st.markdown(f'<div class="chat-message user-message"><strong>你:</strong> {content}</div>', unsafe_allow_html=True)
        elif role == "assistant":
            st.markdown(f'<div class="chat-message assistant-message"><strong>AI助手:</strong> {content}</div>', unsafe_allow_html=True)
        elif role == "system":
            continue
        elif role == "error":
            st.markdown(f'<div class="chat-message error-message"><strong>错误:</strong> {content}</div>', unsafe_allow_html=True)

# 输入区
with st.container():
    col1, col2 = st.columns([5, 1])
    
    with col1:
        user_input = st.text_area("在这里输入你的问题...", height=100, key="user_input")
    
    with col2:
        st.write("")
        st.write("")
        send_button = st.button("发送", use_container_width=True)
    
    # 辅助功能区
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("👋 自我介绍", use_container_width=True):
            user_input = "请介绍一下你自己"
            send_button = True
    
    with col2:
        if st.button("📚 Python学习路径", use_container_width=True):
            user_input = "给我推荐一个Python从入门到精通的学习路径"
            send_button = True
    
    with col3:
        if st.button("🧠 AI发展趋势", use_container_width=True):
            user_input = "请分析一下2025年AI领域的主要发展趋势"
            send_button = True

# 处理用户输入
if send_button and user_input:
    # 添加用户消息到会话
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 创建完整的消息历史
    messages_for_api = []
    
    # 添加系统消息，如果没有的话
    if not any(msg["role"] == "system" for msg in st.session_state.messages):
        system_message = {
            "role": "system",
            "content": "你是一个专业的AI助手，由Python打造。你具有广泛的知识，尤其擅长Python编程、数据科学和人工智能相关话题。"
                       "请提供准确、有帮助的回答，并在适当的情况下提供代码示例。"
                       "保持友好和专业的语气，避免生成有害或不适当的内容。"
        }
        messages_for_api.append(system_message)
    
    # 添加所有聊天历史
    for msg in st.session_state.messages:
        if msg["role"] != "error":  # 跳过错误消息
            messages_for_api.append({"role": msg["role"], "content": msg["content"]})
    
    # 显示思考中的状态
    with st.status("AI助手正在思考...") as status:
        try:
            if st.session_state.settings["stream"]:
                # 流式响应
                response_container = st.empty()
                full_response = ""
                
                # 调用API
                response = openai.ChatCompletion.create(
                    model=st.session_state.settings["model"],
                    messages=messages_for_api,
                    temperature=st.session_state.settings["temperature"],
                    max_tokens=st.session_state.settings["max_tokens"],
                    stream=True
                )
                
                # 逐步处理流式响应
                for chunk in response:
                    if hasattr(chunk.choices[0], "delta") and hasattr(chunk.choices[0].delta, "content"):
                        content_chunk = chunk.choices[0].delta.get("content", "")
                        full_response += content_chunk
                        response_container.markdown(f"<div class='chat-message assistant-message'><strong>AI助手:</strong> {full_response}▌</div>", unsafe_allow_html=True)
                
                # 添加最终响应到会话
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                status.update(label="回答完成！", state="complete")
                
            else:
                # 非流式响应
                response = openai.ChatCompletion.create(
                    model=st.session_state.settings["model"],
                    messages=messages_for_api,
                    temperature=st.session_state.settings["temperature"],
                    max_tokens=st.session_state.settings["max_tokens"],
                    stream=False
                )
                
                # 提取响应内容
                assistant_response = response.choices[0].message.content
                
                # 添加到会话
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                status.update(label="回答完成！", state="complete")
        
        except Exception as e:
            # 处理错误
            error_message = f"发生错误: {str(e)}"
            st.session_state.messages.append({"role": "error", "content": error_message})
            status.update(label="出错了！", state="error")
    
    # 清空输入框并刷新页面
    st.experimental_rerun()

# 页脚
st.markdown('<div class="footer">通过Python和OpenAI API构建的AI助手聊天机器人 | 基于大型语言模型</div>', unsafe_allow_html=True)

# 添加使用说明
with st.expander("📋 使用说明"):
    st.markdown("""
    ### 如何使用这个AI助手
    
    1. **输入问题**：在底部文本框中输入您的问题或指令
    2. **发送消息**：点击"发送"按钮或使用快捷按钮提问预设问题
    3. **查看回答**：AI助手将生成回答并显示在聊天区
    4. **调整设置**：在侧边栏中可以更改模型和参数设置
    5. **会话管理**：可以保存当前会话，创建新会话，或加载历史会话
    
    ### 功能特点
    
    - **流式输出**：实时看到AI的回答过程
    - **会话保存**：保存重要的对话内容以便日后查看
    - **自定义设置**：根据需要调整AI的创造性和回复长度
    - **多种模型**：选择不同的AI模型以满足不同需求
    
    ### 最佳实践
    
    - 提出明确、具体的问题会得到更准确的回答
    - 对于复杂问题，可以分步骤提问
    - 调低温度参数可以获得更确定、准确的回答
    - 调高温度参数可以获得更有创意的回答
    """)

# 创建一个帮助文档
with st.expander("❓ 常见问题 (FAQ)"):
    st.markdown("""
    ### 常见问题解答
    
    **问：这个AI助手能回答什么类型的问题？**  
    答：本助手擅长Python编程、数据科学、AI等技术话题，但也能回答广泛的知识性问题。
    
    **问：我的对话内容会被保存在哪里？**  
    答：对话内容会暂时保存在您的浏览器会话中，如果您手动保存会话，则会存储在本地的"conversations"文件夹中。
    
    **问：如何获取OpenAI API密钥？**  
    答：您需要在OpenAI官网(https://platform.openai.com/)注册账号，然后在API Keys部分创建一个新的密钥。
    
    **问：不同的模型有什么区别？**  
    答：
    - gpt-3.5-turbo：平衡了性能和成本，适合大多数对话场景
    - gpt-4：更强大的理解能力和生成质量，但成本更高
    - gpt-3.5-turbo-16k：与gpt-3.5-turbo类似，但支持更长的上下文窗口
    
    **问：API调用失败怎么办？**  
    答：
    1. 检查您的API密钥是否正确
    2. 确认您的OpenAI账户余额充足
    3. 尝试更换模型或减少最大回复长度
    4. 您可能达到了API调用速率限制，稍等片刻再试
    """)


# pip install openai python-dotenv streamlit streamlit-chat
# 在环境变量中设置 OPENAI_API_KEY=你的密钥
# 在终端运行：streamlit run simple-chatbot.py