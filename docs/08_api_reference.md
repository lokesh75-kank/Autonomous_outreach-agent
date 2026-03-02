# API Reference

## Overview

The FastAPI backend provides REST endpoints for controlling the outreach system.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

API key authentication via header:
```
X-API-Key: your-api-key
```

## Endpoints

### Jobs

#### Discover Jobs
```http
POST /jobs/discover
Content-Type: application/json

{
    "query": "Machine Learning Engineer",
    "location": "San Francisco, CA",
    "sources": ["jobright", "greenhouse", "lever"],
    "max_results": 50
}
```

**Response:**
```json
{
    "status": "started",
    "task_id": "uuid",
    "message": "Job discovery started"
}
```

#### List Jobs
```http
GET /jobs?status=new&limit=50&offset=0
```

**Response:**
```json
{
    "jobs": [
        {
            "id": "uuid",
            "company": "Waymo",
            "role": "ML Engineer",
            "url": "https://...",
            "skills": ["Python", "TensorFlow"],
            "status": "new",
            "discovered_at": "2024-01-15T10:00:00Z"
        }
    ],
    "total": 150,
    "limit": 50,
    "offset": 0
}
```

#### Get Job Details
```http
GET /jobs/{job_id}
```

### Hiring Managers

#### Discover Hiring Managers
```http
POST /hiring-managers/discover/{job_id}
```

**Response:**
```json
{
    "status": "completed",
    "hiring_managers": [
        {
            "id": "uuid",
            "name": "Sarah Johnson",
            "title": "ML Engineering Manager",
            "linkedin_url": "https://linkedin.com/in/...",
            "relevance_score": 95
        }
    ]
}
```

#### List Hiring Managers for Job
```http
GET /hiring-managers?job_id={job_id}
```

### Outreach

#### Generate Message
```http
POST /outreach/generate
Content-Type: application/json

{
    "job_id": "uuid",
    "hiring_manager_id": "uuid"
}
```

**Response:**
```json
{
    "id": "uuid",
    "message": "Hi Sarah — saw you're hiring...",
    "status": "pending_approval"
}
```

#### Get Approval Queue
```http
GET /outreach/queue?status=pending_approval&limit=20
```

**Response:**
```json
{
    "queue": [
        {
            "id": "uuid",
            "job": {
                "company": "Waymo",
                "role": "ML Engineer"
            },
            "hiring_manager": {
                "name": "Sarah Johnson",
                "title": "ML Manager"
            },
            "message": "Hi Sarah...",
            "status": "pending_approval",
            "created_at": "2024-01-15T10:00:00Z"
        }
    ],
    "total": 15
}
```

#### Approve Outreach
```http
POST /outreach/approve/{outreach_id}
Content-Type: application/json

{
    "message": "Optional edited message"
}
```

#### Reject Outreach
```http
POST /outreach/reject/{outreach_id}
Content-Type: application/json

{
    "reason": "Not relevant"
}
```

#### Bulk Approve
```http
POST /outreach/bulk-approve
Content-Type: application/json

{
    "outreach_ids": ["uuid1", "uuid2", "uuid3"],
    "limit": 20
}
```

#### Execute Approved Outreach
```http
POST /outreach/execute
```

**Response:**
```json
{
    "status": "started",
    "task_id": "uuid",
    "pending_count": 15,
    "message": "Execution started (respecting daily limits)"
}
```

### Statistics

#### Get Dashboard Stats
```http
GET /stats/dashboard
```

**Response:**
```json
{
    "jobs_discovered": 250,
    "hiring_managers_found": 180,
    "messages_generated": 150,
    "connections_sent": 45,
    "connections_accepted": 12,
    "response_rate": 0.267,
    "daily_limit_remaining": 15,
    "today_sent": 5
}
```

#### Get Outreach History
```http
GET /stats/history?days=30
```

### User Profile

#### Update Profile
```http
PUT /profile
Content-Type: application/json

{
    "name": "John Doe",
    "resume_text": "Experienced ML engineer...",
    "target_roles": ["ML Engineer", "Data Scientist"],
    "target_locations": ["San Francisco", "Remote"]
}
```

### System

#### Health Check
```http
GET /health
```

**Response:**
```json
{
    "status": "healthy",
    "database": "connected",
    "browser": "ready",
    "rate_limiter": {
        "connections_remaining": 15,
        "resets_at": "2024-01-16T00:00:00Z"
    }
}
```

## Error Responses

```json
{
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Daily connection limit reached",
        "details": {
            "limit": 20,
            "used": 20,
            "resets_at": "2024-01-16T00:00:00Z"
        }
    }
}
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `RATE_LIMIT_EXCEEDED` | 429 | Daily limit reached |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 422 | Invalid request data |
| `BROWSER_ERROR` | 500 | Browser automation failed |
| `SESSION_EXPIRED` | 401 | LinkedIn session invalid |
| `SAFETY_STOP` | 503 | Safety circuit breaker tripped |

## Webhooks (Optional)

Configure webhook URL for real-time notifications:

```http
POST /webhooks/configure
Content-Type: application/json

{
    "url": "https://your-server.com/webhook",
    "events": ["connection_accepted", "reply_received", "error"]
}
```

Webhook payload:
```json
{
    "event": "connection_accepted",
    "data": {
        "outreach_id": "uuid",
        "hiring_manager": "Sarah Johnson",
        "company": "Waymo"
    },
    "timestamp": "2024-01-15T14:30:00Z"
}
```
