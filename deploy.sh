#!/bin/bash

# Marketing Agent GCP Deployment Script
# Usage: ./deploy.sh [environment] [project-id]

set -e

# Configuration
ENVIRONMENT=${1:-development}
PROJECT_ID=${2:-"your-gcp-project-id"}
REGION="us-central1"
SERVICE_NAME="marketing-agent"

echo "🚀 Deploying Marketing Agent to Google Cloud Platform"
echo "Environment: $ENVIRONMENT"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set project
echo "📋 Setting GCP project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable scheduler.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable container.googleapis.com

# Create service account if it doesn't exist
echo "👤 Creating service account..."
gcloud iam service-accounts create marketing-agent-sa \
    --display-name="Marketing Agent Service Account" \
    --description="Service account for Marketing Agent application" \
    || echo "Service account already exists"

# Grant necessary roles
echo "🔐 Granting IAM roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:marketing-agent-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:marketing-agent-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# Create secrets in Secret Manager
echo "🔒 Creating secrets in Secret Manager..."

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if gcloud secrets describe $secret_name --project=$PROJECT_ID &>/dev/null; then
        echo "  Updating existing secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
    else
        echo "  Creating new secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=-
    fi
}

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Please create a .env file with your configuration"
    exit 1
fi

# Read .env file and create secrets
echo "📝 Creating secrets from .env file..."
while IFS= read -r line; do
    # Skip comments and empty lines
    if [[ $line =~ ^[[:space:]]*# ]] || [[ -z "${line// }" ]]; then
        continue
    fi
    
    # Extract key and value
    if [[ $line =~ ^([^=]+)=(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        
        # Convert to lowercase with hyphens for secret names
        secret_name=$(echo "$key" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
        
        # Skip if value is placeholder
        if [[ $value != *"your_"* ]] && [[ $value != *"here"* ]] && [[ -n "$value" ]]; then
            create_or_update_secret "marketing-agent-$secret_name" "$value"
        fi
    fi
done < .env

# Build and submit to Cloud Build
echo "🏗️ Building container image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME:latest .

# Deploy to Cloud Run
echo "🚢 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --service-account marketing-agent-sa@$PROJECT_ID.iam.gserviceaccount.com \
    --memory 4Gi \
    --cpu 2 \
    --concurrency 100 \
    --timeout 3600 \
    --max-instances 10 \
    --min-instances 1 \
    --set-env-vars ENVIRONMENT=$ENVIRONMENT \
    --set-env-vars LOG_LEVEL=INFO

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""

# Create Cloud Scheduler jobs
echo "⏰ Creating Cloud Scheduler jobs..."

# Performance tracking job
gcloud scheduler jobs create http marketing-agent-performance \
    --schedule="0 * * * *" \
    --uri="$SERVICE_URL/campaigns/track" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body="{}" \
    --oidc-service-account-email="marketing-agent-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$REGION \
    || echo "Performance tracking job already exists"

# Budget monitoring job
gcloud scheduler jobs create http marketing-agent-budget \
    --schedule="*/30 * * * *" \
    --uri="$SERVICE_URL/budgets/check" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body="{}" \
    --oidc-service-account-email="marketing-agent-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$REGION \
    || echo "Budget monitoring job already exists"

echo ""
echo "🎉 Marketing Agent deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Test the API: curl $SERVICE_URL/health"
echo "2. Check the dashboard: $SERVICE_URL/dashboard"
echo "3. View logs: gcloud logs read --project=$PROJECT_ID --service=$SERVICE_NAME"
echo "4. Configure your advertising platform API keys in the .env file"
echo "5. Set up your Supabase database using the schema in database/schema.sql"
echo ""
echo "🔧 Configuration URLs:"
echo "• Cloud Run Console: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME/revisions?project=$PROJECT_ID"
echo "• Cloud Scheduler: https://console.cloud.google.com/cloudscheduler?project=$PROJECT_ID"
echo "• Secret Manager: https://console.cloud.google.com/security/secret-manager?project=$PROJECT_ID" 