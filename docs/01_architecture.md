# Architecture Overview

## System Design

The AI Job Outreach Agent is built as a modular, event-driven system with five core agents orchestrated by LangGraph.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Orchestration Layer                          │
│                        (LangGraph + FastAPI)                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│ Job Discovery │           │Hiring Manager │           │Personalization│
│    Agent      │           │   Discovery   │           │    Engine     │
└───────┬───────┘           └───────┬───────┘           └───────┬───────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    ▼
                        ┌───────────────────────┐
                        │   PostgreSQL Database  │
                        └───────────┬───────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Approval    │           │   LinkedIn    │           │   Follow-up   │
│   Dashboard   │           │   Executor    │           │    System     │
└───────────────┘           └───────────────┘           └───────────────┘
```

## Component Responsibilities

### 1. Job Discovery Agent
- Scrapes job listings from multiple sources
- Normalizes data to common schema
- Deduplicates based on URL hash
- Stores in PostgreSQL

### 2. Hiring Manager Discovery Agent
- Takes job listing as input
- Searches Google via Serper API
- Extracts LinkedIn profile information
- Scores relevance of contacts

### 3. Personalization Engine
- Receives job + hiring manager context
- Generates unique connection messages
- Enforces character limits
- Creates variation for each message

### 4. LinkedIn Executor
- Browser automation via Playwright
- Implements safety mechanisms
- Executes approved connection requests
- Logs all actions

### 5. Approval Dashboard
- Streamlit-based web UI
- Shows daily outreach queue
- Allows approve/edit/reject
- Displays statistics

### 6. Follow-up System
- Scheduled job runner
- Tracks connection status
- Queues follow-up messages
- Sends notifications

## Data Flow

1. **Discovery Phase**: Job Discovery Agent finds jobs → stores in DB
2. **Enrichment Phase**: Hiring Manager Agent enriches with contacts → stores in DB
3. **Generation Phase**: Personalization Engine creates messages → adds to queue
4. **Approval Phase**: User reviews queue in dashboard → approves/rejects
5. **Execution Phase**: LinkedIn Executor sends approved connections
6. **Follow-up Phase**: System tracks responses and schedules follow-ups

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Agent Framework | LangGraph + LangChain |
| LLM | OpenAI GPT-4o |
| Database | PostgreSQL + SQLAlchemy |
| API | FastAPI |
| Browser | Playwright |
| Dashboard | Streamlit |
| Scheduler | APScheduler |

## Security Considerations

- API keys stored in environment variables
- LinkedIn session cookies encrypted at rest
- Rate limiting enforced at multiple levels
- Audit logging for all actions
