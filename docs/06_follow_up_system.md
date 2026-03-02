# Follow-up System

## Overview

The Follow-up System tracks connection status and automatically queues appropriate follow-up actions.

## Follow-up Logic

### Timeline

| Day | Status | Action |
|-----|--------|--------|
| 0 | Sent | Wait |
| 3 | No response | Queue follow-up message |
| 7 | Still pending | Final follow-up |
| 14 | No acceptance | Mark as cold |

### On Acceptance

When connection is accepted:
1. Send thank you message
2. Optionally attach resume
3. Mark as "connected"

### On Reply

When contact replies:
1. Notify user immediately (email/Slack)
2. Move to "active conversation"
3. User takes over manually

## Data Schema

```python
class FollowUp:
    id: str
    outreach_id: str          # Original outreach
    type: str                 # follow_up_1, follow_up_2, thank_you
    scheduled_for: datetime
    message: str
    status: str               # pending, sent, cancelled
    completed_at: datetime
```

## Scheduler Implementation

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# Check for follow-ups every hour
scheduler.add_job(
    process_followups,
    CronTrigger(minute=0),  # Every hour on the hour
    id="followup_processor"
)

# Check connection status daily
scheduler.add_job(
    check_connection_status,
    CronTrigger(hour=10),  # 10 AM daily
    id="status_checker"
)

scheduler.start()
```

## Follow-up Messages

### Day 3 Follow-up
```
Hi {name} — just following up on my connection request. Would love 
to connect and learn more about the {role} opportunity at {company}!
```

### Day 7 Final Follow-up
```
Hi {name} — sending a final note about the {role} position. 
If timing isn't right, no worries. Best of luck with the search!
```

### Thank You (on accept)
```
Thanks for connecting, {name}! I'm excited about the {role} 
opportunity. Happy to share my background — here's my resume. 
Would love to chat when convenient!
```

## Status Tracking

```python
async def check_connection_status():
    """Check LinkedIn for connection status updates."""
    pending = await db.get_pending_connections()
    
    for outreach in pending:
        status = await linkedin.check_connection_status(
            outreach.profile_url
        )
        
        if status == "connected":
            await queue_thank_you(outreach)
        elif status == "message_received":
            await notify_user(outreach)
```

## Notification System

```python
async def notify_user(outreach: Outreach):
    """Notify user of important events."""
    
    # Email notification
    await send_email(
        to=user.email,
        subject=f"Reply from {outreach.hiring_manager_name}",
        body=f"You received a reply regarding {outreach.role} at {outreach.company}"
    )
    
    # Slack notification (optional)
    if user.slack_webhook:
        await send_slack(user.slack_webhook, message)
```

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `FOLLOWUP_DAY_1` | Days until first follow-up | 3 |
| `FOLLOWUP_DAY_2` | Days until second follow-up | 7 |
| `MAX_FOLLOWUPS` | Maximum follow-ups per contact | 2 |
| `COLD_AFTER_DAYS` | Days until marked cold | 14 |
