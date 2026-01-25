"""Demo Agent endpoints - A working chat agent for demonstrations"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from app.services.demo_agent_service import get_demo_agent_service
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/demo", tags=["Demo Agent"])


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to the agent")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field(default=None, description="Optional user identifier")


class ChatResponse(BaseModel):
    message: str = Field(..., description="Agent response")
    session_id: str = Field(..., description="Session ID for this conversation")
    request_id: str = Field(..., description="Unique request ID")
    guardrails: Dict[str, Any] = Field(..., description="Guardrail check results")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Chat with the demo Support Agent.

    This endpoint demonstrates the full governance flow:
    1. User input is checked for PII (and redacted if found)
    2. Agent generates a response using Gemini
    3. Response is checked for sensitive data requests
    4. Safe response is returned to user

    Try these examples:
    - Normal: "Hi, I need help with my order"
    - With PII: "My SSN is 123-45-6789, can you help?"
    - The agent should NEVER ask for SSN/credit cards (output guardrail)
    """
    demo_agent = get_demo_agent_service()

    try:
        result = await demo_agent.chat(
            user_message=request.message,
            session_id=request.session_id,
            user_id=request.user_id
        )

        return ChatResponse(
            message=result.message,
            session_id=result.session_id,
            request_id=result.request_id,
            guardrails={
                "input": {
                    "pii_detected": result.input_pii_detected,
                    "was_blocked": result.was_input_blocked
                },
                "output": {
                    "violations": result.output_violations,
                    "was_blocked": result.was_output_blocked
                }
            }
        )

    except Exception as e:
        logger.error(f"Error in demo chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str) -> List[Dict[str, Any]]:
    """Get chat history for a session"""
    demo_agent = get_demo_agent_service()
    return demo_agent.get_session_history(session_id)


@router.delete("/chat/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a chat session"""
    demo_agent = get_demo_agent_service()
    demo_agent.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


# ============ CHAT UI ============

@router.get("/chat-ui", response_class=HTMLResponse)
async def chat_ui():
    """Simple chat UI for demo purposes"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Governance Demo - Support Agent</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: rgba(255,255,255,0.1);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .header h1 {
            color: #fff;
            font-size: 1.5rem;
        }
        .header .badge {
            background: #4ade80;
            color: #000;
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-size: 0.875rem;
            font-weight: 600;
        }
        .container {
            flex: 1;
            display: flex;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
            padding: 1rem;
            gap: 1rem;
        }
        .chat-section {
            flex: 2;
            display: flex;
            flex-direction: column;
            background: rgba(255,255,255,0.05);
            border-radius: 1rem;
            overflow: hidden;
        }
        .chat-header {
            background: rgba(255,255,255,0.1);
            padding: 1rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .agent-avatar {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }
        .agent-info h3 {
            color: #fff;
            font-size: 1rem;
        }
        .agent-info p {
            color: rgba(255,255,255,0.6);
            font-size: 0.875rem;
        }
        .chat-messages {
            flex: 1;
            padding: 1rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .message {
            display: flex;
            gap: 0.75rem;
            max-width: 80%;
        }
        .message.user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }
        .message-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            flex-shrink: 0;
        }
        .message.assistant .message-avatar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .message.user .message-avatar {
            background: #4ade80;
            color: #000;
        }
        .message-content {
            padding: 0.75rem 1rem;
            border-radius: 1rem;
            color: #fff;
        }
        .message.assistant .message-content {
            background: rgba(255,255,255,0.1);
            border-bottom-left-radius: 0.25rem;
        }
        .message.user .message-content {
            background: #667eea;
            border-bottom-right-radius: 0.25rem;
        }
        .message-meta {
            margin-top: 0.5rem;
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        .tag {
            font-size: 0.75rem;
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
        }
        .tag.pii {
            background: #fbbf24;
            color: #000;
        }
        .tag.blocked {
            background: #ef4444;
            color: #fff;
        }
        .tag.safe {
            background: #4ade80;
            color: #000;
        }
        .chat-input {
            padding: 1rem;
            background: rgba(255,255,255,0.1);
            display: flex;
            gap: 0.75rem;
        }
        .chat-input input {
            flex: 1;
            padding: 0.75rem 1rem;
            border: none;
            border-radius: 0.5rem;
            background: rgba(255,255,255,0.1);
            color: #fff;
            font-size: 1rem;
        }
        .chat-input input::placeholder {
            color: rgba(255,255,255,0.5);
        }
        .chat-input input:focus {
            outline: 2px solid #667eea;
        }
        .chat-input button {
            padding: 0.75rem 1.5rem;
            background: #667eea;
            color: #fff;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 600;
            transition: background 0.2s;
        }
        .chat-input button:hover {
            background: #5a67d8;
        }
        .chat-input button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .info-section {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .info-card {
            background: rgba(255,255,255,0.05);
            border-radius: 1rem;
            padding: 1rem;
        }
        .info-card h3 {
            color: #fff;
            margin-bottom: 0.75rem;
            font-size: 1rem;
        }
        .info-card ul {
            list-style: none;
            color: rgba(255,255,255,0.7);
            font-size: 0.875rem;
        }
        .info-card li {
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .info-card li:last-child {
            border-bottom: none;
        }
        .info-card code {
            background: rgba(255,255,255,0.1);
            padding: 0.125rem 0.375rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
        }
        .guardrail-status {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        .guardrail-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem;
            background: rgba(255,255,255,0.05);
            border-radius: 0.5rem;
        }
        .guardrail-item .status {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
        .guardrail-item .status.active {
            background: #4ade80;
            box-shadow: 0 0 8px #4ade80;
        }
        .typing {
            display: flex;
            gap: 0.25rem;
            padding: 0.75rem 1rem;
        }
        .typing span {
            width: 8px;
            height: 8px;
            background: rgba(255,255,255,0.5);
            border-radius: 50%;
            animation: typing 1.4s infinite;
        }
        .typing span:nth-child(2) { animation-delay: 0.2s; }
        .typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-4px); }
        }
        .session-info {
            font-size: 0.75rem;
            color: rgba(255,255,255,0.5);
            padding: 0.5rem 1rem;
            background: rgba(0,0,0,0.2);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ AI Governance Platform - Demo</h1>
        <span class="badge">Live Demo</span>
    </div>

    <div class="container">
        <div class="chat-section">
            <div class="chat-header">
                <div class="agent-avatar">🤖</div>
                <div class="agent-info">
                    <h3>Support Agent</h3>
                    <p>support-agent-001 • Protected by Governance</p>
                </div>
            </div>

            <div class="chat-messages" id="messages">
                <div class="message assistant">
                    <div class="message-avatar">🤖</div>
                    <div>
                        <div class="message-content">
                            Hello! I'm the Customer Support Agent. How can I help you today?
                        </div>
                        <div class="message-meta">
                            <span class="tag safe">✓ Guardrails Active</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="session-info" id="session-info">Session: Not started</div>

            <div class="chat-input">
                <input type="text" id="user-input" placeholder="Type your message..." autocomplete="off">
                <button id="send-btn" onclick="sendMessage()">Send</button>
            </div>
        </div>

        <div class="info-section">
            <div class="info-card">
                <h3>🛡️ Active Guardrails</h3>
                <div class="guardrail-status">
                    <div class="guardrail-item">
                        <span>PII Detection (Input)</span>
                        <span class="status active"></span>
                    </div>
                    <div class="guardrail-item">
                        <span>Sensitive Request (Output)</span>
                        <span class="status active"></span>
                    </div>
                </div>
            </div>

            <div class="info-card">
                <h3>🧪 Try These Examples</h3>
                <ul>
                    <li><strong>Normal:</strong> "Hi, I need help with order #12345"</li>
                    <li><strong>With PII:</strong> "My SSN is 123-45-6789"</li>
                    <li><strong>With Email:</strong> "Contact me at john@email.com"</li>
                </ul>
            </div>

            <div class="info-card">
                <h3>📊 How It Works</h3>
                <ul>
                    <li><strong>1.</strong> Your message → PII check</li>
                    <li><strong>2.</strong> Safe prompt → Gemini AI</li>
                    <li><strong>3.</strong> Response → Sensitive check</li>
                    <li><strong>4.</strong> Safe response → You</li>
                </ul>
            </div>

            <div class="info-card">
                <h3>📝 Last Request Details</h3>
                <div id="last-request">
                    <p style="color: rgba(255,255,255,0.5)">Send a message to see details</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let sessionId = null;

        document.getElementById('user-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        async function sendMessage() {
            const input = document.getElementById('user-input');
            const message = input.value.trim();
            if (!message) return;

            const sendBtn = document.getElementById('send-btn');
            sendBtn.disabled = true;
            input.value = '';

            // Add user message
            addMessage('user', message);

            // Show typing indicator
            const typingId = showTyping();

            try {
                const response = await fetch('/api/v1/demo/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                        session_id: sessionId
                    })
                });

                const data = await response.json();
                sessionId = data.session_id;

                // Update session info
                document.getElementById('session-info').textContent = `Session: ${sessionId.substring(0, 8)}...`;

                // Remove typing indicator
                removeTyping(typingId);

                // Add agent response with guardrail info
                addMessage('assistant', data.message, data.guardrails);

                // Update last request details
                updateLastRequest(data);

            } catch (error) {
                removeTyping(typingId);
                addMessage('assistant', 'Sorry, something went wrong. Please try again.');
                console.error(error);
            }

            sendBtn.disabled = false;
            input.focus();
        }

        function addMessage(role, content, guardrails = null) {
            const messages = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = `message ${role}`;

            let metaTags = '';
            if (guardrails) {
                if (guardrails.input.pii_detected.length > 0) {
                    metaTags += `<span class="tag pii">⚠️ PII: ${guardrails.input.pii_detected.join(', ')}</span>`;
                }
                if (guardrails.output.was_blocked) {
                    metaTags += `<span class="tag blocked">🚫 Blocked: ${guardrails.output.violations.join(', ')}</span>`;
                }
                if (!guardrails.output.was_blocked && guardrails.input.pii_detected.length === 0) {
                    metaTags += `<span class="tag safe">✓ Clean</span>`;
                }
            }

            div.innerHTML = `
                <div class="message-avatar">${role === 'user' ? '👤' : '🤖'}</div>
                <div>
                    <div class="message-content">${escapeHtml(content)}</div>
                    ${metaTags ? `<div class="message-meta">${metaTags}</div>` : ''}
                </div>
            `;

            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        function showTyping() {
            const messages = document.getElementById('messages');
            const id = 'typing-' + Date.now();
            const div = document.createElement('div');
            div.id = id;
            div.className = 'message assistant';
            div.innerHTML = `
                <div class="message-avatar">🤖</div>
                <div class="typing">
                    <span></span><span></span><span></span>
                </div>
            `;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
            return id;
        }

        function removeTyping(id) {
            const el = document.getElementById(id);
            if (el) el.remove();
        }

        function updateLastRequest(data) {
            document.getElementById('last-request').innerHTML = `
                <p><strong>Request ID:</strong> <code>${data.request_id.substring(0, 8)}...</code></p>
                <p><strong>Input PII:</strong> ${data.guardrails.input.pii_detected.length > 0 ? data.guardrails.input.pii_detected.join(', ') : 'None'}</p>
                <p><strong>Output Blocked:</strong> ${data.guardrails.output.was_blocked ? 'Yes' : 'No'}</p>
            `;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>
"""