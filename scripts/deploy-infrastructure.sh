#!/bin/bash

# ============================================================================
# AWS Error Monitor - Infrastructure Deployment Script
# ============================================================================
# Description: Deploys CloudFormation stack for error monitoring Lambda
# Usage: ./scripts/deploy-infrastructure.sh <config-file>
# Example: ./scripts/deploy-infrastructure.sh configs/agadpay-lambda-prod.env
# ============================================================================

set -e  # Exit on error

CONFIG_FILE=$1

# ============================================================================
# Validation
# ============================================================================

if [ -z "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file required"
    echo ""
    echo "Usage: ./scripts/deploy-infrastructure.sh <config-file>"
    echo ""
    echo "Examples:"
    echo "  ./scripts/deploy-infrastructure.sh configs/agadpay-lambda-prod.env"
    echo "  ./scripts/deploy-infrastructure.sh configs/agadpay-ecs-staging.env"
    echo ""
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

# ============================================================================
# Load Configuration
# ============================================================================

echo "📋 Loading configuration from: $CONFIG_FILE"
source $CONFIG_FILE

# Validate required variables
REQUIRED_VARS=("PROJECT_NAME" "ENVIRONMENT" "SERVICE_NAME" "SERVICE_TYPE" "LOG_GROUPS" "SENDER_EMAIL" "RECIPIENT_EMAIL" "STACK_NAME" "IAM_ROLE_ARN" "AWS_REGION")

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: Required variable $var is not set in config file"
        exit 1
    fi
done

# ============================================================================
# Display Configuration
# ============================================================================

echo ""
echo "🚀 Deploying Error Monitor Infrastructure"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Project:       $PROJECT_NAME"
echo "Environment:   $ENVIRONMENT"
echo "Service:       $SERVICE_NAME"
echo "Type:          $SERVICE_TYPE"
echo "Stack Name:    $STACK_NAME"
echo "Region:        $AWS_REGION"
echo "Log Groups:    $(echo $LOG_GROUPS | cut -c1-60)..."
echo "Sender:        $SENDER_EMAIL"
echo "Recipients:    $RECIPIENT_EMAIL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================================================
# Deploy CloudFormation Stack
# ============================================================================

echo "📦 Deploying CloudFormation stack..."

aws cloudformation deploy \
    --template-file cloudformation/template.yaml \
    --stack-name $STACK_NAME \
    --parameter-overrides \
        ProjectName=$PROJECT_NAME \
        Environment=$ENVIRONMENT \
        ServiceName="$SERVICE_NAME" \
        ServiceType=$SERVICE_TYPE \
        LogGroups="$LOG_GROUPS" \
        SenderEmail=$SENDER_EMAIL \
        RecipientEmail="$RECIPIENT_EMAIL" \
        IntervalMinutes=$INTERVAL_MINUTES \
        ExistingIAMRoleArn=$IAM_ROLE_ARN \
    --capabilities CAPABILITY_IAM \
    --region $AWS_REGION

# ============================================================================
# Deployment Complete
# ============================================================================

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Stack deployed successfully!"
    echo ""
    echo "Next Steps:"
    echo "  1. Deploy Lambda code: ./scripts/deploy-code.sh $CONFIG_FILE"
    echo "  2. Check CloudFormation console for stack status"
    echo "  3. Verify Lambda function in AWS Console"
    echo ""
else
    echo ""
    echo "❌ Stack deployment failed!"
    echo "Check CloudFormation console for error details"
    exit 1
fi