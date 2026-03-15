#!/bin/bash
set -e

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
SERVICE_NAME="understudy"
REGION="us-central1"

echo "Building and deploying to Cloud Run..."

gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME ./cloud/

gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,VERTEX_LOCATION=$REGION" \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 3

URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo ""
echo "Deployed to: $URL"
echo "Health check: $URL/health"
