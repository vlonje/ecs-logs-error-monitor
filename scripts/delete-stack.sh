#!/bin/bash

# ============================================================================
# AWS Error Monitor - Stack Deletion Script
# ============================================================================
# Description: Deletes CloudFormation stack and all associated resources
# Usage: ./scripts/delete-stack.sh <config-file>
# Example: ./scripts/delete-stack.sh configs/agadpay-lambda-prod.env
# ============================================================================

set -e  # Exit on error

CONFIG_FILE=$1

# ============================================================================
# Validation
# ============================================================================

if [ -z "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file required"
    echo ""
    echo "Usage: ./scripts/delete-stack.sh <config-file>"
    echo ""
    echo "Examples:"
    echo "  ./scripts/delete-stack.sh configs/agadpay-lambda-prod.env"
    echo "  ./scripts/delete-stack.sh configs/agadpay-ecs-staging.env"
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
if [ -z "$STACK_NAME" ] || [ -z "$AWS_REGION" ]; then
    echo "❌ Error: STACK_NAME and AWS_REGION must be set in config file"
    exit 1
fi

# ============================================================================
# Confirmation
# ============================================================================

echo ""
echo "⚠️  WARNING: Stack Deletion"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Stack Name:    $STACK_NAME"
echo "Region:        $AWS_REGION"
echo "Project:       $PROJECT_NAME"
echo "Environment:   $ENVIRONMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will DELETE the following resources:"
echo "  - Lambda function"
echo "  - EventBridge rule"
echo "  - CloudWatch Log Group"
echo "  - Lambda permissions"
echo ""
read -p "Are you sure you want to delete this stack? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Deletion cancelled"
    exit 0
fi

# ============================================================================
# Delete Stack
# ============================================================================

echo ""
echo "🗑️  Deleting CloudFormation stack..."

aws cloudformation delete-stack \
    --stack-name $STACK_NAME \
    --region $AWS_REGION

echo ""
echo "⏳ Waiting for stack deletion to complete..."
echo "   This may take a few minutes..."

aws cloudformation wait stack-delete-complete \
    --stack-name $STACK_NAME \
    --region $AWS_REGION

# ============================================================================
# Deletion Complete
# ============================================================================

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Stack deleted successfully!"
    echo ""
    echo "Deleted Resources:"
    echo "  - Stack: $STACK_NAME"
    echo "  - All associated Lambda, EventBridge, and CloudWatch resources"
    echo ""
else
    echo ""
    echo "❌ Stack deletion failed!"
    echo "Check CloudFormation console for error details"
    exit 1
fi