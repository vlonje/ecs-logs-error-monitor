import boto3
import os
import time
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# ============================================================================
# LOGGER CONFIGURATION
# ============================================================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    '[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

if logger.handlers:
    for handler in logger.handlers:
        handler.setFormatter(formatter)

# ============================================================================
# CONFIGURATION - All values from environment variables
# ============================================================================

PROJECT_NAME = os.environ.get('PROJECT_NAME', 'Generic')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'UAT')
SERVICE_NAME = os.environ.get('SERVICE_NAME', 'Error Monitor')
SERVICE_TYPE = os.environ.get('SERVICE_TYPE', 'lambda')

# Parse log groups - supports multiple comma-separated values
LOG_GROUPS_RAW = os.environ.get('LOG_GROUPS', '')
LOG_GROUPS = [lg.strip() for lg in LOG_GROUPS_RAW.split(',') if lg.strip()]

SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'alerts@example.com')

# Parse recipients - supports multiple comma-separated values
RECIPIENT_EMAILS_RAW = os.environ.get('RECIPIENT_EMAIL', 'alerts@example.com')
RECIPIENT_EMAILS = [email.strip() for email in RECIPIENT_EMAILS_RAW.split(',')]

INTERVAL_MINUTES = int(os.environ.get('INTERVAL_MINUTES', '60'))
AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-1')

# Initialize AWS clients
logs_client = boto3.client('logs', region_name=AWS_REGION)
ses_client = boto3.client('ses', region_name=AWS_REGION)

# ============================================================================
# QUERIES - Service-type specific
# ============================================================================

LAMBDA_QUERY = r"""
fields @timestamp, @message, @requestId, @logStream
| sort @timestamp desc
| limit 10000
| filter @message like /ERROR/
  or @message like /Error/
  or @message like /Exception/
  or @message like /exception/
  or @message like /Traceback/
  or @message like /failed/i
  or @message like /FAILED/
  or @level = "ERROR"
  or @level = "FATAL"
"""

ECS_QUERY = r"""
fields @timestamp, @message, @logStream
| sort @timestamp desc
| limit 10000
| filter @message like /An unexpected error/
  or @message like /unhandled exception/i
  or @message like /ERROR/
  or @message like /Error/
  or @message like /FATAL/
  or @message like /Fatal/
  or @message like /failed/i
  or @message like /exception/i
"""

RDS_QUERY = r"""
fields @timestamp, @message
| sort @timestamp desc
| limit 10000
| filter @message like /ERROR:/
  or @message like /FATAL:/
  or @message like /PANIC:/
  or @message like /deadlock/i
  or @message like /connection reset/i
  or @message like /could not connect/i
  or @message like /syntax error/i
  or @message like /duplicate key/i
  or @message like /constraint violation/i
"""

# Select query based on service type
if SERVICE_TYPE == 'lambda':
    QUERY = LAMBDA_QUERY
elif SERVICE_TYPE == 'ecs':
    QUERY = ECS_QUERY
elif SERVICE_TYPE == 'rds':
    QUERY = RDS_QUERY
else:
    QUERY = LAMBDA_QUERY  # Default

# DEBUG: Log configuration
logger.info("=" * 80)
logger.info(f"{PROJECT_NAME.upper()} {SERVICE_NAME.upper()} ERROR MONITOR - CONFIGURATION")
logger.info("=" * 80)
logger.info(f"Project: {PROJECT_NAME}")
logger.info(f"Environment: {ENVIRONMENT}")
logger.info(f"Service Name: {SERVICE_NAME}")
logger.info(f"Service Type: {SERVICE_TYPE}")
logger.info(f"Log Groups ({len(LOG_GROUPS)}):")
for idx, lg in enumerate(LOG_GROUPS, 1):
    logger.info(f"  {idx}. {lg}")
logger.info(f"Sender: {SENDER_EMAIL}")
logger.info(f"DEBUG: Recipient Configuration:")
logger.info(f"  Raw value: {RECIPIENT_EMAILS_RAW}")
logger.info(f"  Parsed recipients: {RECIPIENT_EMAILS}")
logger.info(f"  Number of recipients: {len(RECIPIENT_EMAILS)}")
for idx, recipient in enumerate(RECIPIENT_EMAILS, 1):
    logger.info(f"    Recipient #{idx}: {recipient}")
logger.info(f"Scan Interval: {INTERVAL_MINUTES} minutes")
logger.info(f"Region: {AWS_REGION}")
logger.info("=" * 80)

# ============================================================================
# LAMBDA HANDLER
# ============================================================================

def lambda_handler(event, context):
    """
    Monitor CloudWatch Logs for unexpected errors across multiple log groups.
    """
    logger.info("\n" + "=" * 80)
    logger.info(f"{PROJECT_NAME.upper()} {SERVICE_NAME.upper()} ERROR MONITORING - START")
    logger.info(f"Execution Time: {datetime.utcnow().isoformat()} UTC")
    logger.info("=" * 80 + "\n")
    
    # Calculate time window
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=INTERVAL_MINUTES)
    start_epoch = int(start_time.timestamp() * 1000)
    end_epoch = int(end_time.timestamp() * 1000)
    
    logger.info(f"Monitoring Window:")
    logger.info(f"  Start: {start_time.isoformat()} UTC")
    logger.info(f"  End:   {end_time.isoformat()} UTC")
    logger.info(f"  Duration: {INTERVAL_MINUTES} minutes\n")
    
    # Query all log groups
    all_results = {}
    total_errors = 0
    
    logger.info(f"Querying {len(LOG_GROUPS)} Log Groups:")
    for log_group in LOG_GROUPS:
        logger.info(f"  Processing: {log_group}")
        results = query_logs(log_group, QUERY, start_epoch, end_epoch)
        if results:
            all_results[log_group] = results
            total_errors += len(results)
            logger.info(f"    ✓ Found {len(results)} errors")
        else:
            logger.info(f"    ✓ No errors found")
    
    # Check if any errors were found
    if not all_results:
        logger.info(f"\n[SUCCESS] NO ERRORS DETECTED in {PROJECT_NAME} {SERVICE_NAME}")
        logger.info("=" * 80 + "\n")
        
        return {
            'statusCode': 200,
            'body': f'No errors found in {PROJECT_NAME} {SERVICE_NAME}'
        }
    
    # Errors detected - generate report and send alert
    logger.info(f"\n[ALERT] ERRORS DETECTED: {total_errors} errors across {len(all_results)} log groups")
    
    # Generate error summary
    logger.info(f"DEBUG: Generating error summary...")
    error_summary = generate_error_summary(all_results, total_errors)
    logger.info(f"DEBUG: Error summary generated")
    logger.info(f"  Total errors: {error_summary['total_errors']}")
    logger.info(f"  Affected log groups: {error_summary['affected_log_groups']}")
    
    # Format report
    logger.info(f"DEBUG: Formatting error report...")
    log_content = format_error_report(all_results, start_time, end_time, error_summary)
    logger.info(f"DEBUG: Error report formatted")
    logger.info(f"  Report length: {len(log_content)} characters")
    logger.info(f"  Report size: {len(log_content.encode('utf-8'))} bytes")
    logger.info(f"  DEBUG: Attachment will be created: YES")
    
    # Send email alert
    send_email_with_attachment(log_content, start_time, end_time, total_errors, error_summary)
    
    logger.info(f"\n[SUCCESS] MONITORING COMPLETE - {total_errors} errors reported")
    logger.info("=" * 80 + "\n")
    
    return {
        'statusCode': 200,
        'body': f'Found and reported {total_errors} errors in {PROJECT_NAME} {SERVICE_NAME}'
    }

# ============================================================================
# QUERY EXECUTION
# ============================================================================

def query_logs(log_group, query, start_epoch, end_epoch):
    """
    Execute CloudWatch Logs Insights query.
    """
    try:
        # Start query
        response = logs_client.start_query(
            logGroupName=log_group,
            startTime=start_epoch,
            endTime=end_epoch,
            queryString=query
        )
        
        query_id = response['queryId']
        logger.info(f"    Query ID: {query_id}")
        
        # Poll for results
        max_wait = 60
        interval = 2
        elapsed = 0
        
        while elapsed < max_wait:
            result = logs_client.get_query_results(queryId=query_id)
            status = result['status']
            
            if status == 'Complete':
                results = result['results']
                return results
            
            elif status in ['Failed', 'Cancelled']:
                logger.error(f"    [ERROR] Query {status.lower()}")
                return []
            
            time.sleep(interval)
            elapsed += interval
        
        logger.error(f"    [ERROR] Query timeout after {max_wait}s")
        return []
        
    except Exception as e:
        logger.error(f"    [ERROR] Query error: {str(e)}", exc_info=True)
        return []

# ============================================================================
# ERROR ANALYSIS
# ============================================================================

def generate_error_summary(all_results, total_errors):
    """
    Analyze errors from multiple log groups and generate summary.
    """
    summary = {
        'total_errors': total_errors,
        'affected_log_groups': len(all_results),
        'log_group_breakdown': {},
        'first_error_time': None,
        'last_error_time': None
    }
    
    # Collect breakdown per log group
    for log_group, results in all_results.items():
        summary['log_group_breakdown'][log_group] = len(results)
        
        # Track overall first and last error times
        for result in results:
            timestamp = next((f['value'] for f in result if f['field'] == '@timestamp'), None)
            if timestamp:
                if not summary['first_error_time']:
                    summary['first_error_time'] = timestamp
                summary['last_error_time'] = timestamp
    
    return summary

# ============================================================================
# REPORT FORMATTING
# ============================================================================

def format_error_report(all_results, start_time, end_time, summary):
    """
    Format error log report with summary for multiple log groups.
    """
    lines = []
    
    # Header with Environment
    lines.append("=" * 80 + "\n")
    lines.append(f"{PROJECT_NAME.upper()} - {SERVICE_NAME.upper()} ERROR REPORT [{ENVIRONMENT}]\n")
    lines.append("=" * 80 + "\n\n")
    
    # Time Range
    lines.append("MONITORING PERIOD\n")
    lines.append("-" * 80 + "\n")
    lines.append(f"Start Time:  {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    lines.append(f"End Time:    {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    lines.append(f"Duration:    {INTERVAL_MINUTES} minutes\n\n")
    
    # Summary Statistics
    lines.append("ERROR SUMMARY\n")
    lines.append("-" * 80 + "\n")
    lines.append(f"Total Errors Found:     {summary['total_errors']}\n")
    lines.append(f"Project:                {PROJECT_NAME}\n")
    lines.append(f"Environment:            {ENVIRONMENT}\n")
    lines.append(f"Service:                {SERVICE_NAME}\n")
    lines.append(f"Affected Log Groups:    {summary['affected_log_groups']}\n")
    lines.append(f"First Error Occurred:   {summary['first_error_time']}\n")
    lines.append(f"Last Error Occurred:    {summary['last_error_time']}\n\n")
    
    # Log Group Breakdown
    if summary['log_group_breakdown']:
        lines.append("ERROR BREAKDOWN BY LOG GROUP\n")
        lines.append("-" * 80 + "\n")
        for log_group, count in sorted(summary['log_group_breakdown'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / summary['total_errors']) * 100
            lines.append(f"  {log_group}\n")
            lines.append(f"    {count:>4} errors ({percentage:>5.1f}%)\n\n")
    
    lines.append("=" * 80 + "\n\n")
    
    # Detailed Error Logs - grouped by log group
    lines.append("DETAILED ERROR LOGS\n")
    lines.append("=" * 80 + "\n\n")
    
    for log_group, results in all_results.items():
        lines.append(f"\n{'#' * 80}\n")
        lines.append(f"LOG GROUP: {log_group}\n")
        lines.append(f"Error Count: {len(results)}\n")
        lines.append(f"{'#' * 80}\n\n")
        
        # Show first 50 errors per log group
        for i, result in enumerate(results[:50], 1):
            timestamp = next((f['value'] for f in result if f['field'] == '@timestamp'), 'N/A')
            message = next((f['value'] for f in result if f['field'] == '@message'), 'N/A')
            stream = next((f['value'] for f in result if f['field'] == '@logStream'), 'N/A')
            
            lines.append(f"ERROR #{i}\n")
            lines.append(f"Timestamp:   {timestamp}\n")
            lines.append(f"Log Stream:  {stream}\n")
            lines.append(f"Message:     {message}\n")
            lines.append("-" * 80 + "\n\n")
        
        # Truncation notice
        if len(results) > 50:
            lines.append(f"... and {len(results) - 50} more errors (truncated for readability)\n\n")
    
    # Footer
    lines.append("=" * 80 + "\n")
    lines.append("Full details available in CloudWatch Logs Insights\n")
    lines.append("=" * 80 + "\n")
    lines.append("END OF REPORT\n")
    lines.append("=" * 80 + "\n")
    
    return ''.join(lines)

# ============================================================================
# EMAIL DELIVERY
# ============================================================================

def send_email_with_attachment(log_content, start_time, end_time, error_count, summary):
    """
    Send email alert with error report attachment.
    """
    try:
        logger.info("=" * 80)
        logger.info("DEBUG: Starting email send process")
        
        # Email subject
        subject = f"[{ENVIRONMENT}] ALERT: {SERVICE_NAME} Errors"
        logger.info(f"  Subject: {subject}")
        
        # Email body
        body_text = f"""{PROJECT_NAME} {SERVICE_NAME} Error Alert - {ENVIRONMENT}

================================================================================

MONITORING PERIOD
  Time Range: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC
  Duration: {INTERVAL_MINUTES} minutes

ALERT SUMMARY
  Total Errors Found: {error_count}
  Project: {PROJECT_NAME}
  Environment: {ENVIRONMENT}
  Service: {SERVICE_NAME}
  Affected Log Groups: {summary['affected_log_groups']}

LOG GROUP BREAKDOWN
"""
        
        # Add log group breakdown to email body
        for log_group, count in sorted(summary['log_group_breakdown'].items(), key=lambda x: x[1], reverse=True):
            body_text += f"  - {log_group}: {count} errors\n"
        
        body_text += f"""
================================================================================

DETAILED INFORMATION
Please review the attached file for complete error logs, timestamps, and 
log stream information. The attachment contains full error messages and 
context for troubleshooting.

RECOMMENDED ACTIONS
1. Review the attached error report
2. Check CloudWatch Logs for additional context
3. Investigate affected log groups and streams
4. Correlate errors with application deployments or infrastructure changes

================================================================================

This is an automated alert from the {PROJECT_NAME} monitoring system.
Environment: {ENVIRONMENT}
Region: {AWS_REGION}
"""
        
        logger.info(f"  Email body length: {len(body_text)} characters")
        
        # Create email
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = ', '.join(RECIPIENT_EMAILS)
        
        # DEBUG: Log recipient details
        logger.info(f"DEBUG: Email headers configured")
        logger.info(f"  From: {SENDER_EMAIL}")
        logger.info(f"  To (header): {', '.join(RECIPIENT_EMAILS)}")
        logger.info(f"  Number of recipients: {len(RECIPIENT_EMAILS)}")
        for idx, recipient in enumerate(RECIPIENT_EMAILS, 1):
            logger.info(f"    Recipient #{idx}: {recipient}")
        
        # Attach body
        msg.attach(MIMEText(body_text, 'plain'))
        logger.info(f"  Email body attached successfully")
        
        # Attach error report
        filename = f"{PROJECT_NAME.lower()}_{SERVICE_TYPE}_errors_{ENVIRONMENT.lower()}_{start_time.strftime('%Y%m%d_%H%M')}.txt"
        
        # DEBUG: Log attachment details
        logger.info(f"DEBUG: Creating attachment (TXT file)")
        logger.info(f"  Filename: {filename}")
        logger.info(f"  Content length: {len(log_content)} characters")
        logger.info(f"  Content size: {len(log_content.encode('utf-8', errors='replace'))} bytes")
        logger.info(f"  Attachment created: YES")
        
        attachment = MIMEApplication(log_content.encode('utf-8', errors='replace'))
        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(attachment)
        
        logger.info(f"  Attachment added to email successfully")
        logger.info(f"  Total MIME parts: {len(msg.get_payload())} (1=body, 2=body+attachment)")
        
        # DEBUG: Log final recipient list before SES call
        logger.info(f"DEBUG: Preparing to send email via SES")
        logger.info(f"  Destinations for SES API: {RECIPIENT_EMAILS}")
        logger.info(f"  Destination type: {type(RECIPIENT_EMAILS)}")
        
        # Send via SES
        logger.info(f"DEBUG: Calling SES send_raw_email API...")
        response = ses_client.send_raw_email(
            Source=SENDER_EMAIL,
            Destinations=RECIPIENT_EMAILS,
            RawMessage={'Data': msg.as_string()}
        )
        
        # DEBUG: Log SES response
        logger.info(f"DEBUG: SES Response received")
        logger.info(f"  Full response: {response}")
        logger.info(f"  MessageId: {response.get('MessageId', 'N/A')}")
        logger.info(f"  HTTP Status Code: {response.get('ResponseMetadata', {}).get('HTTPStatusCode', 'N/A')}")
        logger.info(f"  Request ID: {response.get('ResponseMetadata', {}).get('RequestId', 'N/A')}")
        logger.info(f"  Retry Attempts: {response.get('ResponseMetadata', {}).get('RetryAttempts', 0)}")
        
        # Success log
        logger.info(f"[SUCCESS] Email Sent Successfully")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  To: {', '.join(RECIPIENT_EMAILS)}")
        logger.info(f"  Message ID: {response['MessageId']}")
        logger.info(f"  Attachment: {filename}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"[ERROR] Email sending failed")
        logger.error(f"  Error type: {type(e).__name__}")
        logger.error(f"  Error message: {str(e)}")
        logger.error(f"  Full traceback:", exc_info=True)
        logger.info("  Attempting fallback email...")
        send_simple_email(log_content[:2000], start_time, end_time, error_count)

def send_simple_email(log_content, start_time, end_time, error_count):
    """
    Fallback: Send simple email without attachment.
    """
    try:
        logger.info("=" * 80)
        logger.info("DEBUG: Starting fallback email (no attachment)")
        
        # Email subject
        subject = f"[{ENVIRONMENT}] ALERT: {SERVICE_NAME} Errors"
        
        body = f"""{PROJECT_NAME} {SERVICE_NAME} Error Alert - {ENVIRONMENT}

Time Range: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC
Total Errors Found: {error_count}
Project: {PROJECT_NAME}
Environment: {ENVIRONMENT}
Service: {SERVICE_NAME}

ERROR LOG PREVIEW (First 2000 characters):
{log_content}

Note: This is a fallback notification. The complete error report could not be attached.
Please check CloudWatch Logs for full details.

This is an automated alert from the {PROJECT_NAME} monitoring system.
Environment: {ENVIRONMENT}
"""
        
        # DEBUG: Log fallback email details
        logger.info(f"  Recipients: {RECIPIENT_EMAILS}")
        logger.info(f"  Number of recipients: {len(RECIPIENT_EMAILS)}")
        logger.info(f"  Attachment: NONE (fallback mode)")
        
        response = ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': RECIPIENT_EMAILS},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        
        # DEBUG: Log fallback response
        logger.info(f"DEBUG: Fallback email SES response")
        logger.info(f"  MessageId: {response.get('MessageId', 'N/A')}")
        logger.info(f"  HTTP Status: {response.get('ResponseMetadata', {}).get('HTTPStatusCode', 'N/A')}")
        logger.info(f"[SUCCESS] Fallback email sent: {response['MessageId']}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"[ERROR] Fallback email failed")
        logger.error(f"  Error: {str(e)}")
        logger.error(f"  Full traceback:", exc_info=True)