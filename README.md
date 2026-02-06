# AWS Error Monitor

Generic, reusable CloudWatch Logs error monitoring system with email alerting via SES.

## Overview

Automated error monitoring solution that:
- Monitors CloudWatch Logs for errors across multiple log groups
- Sends email alerts with detailed error reports when issues are detected
- Supports Lambda, ECS, and RDS log monitoring
- Completely project-agnostic and configurable
- Runs on a 1-hour schedule via EventBridge

## Features

✅ **Multi-Log-Group Support** - Monitor multiple CloudWatch log groups in a single Lambda  
✅ **Service-Type Specific Queries** - Optimized queries for Lambda, ECS, and RDS  
✅ **Multi-Recipient Emails** - Send alerts to multiple email addresses  
✅ **Comprehensive Debug Logging** - Track email delivery, attachment creation, SES responses  
✅ **Infrastructure as Code** - CloudFormation template for reproducible deployments  
✅ **Project Agnostic** - Deploy to any project with just config changes  

## Architecture

```
EventBridge (1 hour) → Lambda Function → CloudWatch Logs Insights
                                      ↓
                                    SES Email (with TXT attachment)
```

## Repository Structure

```
aws-error-monitor/
├── cloudformation/
│   └── template.yaml              # CloudFormation template
├── lambda/
│   └── lambda_function.py         # Lambda function code
├── configs/
│   ├── .env.template              # Config template
│   ├── agadpay-lambda-prod.env    # AgadPay Lambda PROD
│   ├── agadpay-lambda-staging.env # AgadPay Lambda STAGING
│   ├── agadpay-ecs-prod.env       # AgadPay ECS PROD
│   ├── agadpay-ecs-staging.env    # AgadPay ECS STAGING
│   ├── agadpay-rds-prod.env       # AgadPay RDS PROD
│   └── agadpay-rds-staging.env    # AgadPay RDS STAGING
├── scripts/
│   ├── deploy-infrastructure.sh   # Deploy CloudFormation stack
│   ├── deploy-code.sh             # Upload Lambda code
│   └── delete-stack.sh            # Delete stack and resources
├── queries/
│   ├── lambda-query.txt           # Lambda error query
│   ├── ecs-query.txt              # ECS error query
│   └── rds-query.txt              # RDS error query
└── README.md
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS account with:
  - CloudWatch Logs access
  - Lambda permissions
  - SES configured (sender and recipient emails verified)
  - Existing IAM role for Lambda execution with required policies:
    - CloudWatch Logs read access (StartQuery, GetQueryResults)
    - SES send permissions (SendEmail, SendRawEmail)

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/aws-error-monitor.git
cd aws-error-monitor
```

### 2. Configure for Your Project

Copy the template and fill in your values:

```bash
cp configs/.env.template configs/myproject-lambda-prod.env
vim configs/myproject-lambda-prod.env
```

Example configuration:

```bash
PROJECT_NAME=MyProject
ENVIRONMENT=PROD
SERVICE_NAME=Lambda Functions
SERVICE_TYPE=lambda
LOG_GROUPS=/aws/lambda/service1,/aws/lambda/service2
SENDER_EMAIL=alerts@example.com
RECIPIENT_EMAIL=team@example.com,manager@example.com
INTERVAL_MINUTES=60
AWS_REGION=ap-southeast-1
STACK_NAME=myproject-lambda-monitor-prod
IAM_ROLE_ARN=arn:aws:iam::123456789012:role/lambda-execution-role
```

### 3. Deploy Infrastructure

```bash
./scripts/deploy-infrastructure.sh configs/myproject-lambda-prod.env
```

This creates:
- Lambda function (with placeholder code)
- EventBridge schedule rule (1 hour interval)
- CloudWatch Log Group for Lambda logs
- Lambda permissions

### 4. Deploy Lambda Code

```bash
./scripts/deploy-code.sh configs/myproject-lambda-prod.env
```

This uploads the actual monitoring code to your Lambda function.

### 5. Verify

- Check CloudFormation console for stack status
- View Lambda function in AWS Console
- Check CloudWatch Logs for Lambda execution logs
- Wait for next scheduled run or test manually

## Configuration Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `PROJECT_NAME` | Project identifier | AgadPay, APDU, MyProject |
| `ENVIRONMENT` | Environment (PROD/STAGING/UAT) | PROD |
| `SERVICE_NAME` | Human-readable service name | Lambda Functions |
| `SERVICE_TYPE` | Service type (lambda/ecs/rds) | lambda |
| `LOG_GROUPS` | Comma-separated log groups | /aws/lambda/svc1,/aws/lambda/svc2 |
| `SENDER_EMAIL` | SES verified sender | alerts@example.com |
| `RECIPIENT_EMAIL` | Comma-separated recipients | team@example.com,manager@example.com |
| `INTERVAL_MINUTES` | Monitoring window (minutes) | 60 |
| `AWS_REGION` | AWS region | ap-southeast-1 |
| `STACK_NAME` | CloudFormation stack name | myproject-lambda-monitor-prod |
| `IAM_ROLE_ARN` | Existing Lambda execution role ARN | arn:aws:iam::123456789012:role/... |

## Email Alert Format

### Subject
```
[PROD] ALERT: Lambda Functions Errors
[STAGING] ALERT: ECS Services Errors
```

### Body
- Monitoring period details
- Error count summary
- Log group breakdown
- Recommended actions

### Attachment
```
myproject_lambda_errors_prod_20251120_1030.txt
```

Contains:
- Complete error report
- Timestamps and log streams
- Full error messages
- Up to 50 errors per log group

## Service-Specific Queries

```python
# Lambda
Searches for: 
- ERROR, 
- Exception, 
- Traceback, 
- failed

# ECS
Searches for: 
- An unexpected error, 
- unhandled exception, 
- ERROR, 
- FATAL

# RDS
Searches for: 
- ERROR, 
- FATAL, 
- PANIC, 
- deadlock, 
- connection issues

# Custom Queries
- Custom queries can be added in `queries/` directory.
```

## Deployment Commands

### Deploy Multiple Monitors

```bash
# Deploy all AgadPay monitors
for config in configs/agadpay-*.env; do
    ./scripts/deploy-infrastructure.sh $config
    ./scripts/deploy-code.sh $config
done
```

### Update Lambda Code Only

```bash
# Update code for specific monitor
./scripts/deploy-code.sh configs/agadpay-lambda-prod.env

# Update all monitors
for config in configs/*.env; do
    ./scripts/deploy-code.sh $config
done
```

### Delete Stack

```bash
./scripts/delete-stack.sh configs/agadpay-lambda-prod.env
```

## Troubleshooting

### No Email Received

1. Check CloudWatch Logs: `/aws/lambda/{function-name}`
2. Look for "MessageId" in logs - if present, email was sent
3. Verify sender and recipient emails are verified in SES
4. Check spam/junk folder
5. Review SES sending statistics

### Lambda Timeout

- Increase timeout in CloudFormation template (default: 300 seconds)
- Reduce number of log groups per monitor
- Reduce `INTERVAL_MINUTES` to query less data

### Query Errors

- Verify log group names are correct
- Check IAM permissions for CloudWatch Logs
- Review query syntax in `queries/` directory

## Adding a New Project

### Option 1: Copy Existing Config

```bash
# Copy template
cp configs/.env.template configs/newproject-lambda-prod.env

# Edit configuration
vim configs/newproject-lambda-prod.env

# Deploy
./scripts/deploy-infrastructure.sh configs/newproject-lambda-prod.env
./scripts/deploy-code.sh configs/newproject-lambda-prod.env
```

### Option 2: Use Existing Config as Base

```bash
# Copy similar project config
cp configs/agadpay-lambda-prod.env configs/newproject-lambda-prod.env

# Update values
vim configs/newproject-lambda-prod.env

# Deploy
./scripts/deploy-infrastructure.sh configs/newproject-lambda-prod.env
./scripts/deploy-code.sh configs/newproject-lambda-prod.env
```

## Cost Estimate

Per monitor (monthly):
- Lambda executions: ~720 invocations/month (1/hour) - $0.00 (free tier)
- CloudWatch Logs Insights: ~720 queries/month - ~$0.75
- SES emails: Variable based on error frequency - ~$0.01-0.10
- CloudWatch Logs storage: Lambda logs - ~$0.50

**Total: ~$1.30/month per monitor**

## Security Considerations

- Keep `.env` files out of version control (use `.gitignore`)
- Use existing IAM roles with least-privilege permissions
- Verify all SES emails to prevent abuse
- Review error messages for sensitive data before sending
- Use CloudWatch Logs retention policies

## Support

For issues or questions:
1. Check CloudWatch Logs for Lambda execution details
2. Review SES sending statistics
3. Verify IAM permissions
4. Check CloudFormation stack events

## License

Internal use only

## Contributors

- Vin Lonje

## Changelog

### v1.0.0 (2025-11-20)
- Initial release
- Multi-log-group support
- Service-type specific queries (Lambda, ECS, RDS)
- CloudFormation infrastructure as code
- Automated deployment scripts