# AI Governance Platform - 5 Minute Demo Script

## Setup Before Demo
- Open these tabs in browser:
  1. Dashboard: https://ai-governance-platform-902023244402.us-central1.run.app/dashboard
  2. Demo Chat: https://ai-governance-platform-902023244402.us-central1.run.app/api/v1/demo/chat-ui
  3. API Docs: https://ai-governance-platform-902023244402.us-central1.run.app/docs

---

## Demo Script (5 minutes)

### Intro (30 seconds)
> "Let me show you a live demo of our AI Governance Platform. This is running on Google Cloud right now, processing real requests with Gemini 3."

### Part 1: The Problem (30 seconds)
> "Imagine you have a customer support chatbot. A customer accidentally shares their SSN or credit card. Without guardrails, that sensitive data goes straight to your AI model - a compliance nightmare."

**[Show Dashboard]**
> "This dashboard shows our platform monitoring 6 different AI agents. You can see we've already caught 20 PII incidents across 29 requests."

### Part 2: Live PII Detection (1.5 minutes)

**[Switch to Demo Chat]**

> "Let me show you how we protect against this. This is a customer support bot powered by Gemini."

**Type:** "Hi, I need help with my order"

> "Normal conversation works fine."

**Type:** "My email is john@example.com and my SSN is 123-45-6789"

> "Watch what happens when sensitive data is shared..."

**[Point to the response]**
> "The AI never asked for this information, and our platform detected it immediately. Look at the guardrail notification - it flagged email and SSN."

> "But here's the key part - we also have OUTPUT guardrails."

**Type:** "Can you look up my account with my social security number?"

> "Even though the user is offering their SSN, our platform blocked the AI from accepting it. The bot politely declines and asks for safe identifiers instead."

### Part 3: Real-time Dashboard (1 minute)

**[Switch to Dashboard]**

> "Every single interaction is logged in real-time to BigQuery."

**[Point to metrics]**
- "Total requests across all agents"
- "PII detection rate - this tells you which teams need training"
- "Department breakdown - see which teams have the highest risk"

**[Point to agent table]**
> "Every AI agent is registered and tracked. You can see which agents have compliance issues."

**[Click Refresh]**
> "This updates in real-time. The requests we just made should appear now."

### Part 4: API Integration (1 minute)

**[Switch to API Docs]**

> "Integration takes 5 minutes. Let me show you the API."

**[Click on POST /api/v1/guardrails/check]**

> "You send us the prompt, we return a safe version with PII redacted. Three lines of code in your application."

**[Show the request schema]**
```json
{
  "prompt": "My email is john@example.com",
  "agent_id": "your-bot-id",
  "guardrails": ["pii_detection"]
}
```

> "We return the original prompt, the safe prompt with redactions, and exactly what was detected. All logged for compliance."

### Part 5: Enterprise Value (30 seconds)

> "What does this mean for enterprises?"

> "1. **Compliance** - Automatic audit trail for SOC2, HIPAA, GDPR
> 2. **Security** - PII never reaches your AI models
> 3. **Visibility** - Know exactly what your AI agents are doing
> 4. **Control** - One platform for all your AI agents"

### Close (30 seconds)

> "We're currently onboarding pilot customers. The platform is live, it's fast - under 500ms latency - and it scales automatically on Google Cloud."

> "Any questions about what you just saw?"

---

## Backup Demos (If Asked)

### Show API Call Live
```bash
curl -X POST "https://ai-governance-platform-902023244402.us-central1.run.app/api/v1/guardrails/check" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Contact me at ceo@company.com or 415-555-0100",
    "agent_id": "demo-agent",
    "guardrails": ["pii_detection"]
  }'
```

### Show Agent Registration
```bash
curl -X POST "https://ai-governance-platform-902023244402.us-central1.run.app/api/v1/enterprise/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "new-sales-bot",
    "agent_name": "Sales Assistant",
    "department": "Sales",
    "owner_email": "sales@company.com",
    "environment": "production"
  }'
```

### Show Analytics Endpoint
```bash
curl "https://ai-governance-platform-902023244402.us-central1.run.app/api/v1/enterprise/analytics?days=30"
```

---

## Common Questions & Answers

**Q: What AI models do you support?**
> "Any model. We sit in front of your AI - whether it's GPT-4, Claude, Gemini, or open source. We check the prompt before it reaches your model."

**Q: What's the latency?**
> "Average under 500ms. We use Gemini Flash which is optimized for speed."

**Q: Can we self-host?**
> "Currently cloud-only on GCP. Self-hosted option is on the roadmap for enterprise customers."

**Q: What about false positives?**
> "Gemini's contextual understanding is excellent. It knows 'john@example.com' in a sentence about email formats isn't the same as someone sharing their actual email."

**Q: How is this different from regex?**
> "Regex catches patterns. We catch intent. 'My social is one two three...' - regex misses that. Gemini catches it."

**Q: What other guardrails are you adding?**
> "Toxicity detection, prompt injection prevention, and hallucination detection are next on the roadmap."

---

## Demo Recovery Tips

### If API is slow:
> "Cloud Run scales to zero when idle. First request wakes it up. In production, we keep instances warm."

### If something errors:
> "Let me show you the fallback - we have regex-based detection as a backup. The system never fails open."

### If dashboard is empty:
> "Let me generate some test data real quick..."
**[Make a few requests in Demo Chat]**
**[Refresh Dashboard]**