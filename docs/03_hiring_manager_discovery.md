# Hiring Manager Discovery

## Overview

The Hiring Manager Discovery Agent finds relevant contacts (recruiters, hiring managers, team leads) for each job listing using search APIs.

## Discovery Strategy

### Search Queries

For each job, we construct targeted search queries:

```
site:linkedin.com "{company}" "{role}" "hiring manager"
site:linkedin.com "{company}" "recruiter" "{department}"
site:linkedin.com "{company}" "head of" "{function}"
site:linkedin.com "{company}" "director" "{function}"
```

### Relevance Scoring

Contacts are scored based on title relevance:

| Title Pattern | Score |
|--------------|-------|
| Hiring Manager for {role} | 100 |
| {Role} Manager | 90 |
| Head of {Department} | 85 |
| Director of {Department} | 80 |
| Technical Recruiter | 70 |
| Recruiter | 60 |
| HR Manager | 50 |
| Talent Acquisition | 50 |

## Data Schema

```python
class HiringManager:
    id: str                  # Internal UUID
    job_id: str              # Related job ID
    name: str                # Full name
    title: str               # Current title
    linkedin_url: str        # Profile URL
    company: str             # Current company
    relevance_score: int     # 0-100
    discovered_at: datetime
    status: str              # new, contacted, connected
```

## API Integration

### Serper API

```python
import httpx

async def search_hiring_managers(company: str, role: str) -> List[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY},
            json={
                "q": f'site:linkedin.com "{company}" "{role}" hiring manager',
                "num": 10
            }
        )
        return response.json()["organic"]
```

## Profile Parsing

From search results, we extract:
- Name from title/snippet
- Title from snippet
- LinkedIn URL from link

```python
def parse_linkedin_result(result: dict) -> HiringManager:
    # LinkedIn URL pattern: linkedin.com/in/{username}
    url = result["link"]
    
    # Extract name from title: "Name - Title - Company | LinkedIn"
    title_parts = result["title"].split(" - ")
    name = title_parts[0] if title_parts else ""
    
    # Extract title from snippet
    title = extract_title_from_snippet(result["snippet"])
    
    return HiringManager(name=name, title=title, linkedin_url=url)
```

## Usage

```python
from src.agents.hiring_manager import HiringManagerAgent

agent = HiringManagerAgent()
contacts = await agent.discover(job_id="uuid-here")
```

## Rate Limiting

- Serper API: 2,500 searches/month (free tier)
- Implement caching for repeated searches
- Batch similar queries

## Error Handling

- Handle API rate limits gracefully
- Cache results to avoid duplicate searches
- Fallback to alternative search patterns
