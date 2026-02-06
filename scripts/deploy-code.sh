#!/bin/bash

# ============================================================================
# AWS Error Monitor - Lambda Code Deployment Script
# ============================================================================
# Description: Packages and uploads Lambda function code
# Usage: ./scripts/deploy-code.sh <config-file>
# Example: ./scripts/deploy-code.sh configs/agadpay-lambda-prod.env
# ============================================================================

set -e  # Exit on error

CONFIG_FILE=$1

# ============================================================================
# Validation
# ============================================================================

if [ -z "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file required"
    echo ""
    echo "Usage: ./scripts/deploy-code.sh <config-file>"
    echo ""
    echo "Examples:"
    echo "  ./scripts/deploy-code.sh configs/agadpay-lambda-prod.env"
    echo "  ./scripts/deploy-code.sh configs/agadpay-ecs-staging.env"
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
# Display Configuration
# ============================================================================

echo ""
echo "📦 Deploying Lambda Code"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Stack Name:    $STACK_NAME"
echo "Region:        $AWS_REGION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================================================
# Get Lambda Function Name from Stack
# ============================================================================

echo "🔍 Getting Lambda function name from CloudFormation stack..."

FUNCTION_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text \
    --region $AWS_REGION 2>/dev/null)

if [ -z "$FUNCTION_NAME" ]; then
    echo "❌ Error: Could not find Lambda function in stack: $STACK_NAME"
    echo "Make sure the infrastructure is deployed first:"
    echo "  ./scripts/deploy-infrastructure.sh $CONFIG_FILE"
    exit 1
fi

echo "✅ Found Lambda function: $FUNCTION_NAME"

# ============================================================================
# Package Lambda Code
# ============================================================================

echo ""
echo "📦 Packaging Lambda code..."

# Create temporary directory for packaging
TMP_DIR=$(mktemp -d)
ZIP_FILE="$TMP_DIR/lambda.zip"

# Copy Lambda code to temp directory
cp lambda/lambda_function.py $TMP_DIR/

# Create ZIP package
cd $TMP_DIR
zip -q lambda.zip lambda_function.py
cd - > /dev/null

echo "✅ Package created: $(du -h $ZIP_FILE | cut -f1)"

# ============================================================================
# Upload Lambda Code
# ============================================================================

echo ""
echo "☁️  Uploading code to Lambda function..."

aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://$ZIP_FILE \
    --region $AWS_REGION \
    --output json > /dev/null

# ============================================================================
# Cleanup
# ============================================================================

rm -rf $TMP_DIR

# ============================================================================
# Deployment Complete
# ============================================================================

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Lambda code deployed successfully!"
    echo ""
    echo "Function Details:"
    echo "  Name:     $FUNCTION_NAME"
    echo "  Region:   $AWS_REGION"
    echo ""
    echo "Next Steps:"
    echo "  1. Test the Lambda function manually in AWS Console"
    echo "  2. Check CloudWatch Logs: /aws/lambda/$FUNCTION_NAME"
    echo "  3. Wait for next scheduled execution (1 hour interval)"
    echo ""
else
    echo ""
    echo "❌ Lambda code deployment failed!"
    exit 1
fi