# Safety Mechanisms

## Overview

LinkedIn actively detects and bans automated activity. This document outlines all safety measures implemented to protect your account.

## Rate Limiting

### Daily Limits

```python
DAILY_LIMITS = {
    "connections": 20,      # Connection requests per day
    "profile_views": 100,   # Profile views per day
    "messages": 50,         # Messages per day (if InMail)
    "searches": 200         # Searches per day
}
```

### Implementation

```python
class RateLimiter:
    def __init__(self):
        self.redis = Redis()  # Or in-memory dict
        
    async def check_limit(self, action: str) -> bool:
        key = f"limit:{action}:{today()}"
        current = await self.redis.get(key) or 0
        
        if current >= DAILY_LIMITS[action]:
            return False
            
        await self.redis.incr(key)
        await self.redis.expire(key, 86400)  # 24 hours
        return True
```

## Timing Controls

### Optimal Outreach Windows (Recruiter Activity-Based)

Research shows recruiters and hiring managers are most active during:

| Window | Time (PST) | Why |
|--------|------------|-----|
| Morning Rush | 8 AM - 10 AM | Checking messages, reviewing applicants as they start day |
| Afternoon Boost | 2 PM - 4 PM | Final check before concluding their day |

```python
from datetime import datetime
import pytz

def is_optimal_window() -> bool:
    """Check if current time is when recruiters are most active."""
    tz = pytz.timezone("America/Los_Angeles")
    now = datetime.now(tz)
    
    # Weekday check
    if now.weekday() >= 5:  # Saturday, Sunday
        return False
    
    # Morning Rush: 8 AM - 10 AM
    in_morning = 8 <= now.hour < 10
    
    # Afternoon Boost: 2 PM - 4 PM
    in_afternoon = 14 <= now.hour < 16
    
    return in_morning or in_afternoon
```

### Why Optimal Windows Matter

- **Higher visibility**: Your connection request appears at the top when they're actively checking
- **Faster response**: Recruiters are more likely to accept immediately
- **Mimics real behavior**: Job seekers typically reach out during business hours
- **Avoids off-hours spam signals**: Late night/early morning messages look automated

### Random Delays

```python
import random
import asyncio

async def random_delay(min_sec: int = 45, max_sec: int = 120):
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)
```

### Daily Schedule Variation

```python
def get_todays_schedule() -> List[datetime]:
    """Generate random execution times for today."""
    times = []
    current = datetime.now().replace(hour=9, minute=0)
    end = datetime.now().replace(hour=18, minute=0)
    
    while current < end and len(times) < MAX_CONNECTIONS_PER_DAY:
        # Add random offset
        offset = random.randint(30, 90)  # minutes
        current += timedelta(minutes=offset)
        
        if current < end:
            times.append(current)
    
    return times
```

## Human-Like Behavior

### Mouse Movements

```python
async def human_mouse_move(page, target_element):
    # Get element position
    box = await target_element.bounding_box()
    target_x = box['x'] + box['width'] / 2
    target_y = box['y'] + box['height'] / 2
    
    # Current position
    current = await page.evaluate("({x: window.mouseX, y: window.mouseY})")
    
    # Move in small increments with slight randomness
    steps = random.randint(10, 20)
    for i in range(steps):
        progress = (i + 1) / steps
        x = current['x'] + (target_x - current['x']) * progress
        y = current['y'] + (target_y - current['y']) * progress
        
        # Add slight wobble
        x += random.uniform(-3, 3)
        y += random.uniform(-3, 3)
        
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.01, 0.03))
```

### Typing Patterns

```python
async def human_type(element, text: str):
    for i, char in enumerate(text):
        # Base delay
        delay = random.randint(50, 150)
        
        # Longer pause after punctuation
        if char in '.!?,':
            delay += random.randint(100, 300)
        
        # Occasional typo and correction (very rare)
        if random.random() < 0.02:
            typo = random.choice('qwertyuiop')
            await element.type(typo, delay=delay)
            await asyncio.sleep(0.1)
            await element.press('Backspace')
        
        await element.type(char, delay=delay)
```

### Scrolling Behavior

```python
async def natural_scroll(page):
    # Scroll in chunks with pauses
    scroll_times = random.randint(2, 4)
    
    for _ in range(scroll_times):
        amount = random.randint(100, 300)
        await page.evaluate(f"""
            window.scrollBy({{
                top: {amount},
                behavior: 'smooth'
            }})
        """)
        await asyncio.sleep(random.uniform(0.5, 1.5))
```

## Session Management

### Persistent Browser Context

```python
BROWSER_DATA_DIR = "./browser_data"

async def get_persistent_context():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch_persistent_context(
        BROWSER_DATA_DIR,
        headless=False,
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...'
    )
    return browser
```

### Session Health Check

```python
async def is_session_valid(page) -> bool:
    await page.goto("https://www.linkedin.com/feed/")
    
    # Check if redirected to login
    if "login" in page.url:
        return False
    
    # Check for security challenge
    if "checkpoint" in page.url:
        logging.warning("Security checkpoint detected!")
        return False
        
    return True
```

## Circuit Breaker

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=3600):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure = None
        self.state = "closed"  # closed, open, half-open
    
    def record_failure(self):
        self.failures += 1
        self.last_failure = datetime.now()
        
        if self.failures >= self.threshold:
            self.state = "open"
            logging.critical("Circuit breaker OPEN - stopping all operations")
    
    def can_proceed(self) -> bool:
        if self.state == "closed":
            return True
            
        if self.state == "open":
            # Check if reset timeout passed
            if (datetime.now() - self.last_failure).seconds > self.reset_timeout:
                self.state = "half-open"
                return True
            return False
            
        return True  # half-open allows one request
```

## Monitoring & Alerts

```python
async def monitor_account_health():
    """Check for warning signs of account issues."""
    
    indicators = {
        "connection_success_rate": calculate_success_rate(),
        "daily_limit_reached": check_daily_limit(),
        "security_challenges": count_security_challenges(),
        "profile_restrictions": check_restrictions()
    }
    
    if indicators["security_challenges"] > 0:
        await alert("CRITICAL: Security challenge detected")
        await circuit_breaker.trip()
    
    if indicators["connection_success_rate"] < 0.5:
        await alert("WARNING: Low connection success rate")
```

## Best Practices

1. **Start Slow**: Begin with 5 connections/day, increase gradually
2. **Use Real Account Data**: Complete profile, connections, activity
3. **Manual Activity**: Mix in manual browsing sessions
4. **Monitor Closely**: Watch for any warnings or restrictions
5. **Backup Account**: Use secondary account for testing
6. **Respect Limits**: Never override safety limits
