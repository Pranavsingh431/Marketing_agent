# Marketing Agent - Production-Grade Multi-Agent Marketing System

A comprehensive marketing automation system built with LangChain, LangGraph, and LangSmith that creates, launches, and optimizes advertising campaigns across Meta (Facebook/Instagram) and Google Ads platforms.

## 🚀 Features

### Core Capabilities
- **AI-Powered Content Generation**: Creates compelling ad copy and headlines using Claude 3 Sonnet
- **Visual Asset Creation**: Generates platform-optimized images using DALL-E 3 and Stability AI
- **Multi-Platform Campaign Launch**: Deploys campaigns to Meta and Google Ads automatically
- **Real-Time Performance Tracking**: Monitors CTR, CPC, ROAS, and other KPIs hourly
- **Intelligent Optimization**: Auto-optimizes campaigns based on performance thresholds
- **Human-in-the-Loop Approvals**: Optional approval workflow for budget and creative decisions
- **Production-Ready Deployment**: Containerized with Docker, deployable to GCP Cloud Run

### Technical Stack
- **LangChain**: AI agent orchestration and LLM integration
- **LangGraph**: Multi-agent workflow management with state persistence
- **LangSmith**: Execution tracing and debugging
- **Supabase**: PostgreSQL database with real-time capabilities
- **FastAPI**: High-performance API framework
- **OpenRouter**: Access to multiple LLM providers
- **Meta Business SDK**: Facebook and Instagram Ads integration
- **Google Ads API**: Google Ads campaign management

## 📋 Prerequisites

Before you begin, ensure you have:

### Required API Keys
1. **OpenRouter API Key**: Get from [OpenRouter.ai](https://openrouter.ai/)
2. **Supabase Project**: URL and anon key
3. **Meta Developer Account**: App ID, App Secret, Access Token, Ad Account ID
4. **Google Ads Developer Token**: Client ID, Client Secret, Refresh Token, Customer ID
5. **LangSmith API Key** (optional): For execution tracing
6. **Stability AI API Key** (optional): For advanced image generation

### Platform Setup
- **Meta Business Manager**: Configure ad account and obtain necessary permissions
- **Google Ads Account**: Set up developer access and obtain API credentials
- **Supabase Project**: Create database and enable required extensions

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd marketing-agent
```

### 2. Environment Configuration
```bash
# Copy environment template
cp env.template .env

# Edit .env with your API keys and configuration
nano .env
```

### 3. Database Setup
```bash
# Run the database schema in your Supabase SQL editor
cat database/schema.sql
# Execute the SQL in Supabase dashboard
```

### 4. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### 5. Docker Deployment
```bash
# Build Docker image
docker build -t marketing-agent .

# Run container
docker run -p 8080:8080 --env-file .env marketing-agent
```

### 6. GCP Cloud Run Deployment
```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/marketing-agent

# Deploy to Cloud Run
gcloud run deploy marketing-agent \
  --image gcr.io/YOUR_PROJECT_ID/marketing-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="$(cat .env | tr '\n' ',')"
```

## 🎯 Usage Examples

### Create a Campaign
```bash
curl -X POST "http://localhost:8080/campaigns/create" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Summer Sale Campaign",
    "product_name": "Wireless Headphones",
    "objective": "conversions",
    "platform": "both",
    "budget_daily": 100.00,
    "target_audience": {
      "age_range": "25-45",
      "interests": ["technology", "music", "fitness"],
      "countries": ["US", "CA", "UK"]
    },
    "landing_url": "https://yourstore.com/headphones"
  }'
```

### Monitor Performance
```bash
curl "http://localhost:8080/campaigns/{campaign_id}/performance?hours=24"
```

### Trigger Optimization
```bash
curl -X POST "http://localhost:8080/campaigns/{campaign_id}/optimize" \
  -H "Content-Type: application/json" \
  -d '{"force_optimization": false}'
```

### View Dashboard
```bash
curl "http://localhost:8080/dashboard"
```

## 🏗️ Architecture

### Agent System
```
┌─────────────────────┐
│   Orchestrator      │
│   (LangGraph)       │
└─────────┬───────────┘
          │
     ┌────┴────┐
     │         │
┌────▼──┐ ┌───▼──┐ ┌────▼──┐ ┌──────▼──┐
│Content│ │Visual│ │Campaign│ │Performance│
│Gen    │ │Creator│ │Launcher│ │Tracker   │
└───────┘ └──────┘ └───────┘ └─────────┘
```

### Data Flow
1. **Campaign Creation**: User submits campaign requirements
2. **Content Generation**: AI creates optimized ad copy using platform-specific prompts
3. **Visual Creation**: AI generates platform-optimized images
4. **Approval Process**: Optional human review for budget and creative approval
5. **Campaign Launch**: Automated deployment to Meta/Google Ads platforms
6. **Performance Monitoring**: Hourly tracking of key metrics
7. **Optimization Loop**: Automatic improvements based on performance thresholds

### Database Schema
- **campaigns**: Campaign metadata and configuration
- **ad_creatives**: Generated content and visual assets
- **performance_logs**: Hourly performance metrics
- **approvals**: Human approval workflow tracking
- **agent_logs**: Execution tracing and debugging
- **optimizations**: Optimization history and results

## 📊 Performance Thresholds

Default optimization triggers:
- **CTR < 2%**: Low click-through rate
- **CPC > $2.00**: High cost per click
- **ROAS < 3.0**: Low return on ad spend
- **Daily Spend > $1000**: Budget protection

Configure thresholds in `.env`:
```env
CTR_THRESHOLD=0.02
CPC_THRESHOLD=2.00
ROAS_THRESHOLD=3.00
DAILY_BUDGET_LIMIT=1000
```

## 🔧 Configuration

### Key Environment Variables
```env
# Core Configuration
OPENROUTER_API_KEY=your_openrouter_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Platform APIs
META_ACCESS_TOKEN=your_meta_token
META_AD_ACCOUNT_ID=your_ad_account_id
GOOGLE_ADS_CUSTOMER_ID=your_customer_id

# Features
HUMAN_APPROVAL_REQUIRED=true
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## 📈 Monitoring & Debugging

### LangSmith Integration
Enable execution tracing by setting:
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=marketing-agent
```

### Health Checks
- **API Health**: `GET /health`
- **System Status**: `GET /`
- **Dashboard**: `GET /dashboard`

### Logging
Structured JSON logging with:
- Agent execution traces
- Performance metrics
- Error tracking
- Optimization events

## 🔒 Security Best Practices

1. **Environment Variables**: Never commit API keys to version control
2. **Database Security**: Enable Row Level Security (RLS) in Supabase
3. **API Rate Limiting**: Implement rate limiting for production deployments
4. **CORS Configuration**: Restrict allowed origins for production
5. **Secret Management**: Use Google Secret Manager or similar for production

## 🚀 Deployment

### Cloud Scheduler Setup
Schedule hourly performance tracking:
```bash
gcloud scheduler jobs create http marketing-agent-tracker \
  --schedule="0 * * * *" \
  --uri="https://your-cloud-run-url/campaigns/track" \
  --http-method=POST
```

### Scaling Configuration
```yaml
# cloud-run.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: marketing-agent
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "10"
    spec:
      containerConcurrency: 100
      containers:
      - image: gcr.io/PROJECT_ID/marketing-agent
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
```

## 🧪 Testing

### Run Tests
```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/integration/

# Load testing
locust -f tests/load_test.py
```

### API Testing
```bash
# Test campaign creation
python tests/test_campaign_creation.py

# Test performance tracking
python tests/test_performance_tracking.py
```

## 📚 API Documentation

Once running, access interactive API documentation:
- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: See `/docs` directory for detailed guides
- **Issues**: Report bugs and request features via GitHub Issues
- **Email**: For urgent production issues

## 🔄 Roadmap

### Phase 1 (Current)
- ✅ Core agent system
- ✅ Meta and Google Ads integration
- ✅ Performance tracking
- ✅ Basic optimization

### Phase 2 (Planned)
- 🔄 Advanced targeting optimization
- 🔄 A/B testing framework
- 🔄 Multi-language support
- 🔄 Advanced analytics dashboard

### Phase 3 (Future)
- 📋 Additional ad platforms (LinkedIn, Twitter)
- 📋 Video ad generation
- 📋 Advanced ML optimization models
- 📋 Customer journey tracking

---

**Built with ❤️ for production-grade marketing automation** 