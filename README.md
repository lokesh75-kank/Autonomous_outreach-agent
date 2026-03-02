# AI Job Outreach Agent

An autonomous AI-powered system for job discovery, hiring manager identification, and personalized LinkedIn outreach with human-in-the-loop approval.

## Features

- **Job Discovery Agent**: Scrapes jobs from Jobright, LinkedIn, Greenhouse, and Lever
- **Hiring Manager Discovery**: Finds relevant recruiters and hiring managers using Serper API
- **AI Personalization Engine**: Generates unique, role-aware connection messages using GPT-4
- **LinkedIn Execution Agent**: Automates connection requests with human-like behavior
- **Approval Dashboard**: Daily review queue for semi-autonomous operation
- **Follow-up System**: Automated follow-ups and response tracking

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Job Discovery  │────▶│  Hiring Manager  │────▶│ Personalization │
│     Agent       │     │    Discovery     │     │     Engine      │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Follow-up     │◀────│    LinkedIn      │◀────│    Approval     │
│    System       │     │    Executor      │     │    Dashboard    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API Key
- Serper API Key

### Installation

1. Clone the repository:
```bash
cd linkedin_outreach_agent
```

2. Copy environment file and configure:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Start with Docker:
```bash
docker-compose up -d
```

4. Run database migrations:
```bash
docker-compose exec api alembic upgrade head
```

5. Access the services:
- API: http://localhost:8000
- Dashboard: http://localhost:8501
- API Docs: http://localhost:8000/docs

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Start PostgreSQL (or use Docker)
docker-compose up -d postgres

# Run API server
uvicorn src.api.main:app --reload

# Run dashboard (separate terminal)
streamlit run src/dashboard/app.py
```

## Safety Features

This system implements strict safety measures to protect your LinkedIn account:

- **Rate Limiting**: Maximum 20 connections per day (configurable)
- **Random Delays**: 45-120 seconds between actions
- **Typing Simulation**: Human-like typing speed (50-150ms per character)
- **Optimal Windows**: Sends during peak recruiter activity times
- **Human Approval**: Semi-autonomous mode requires daily approval

### Optimal Outreach Windows (PST)

Connection requests are sent when recruiters are most active:

| Window | Time | Why |
|--------|------|-----|
| **Morning Rush** | 8 AM - 10 AM | Recruiters check messages & review applicants |
| **Afternoon Boost** | 2 PM - 4 PM | Final check before end of day |

*This increases acceptance rates by appearing at the top of their inbox during active checking.*

## Project Structure

```
├── src/
│   ├── agents/
│   │   ├── job_discovery/      # Job scraping agents
│   │   ├── hiring_manager/     # People discovery
│   │   ├── personalization/    # LLM message generation
│   │   ├── linkedin_executor/  # Browser automation
│   │   └── follow_up/          # Follow-up scheduling
│   ├── core/
│   │   ├── config.py           # Configuration
│   │   ├── database.py         # Database connection
│   │   ├── rate_limiter.py     # Safety rate limiting
│   │   └── scheduler.py        # Job scheduling
│   ├── api/
│   │   └── main.py             # FastAPI endpoints
│   ├── dashboard/
│   │   └── app.py              # Streamlit dashboard
│   └── models/
│       └── schemas.py          # Pydantic models
├── docs/                       # Documentation
├── tests/                      # Test suite
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/discover` | POST | Trigger job discovery |
| `/jobs` | GET | List discovered jobs |
| `/hiring-managers/discover/{job_id}` | POST | Find hiring managers |
| `/outreach/generate/{job_id}` | POST | Generate personalized message |
| `/outreach/queue` | GET | Get approval queue |
| `/outreach/approve/{id}` | POST | Approve outreach |
| `/outreach/execute` | POST | Execute approved outreach |

## Configuration

See `.env.example` for all configuration options.

### Key Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_CONNECTIONS_PER_DAY` | Daily connection limit | 20 |
| `MIN_DELAY_SECONDS` | Minimum delay between actions | 45 |
| `MAX_DELAY_SECONDS` | Maximum delay between actions | 120 |
| `USE_OPTIMAL_WINDOWS` | Use peak recruiter hours | true |
| `MORNING_WINDOW_START` | Morning rush start (24h) | 8 |
| `MORNING_WINDOW_END` | Morning rush end (24h) | 10 |
| `AFTERNOON_WINDOW_START` | Afternoon boost start (24h) | 14 |
| `AFTERNOON_WINDOW_END` | Afternoon boost end (24h) | 16 |

## License

MIT License - See LICENSE file for details.

## Disclaimer

This tool is for educational purposes. Use responsibly and in compliance with LinkedIn's Terms of Service. The authors are not responsible for any account restrictions or bans resulting from use of this software.
