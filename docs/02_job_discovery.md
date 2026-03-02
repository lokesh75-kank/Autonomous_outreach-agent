# Job Discovery Agent

## Overview

The Job Discovery Agent is responsible for finding relevant job listings from multiple sources and normalizing them into a common format.

## Supported Sources

### 1. Jobright
- Web scraping via Playwright
- Search by role keywords and location
- Extracts: title, company, description, skills, URL

### 2. LinkedIn Jobs
- API-based approach where available
- Fallback to web scraping
- Requires authentication for full details

### 3. Greenhouse
- Many companies use Greenhouse boards
- Pattern: `boards.greenhouse.io/{company}/jobs`
- Clean JSON API available

### 4. Lever
- Similar to Greenhouse
- Pattern: `jobs.lever.co/{company}`
- Structured data extraction

## Data Schema

```python
class JobListing:
    id: str                  # Internal UUID
    source: str              # jobright, linkedin, greenhouse, lever
    external_id: str         # Source-specific ID
    url: str                 # Direct job URL
    company: str             # Company name
    role: str                # Job title
    location: str            # Location/Remote
    description: str         # Full job description
    skills: List[str]        # Required skills (extracted)
    salary_range: str        # If available
    posted_date: datetime    # When posted
    discovered_at: datetime  # When we found it
    status: str              # new, processed, expired
```

## Agent Architecture

```python
from langgraph.graph import StateGraph

# State definition
class JobDiscoveryState(TypedDict):
    query: str
    location: str
    sources: List[str]
    jobs: List[JobListing]
    errors: List[str]

# Graph definition
graph = StateGraph(JobDiscoveryState)
graph.add_node("jobright_scraper", scrape_jobright)
graph.add_node("linkedin_scraper", scrape_linkedin)
graph.add_node("greenhouse_scraper", scrape_greenhouse)
graph.add_node("lever_scraper", scrape_lever)
graph.add_node("normalize", normalize_jobs)
graph.add_node("deduplicate", deduplicate_jobs)
graph.add_node("store", store_jobs)
```

## Usage

```python
from src.agents.job_discovery import JobDiscoveryAgent

agent = JobDiscoveryAgent()
jobs = await agent.discover(
    query="Machine Learning Engineer",
    location="San Francisco",
    sources=["jobright", "greenhouse", "lever"]
)
```

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `MAX_JOBS_PER_SOURCE` | Limit per source | 50 |
| `SCRAPE_DELAY` | Delay between requests | 2s |
| `SKILL_EXTRACTION` | Enable skill parsing | True |

## Error Handling

- Retries with exponential backoff
- Source-specific error handling
- Graceful degradation if source fails
- All errors logged for debugging
