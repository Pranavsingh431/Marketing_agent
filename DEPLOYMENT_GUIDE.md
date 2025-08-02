# Marketing Agent - Production Deployment Guide

## 🚀 Quick Deployment (5 Minutes)

### Prerequisites
- Google Cloud Platform account with billing enabled
- `gcloud` CLI installed and authenticated
- Supabase account (free tier available)

### Step 1: Database Setup (2 minutes)
```bash
# 1. Go to supabase.com and create a new project
# 2. In the SQL editor, run the entire contents of database/schema.sql
# 3. Get your project URL and anon key from Settings > API
```

### Step 2: Environment Configuration (1 minute)
```bash
# Copy the template and fill in your credentials
cp env.template .env

# Required minimum configuration:
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
OPENROUTER_API_KEY=your_openrouter_key
```

### Step 3: Deploy to GCP (2 minutes)
```bash
# Make the deploy script executable
chmod +x deploy.sh

# Deploy to production
./deploy.sh production your-gcp-project-id
```

That's it! Your marketing agent is now running in production.

---

## 🔧 Detailed Setup Instructions

### Google Cloud Platform Setup

#### 1. Create GCP Project
```bash
# Create new project
gcloud projects create your-project-id --name="Marketing Agent"

# Set as default project
gcloud config set project your-project-id

# Enable billing (required for Cloud Run)
# Go to: https://console.cloud.google.com/billing
```

#### 2. Enable Required APIs
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable scheduler.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable container.googleapis.com
```

#### 3. Set Up IAM
```bash
# Create service account
gcloud iam service-accounts create marketing-agent-sa \
    --display-name="Marketing Agent Service Account"

# Grant necessary roles
gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:marketing-agent-sa@your-project-id.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:marketing-agent-sa@your-project-id.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"
```

### Database Configuration

#### Supabase Setup
1. **Create Project**
   - Go to [supabase.com](https://supabase.com)
   - Click "New Project"
   - Choose organization and enter project details

2. **Run Database Schema**
   - Go to SQL Editor in Supabase dashboard
   - Copy and paste the entire contents of `database/schema.sql`
   - Click "Run" to execute

3. **Get Credentials**
   - Go to Settings > API
   - Copy "Project URL" and "anon public" key
   - Add to your `.env` file

#### Database Schema Overview
```sql
-- Core tables created:
campaigns          -- Campaign metadata and configuration
ad_creatives       -- Generated content and visuals
performance_logs   -- Metrics and KPI tracking
approvals         -- Human approval workflow
agent_logs        -- Agent execution tracking
optimizations     -- AI optimization history
```

### Environment Variables

#### Required Configuration
```bash
# Core Services (Required)
OPENROUTER_API_KEY=your_openrouter_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# Optional Services
LANGCHAIN_API_KEY=your_langsmith_key    # For execution tracing
STABILITY_API_KEY=your_stability_key    # For image generation
```

#### Platform API Keys (Optional)
```bash
# Meta/Facebook Ads
META_ACCESS_TOKEN=your_meta_token
META_APP_ID=your_meta_app_id
META_APP_SECRET=your_meta_app_secret
META_AD_ACCOUNT_ID=your_ad_account_id

# Google Ads
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token
GOOGLE_ADS_CLIENT_ID=your_client_id
GOOGLE_ADS_CLIENT_SECRET=your_client_secret
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token
GOOGLE_ADS_CUSTOMER_ID=your_customer_id
```

### Platform API Setup

#### Meta/Facebook Ads Setup
1. **Create Facebook App**
   - Go to [developers.facebook.com](https://developers.facebook.com)
   - Create new app for "Business"
   - Add "Marketing API" product

2. **Get Credentials**
   - App ID and App Secret from app dashboard
   - Generate long-lived access token
   - Get Ad Account ID from Business Manager

3. **Permissions Required**
   - `ads_management`
   - `ads_read`
   - `business_management`

#### Google Ads Setup
1. **Apply for API Access**
   - Go to [developers.google.com/google-ads](https://developers.google.com/google-ads)
   - Apply for Google Ads API access
   - Wait for approval (can take several days)

2. **Set Up OAuth2**
   - Create OAuth2 credentials in Google Cloud Console
   - Generate refresh token using OAuth2 playground
   - Get customer ID from Google Ads interface

---

## 🐳 Docker Deployment

### Local Development
```bash
# Build image
docker build -t marketing-agent .

# Run locally
docker run -p 8080:8080 --env-file .env marketing-agent

# Test health endpoint
curl http://localhost:8080/health
```

### Production Container Registry
```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/your-project-id/marketing-agent:latest .

# Deploy to Cloud Run
gcloud run deploy marketing-agent \
    --image gcr.io/your-project-id/marketing-agent:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated
```

---

## 📊 Monitoring and Maintenance

### Health Checks
```bash
# System health
curl https://your-service-url/health

# API status
curl https://your-service-url/

# Dashboard
curl https://your-service-url/dashboard
```

### Logging
```bash
# View application logs
gcloud logs read --service=marketing-agent --limit=50

# Follow logs in real-time
gcloud logs tail --service=marketing-agent

# Filter by severity
gcloud logs read --service=marketing-agent --filter="severity>=ERROR"
```

### Performance Monitoring
```bash
# Check Cloud Run metrics
gcloud run services describe marketing-agent \
    --region=us-central1 \
    --format="table(status.traffic[].percent,status.traffic[].revisionName)"

# View Cloud Scheduler jobs
gcloud scheduler jobs list --location=us-central1
```

### Scaling Configuration
```yaml
# In cloud_deployment.yaml
autoscaling.knative.dev/minScale: "1"    # Minimum instances
autoscaling.knative.dev/maxScale: "10"   # Maximum instances
run.googleapis.com/cpu: "2"              # CPU allocation
run.googleapis.com/memory: "4Gi"         # Memory allocation
```

---

## 🔒 Security Best Practices

### Secret Management
- ✅ All API keys stored in Google Secret Manager
- ✅ No secrets in container images or code
- ✅ Automatic secret rotation support
- ✅ IAM-based access control

### Network Security
- ✅ VPC connector for private network access
- ✅ HTTPS-only communication
- ✅ Service account authentication
- ✅ Minimal IAM permissions

### Container Security
- ✅ Non-root user in container
- ✅ Minimal base image (Python slim)
- ✅ No unnecessary packages
- ✅ Regular security updates

---

## 🚨 Troubleshooting

### Common Issues

#### "Database connection failed"
```bash
# Check Supabase credentials
echo $SUPABASE_URL
echo $SUPABASE_KEY

# Verify database schema is installed
# Go to Supabase dashboard > Table Editor
```

#### "API rate limits exceeded"
```bash
# Check API quotas in respective platforms
# Meta: Business Manager > API Usage
# Google: Google Cloud Console > APIs & Services > Quotas
```

#### "Container build fails"
```bash
# Check Cloud Build logs
gcloud builds log --region=us-central1

# Verify Dockerfile syntax
docker build -t test-build .
```

#### "Service won't start"
```bash
# Check Cloud Run logs
gcloud logs read --service=marketing-agent --limit=10

# Verify environment variables
gcloud run services describe marketing-agent --region=us-central1
```

### Performance Issues

#### "High latency"
- Increase CPU allocation in Cloud Run
- Enable request concurrency optimization
- Check database connection pooling

#### "Memory errors"
- Increase memory allocation (current: 4Gi)
- Monitor memory usage patterns
- Optimize image processing workflows

---

## 📈 Scaling for Production

### Traffic Patterns
- **Minimum Instances**: 1 (always warm)
- **Maximum Instances**: 10 (auto-scaling)
- **Concurrency**: 100 requests per instance
- **Timeout**: 3600 seconds (1 hour)

### Resource Optimization
```yaml
# Recommended production settings
resources:
  limits:
    memory: "4Gi"
    cpu: "2000m"
  requests:
    memory: "2Gi"
    cpu: "1000m"
```

### Cost Optimization
- Use Cloud Scheduler for automated tasks
- Implement request batching for API calls
- Monitor and optimize cold start times
- Use appropriate instance sizing

---

## 🎯 Success Metrics

### System Health
- ✅ 99.9% uptime target
- ✅ < 2 second response time
- ✅ Zero failed deployments
- ✅ Automated monitoring alerts

### Business Metrics
- 📊 Campaign creation success rate
- 📊 Performance tracking accuracy
- 📊 Optimization effectiveness
- 📊 Cost per acquisition improvement

Your Marketing Agent is now production-ready! 🚀

For support or questions, refer to the comprehensive documentation in `setup_instructions.md`.
