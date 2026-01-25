# AI Governance Platform - Prototype

A working prototype of an AI governance platform that provides real-time guardrails for AI agents, with PII detection, audit logging, and compliance monitoring.

## What This Prototype Does

This prototype demonstrates the core value proposition of an AI governance platform:

1. **PII Detection** - Automatically detects and redacts sensitive information (emails, phone numbers, SSNs, credit cards)
2. **Audit Logging** - Every request is logged to BigQuery for compliance and monitoring
3. **Real-time Guardrails** - Check prompts before they reach your AI models
4. **RESTful API** - Easy integration with existing AI applications

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

  1. REGISTER AGENT              2. CHECK PROMPTS              3. VIEW ANALYTICS
  (One-time setup)               (Every request)               (Dashboard)
        │                              │                              │
        ▼                              ▼                              ▼
┌──────────────┐              ┌──────────────┐              ┌──────────────┐
│  POST        │              │  POST        │              │  GET         │
│  /enterprise │              │  /guardrails │              │  /dashboard  │
│  /agents     │              │  /check      │              │              │
└──────┬───────┘              └──────┬───────┘              └──────┬───────┘
       │                             │                             │
       │                             ▼                             │
       │                    ┌──────────────┐                       │
       │                    │ Gemini 3     │                       │
       │                    │ Flash        │                       │
       │                    │ (PII Check)  │                       │
       │                    └──────┬───────┘                       │
       │                           │                               │
       │              ┌────────────┴────────────┐                  │
       │              ▼                         ▼                  │
       │         [PASSED]                  [BLOCKED]               │
       │         Safe prompt               Redacted prompt         │
       │                                   + warning               │
       │                                                           │
       └───────────────────────┬───────────────────────────────────┘
                               ▼
                    ┌──────────────────┐
                    │    BigQuery      │
                    │  ┌────────────┐  │
                    │  │ agents     │  │  ← Agent registry
                    │  │ audit_logs │  │  ← All requests logged
                    │  └────────────┘  │
                    └──────────────────┘
```

Simple flow:
```
User Prompt → Guardrail API → Gemini (PII Detection) → Audit Log (BigQuery) → Safe Response
```

## Quick Start

### Prerequisites

- Python 3.9+
- Google Cloud Platform account
- GCP Project with billing enabled

### 1. Setup GCP Project

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Authenticate
gcloud auth login
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable aiplatform.googleapis.com
gcloud services enable bigquery.googleapis.com

# Set up Application Default Credentials
gcloud auth application-default login
```

### 2. Install Dependencies

```bash
cd ai-governance-prototype

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and set your project ID
# PROJECT_ID=your-actual-project-id
```

### 4. Run the Server

```bash
# Start the FastAPI server
python -m app.main
```

The server will start at `http://localhost:8080`

### 5. Test the API

Open your browser to `http://localhost:8080/docs` to see the interactive API documentation.

Or run the test suite:

```bash
# In a new terminal (keep the server running)
python test_examples.py
```

## API Usage

### Step 1: Register Your AI Agent

Before using the guardrails, register your AI agent to enable tracking and analytics:

```bash
curl -X POST "http://localhost:8080/api/v1/enterprise/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-chatbot-v1",
    "agent_name": "Customer Support Bot",
    "department": "Support",
    "team": "Customer Experience",
    "description": "Handles customer inquiries via chat",
    "owner_email": "support-team@company.com",
    "environment": "production",
    "tags": ["customer-facing", "support"]
  }'
```

Response:
```json
{
  "agent_id": "my-chatbot-v1",
  "agent_name": "Customer Support Bot",
  "department": "Support",
  "team": "Customer Experience",
  "environment": "production",
  "is_active": true,
  "total_requests": 0,
  "pii_incidents": 0
}
```

### Step 2: Check Prompts for PII

Use your registered `agent_id` in all guardrail requests:

```bash
curl -X POST "http://localhost:8080/api/v1/guardrails/check" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "My email is john@example.com",
    "agent_id": "my-chatbot-v1",
    "user_id": "user-123",
    "guardrails": ["pii_detection"]
  }'
```

Response:
```json
{
  "request_id": "uuid-here",
  "agent_id": "my-chatbot-v1",
  "overall_status": "blocked",
  "original_prompt": "My email is john@example.com",
  "safe_prompt": "My email is [REDACTED_EMAIL]",
  "results": [
    {
      "guardrail_type": "pii_detection",
      "status": "blocked",
      "confidence": 1.0,
      "details": {
        "has_pii": true,
        "pii_types": ["email"]
      }
    }
  ]
}
```

### Step 3: Track Agent Performance

**View all registered agents:**
```bash
curl "http://localhost:8080/api/v1/enterprise/agents"
```

**View specific agent with stats:**
```bash
curl "http://localhost:8080/api/v1/enterprise/agents/my-chatbot-v1"
```

Response:
```json
{
  "agent_id": "my-chatbot-v1",
  "agent_name": "Customer Support Bot",
  "department": "Support",
  "total_requests": 150,
  "pii_incidents": 12,
  "is_active": true
}
```

**View enterprise analytics:**
```bash
curl "http://localhost:8080/api/v1/enterprise/analytics?days=30"
```

**View department leaderboard:**
```bash
curl "http://localhost:8080/api/v1/enterprise/leaderboard"
```

### Using the Python SDK

```python
from ai_governance_sdk import GovernanceClient

# Initialize client
client = GovernanceClient(base_url="http://localhost:8080")

# Step 1: Register your agent (one-time)
agent = client.register_agent(
    agent_id="my-chatbot-v1",
    agent_name="Customer Support Bot",
    department="Support",
    team="Customer Experience",
    owner_email="support@company.com",
    environment="production"
)

# Step 2: Check prompts in your application
result = client.check_prompt(
    prompt=user_input,
    agent_id="my-chatbot-v1",
    user_id="user-123"
)

if result.status == "passed":
    # Safe to send to AI model
    response = my_ai_model.generate(result.safe_prompt)
else:
    # PII detected - handle appropriately
    print(f"PII detected: {result.pii_types}")

# Step 3: Check your agent's performance
stats = client.get_agent("my-chatbot-v1")
print(f"Total requests: {stats.total_requests}")
print(f"PII incidents: {stats.pii_incidents}")
```

## How It Works

### 1. PII Detection Flow

```python
User Prompt → FastAPI Endpoint → Gemini Service → PII Analysis → Redaction
                    ↓
              Audit Service → BigQuery Log
```

### 2. Gemini Integration

The prototype uses Google's Gemini model to:
- Analyze prompts for PII
- Identify specific PII types (email, phone, SSN, etc.)
- Generate redacted versions of the text

**Fallback**: If Gemini is unavailable, it falls back to regex-based detection.

### 3. Audit Logging

Every guardrail check is logged to BigQuery with:
- Request ID and timestamp
- Agent and user information
- Guardrail results
- Processing time
- PII detection details

### 4. Cost Tracking

The system tracks:
- Processing time per request
- Model used
- Number of guardrail checks
- (Future) Token usage and cost estimation

### 5. Agent Performance Tracking

Each registered agent is tracked with:

| Metric | Description |
|--------|-------------|
| `total_requests` | Total API calls made by this agent |
| `pii_incidents` | Number of times PII was detected |
| `unique_users` | Distinct users who used this agent |
| `avg_response_time_ms` | Average processing latency |
| `blocked_requests` | Requests that were blocked |

### 6. Dashboard

Access the analytics dashboard at `/dashboard` to view:
- Total requests across all agents
- PII incident rate
- Department-level breakdown
- Top agents by usage
- Registered agents list with status

## Project Structure

```
ai-governance-prototype/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration management
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── guardrails.py       # Guardrail endpoints
│   │   ├── enterprise.py       # Agent registration & analytics
│   │   ├── demo_agent.py       # Demo chat endpoints
│   │   └── auth.py             # Authentication
│   └── services/
│       ├── __init__.py
│       ├── gemini_service.py   # Gemini integration
│       ├── audit_service.py    # BigQuery logging
│       ├── enterprise_service.py # Agent registry & analytics
│       └── demo_agent_service.py # Demo chat service
├── sdk/                        # Python SDK for integration
│   ├── __init__.py
│   └── client.py
├── dashboard/
│   ├── index.html              # Analytics dashboard
│   └── looker_queries.sql      # BigQuery queries for Looker
├── Dockerfile                  # Container for Cloud Run
├── deploy.sh                   # Deployment script
├── requirements.txt
├── .env.example
├── .gitignore
├── test_examples.py            # Test suite
└── README.md
```

## Key Features Demonstrated

✅ **Real Gemini Integration** - Using Vertex AI and Gemini 2.0 Flash
✅ **PII Detection** - Email, phone, SSN, credit card detection
✅ **Audit Logging** - BigQuery with partitioned tables
✅ **REST API** - FastAPI with automatic OpenAPI docs
✅ **Error Handling** - Graceful fallbacks and proper error messages
✅ **Type Safety** - Pydantic models throughout
✅ **Logging** - Structured logging for debugging

## What's NOT in This Prototype

⚠️ **Authentication** - No auth (add JWT/API keys for production)
⚠️ **Rate Limiting** - No rate limiting (add for production)
⚠️ **Advanced Guardrails** - Only PII detection implemented
⚠️ **Dashboard UI** - API only (build React frontend separately)
⚠️ **Multi-tenancy** - Single tenant (add org/team support)
⚠️ **Caching** - No response caching (add Redis for production)

## Cloud Run Deployment

### Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed
- [Docker](https://docs.docker.com/get-docker/) installed
- GCP Project with billing enabled

### Quick Deploy

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Run the deployment script
./deploy.sh
```

### Manual Deployment Steps

1. **Authenticate with GCP**
   ```bash
   gcloud auth login
   gcloud config set project $PROJECT_ID
   ```

2. **Enable required APIs**
   ```bash
   gcloud services enable \
       cloudbuild.googleapis.com \
       run.googleapis.com \
       containerregistry.googleapis.com \
       bigquery.googleapis.com \
       secretmanager.googleapis.com
   ```

3. **Store Gemini API key in Secret Manager**
   ```bash
   echo -n "your-gemini-api-key" | \
       gcloud secrets create gemini-api-key --data-file=-
   ```

4. **Build and deploy**
   ```bash
   # Build image with Cloud Build
   gcloud builds submit --tag gcr.io/$PROJECT_ID/ai-governance-platform

   # Deploy to Cloud Run
   gcloud run deploy ai-governance-platform \
       --image gcr.io/$PROJECT_ID/ai-governance-platform \
       --region us-central1 \
       --platform managed \
       --allow-unauthenticated \
       --memory 1Gi \
       --set-env-vars "PROJECT_ID=$PROJECT_ID,BIGQUERY_DATASET=ai_governance" \
       --set-secrets "GEMINI_API_KEY=gemini-api-key:latest"
   ```

### Deployment Endpoints

After deployment, you'll have:

| Endpoint | Description |
|----------|-------------|
| `/docs` | Interactive API documentation |
| `/health` | Health check endpoint |
| `/api/v1/demo/chat-ui` | Demo chat interface |
| `/dashboard` | Analytics dashboard |

### Local Docker Testing

```bash
# Build locally
docker build -t ai-governance-platform .

# Run with environment variables
docker run -p 8080:8080 \
    -e GEMINI_API_KEY=your-key \
    -e PROJECT_ID=your-project \
    ai-governance-platform
```

## Next Steps for MVP

1. ~~**Add Authentication**~~ ✅ API key auth implemented
2. ~~**Build Dashboard**~~ ✅ HTML dashboard available
3. ~~**Add Output Guardrails**~~ ✅ Sensitive request detection
4. ~~**SDK Development**~~ ✅ Python SDK in /sdk folder
5. ~~**Deploy to Cloud Run**~~ ✅ Deployment script ready
6. **Add More Guardrails** - Toxicity, hallucination, prompt injection
7. **Cost Optimization** - Cache results, batch requests
8. **Add Analytics** - Usage metrics and Looker dashboards

## Estimated Costs

For testing with ~1000 requests/month:

- **Gemini API**: ~$0.10 (using Flash model)
- **BigQuery Storage**: ~$0.02 (1GB)
- **BigQuery Queries**: ~$0.01
- **Total**: Less than $1/month for testing

For production, costs scale with usage. Consider:
- Using Gemini Flash instead of Pro (10x cheaper)
- Implementing caching for repeated prompts
- Batching requests where possible

## Troubleshooting

### "Google Cloud authentication failed"

```bash
# Re-authenticate
gcloud auth application-default login
```

### "Table not found in BigQuery"

The table is created automatically on first run. If you see this error:

```bash
# Check if the dataset exists
bq ls --project_id=$PROJECT_ID

# If not, it will be created on the next API call
```

### "Module not found" errors

```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## Demo Script for Investors

1. **Show the API docs**: `http://localhost:8080/docs`
2. **Run PII test**: Execute test_examples.py and show redaction
3. **Query BigQuery**: Show audit logs in GCP console
4. **Explain architecture**: Control plane concept
5. **Discuss scale**: How this handles millions of requests

## Contributing

This is a prototype. For production use, you'll need to add:
- Proper error handling
- Comprehensive testing
- Security hardening
- Performance optimization
- Monitoring and alerting

## License

MIT License - feel free to use this as a starting point for your project.
