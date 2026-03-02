# LinkedIn Automation

## Overview

The LinkedIn Execution Agent uses Playwright for browser automation to send connection requests while mimicking human behavior.

## Safety First

**This is the most sensitive component.** LinkedIn actively detects automation and will ban accounts. All safety measures are mandatory.

## Safety Mechanisms

### Rate Limiting
```python
MAX_CONNECTIONS_PER_DAY = 20  # Never exceed this
CURRENT_DAILY_COUNT = 0       # Reset at midnight
```

### Timing Simulation
```python
# Random delays between actions
MIN_DELAY = 45   # seconds
MAX_DELAY = 120  # seconds

# Human-like typing
TYPING_DELAY_MIN = 50   # ms
TYPING_DELAY_MAX = 150  # ms
```

### Working Hours
```python
WORKING_HOURS_START = 9   # 9 AM
WORKING_HOURS_END = 18    # 6 PM
TIMEZONE = "America/Los_Angeles"
```

### Session Management
- Persist browser context between sessions
- Avoid repeated logins (triggers security)
- Use same browser fingerprint

## Browser Actions

### Connection Request Flow

```python
async def send_connection(page, profile_url: str, message: str):
    # 1. Navigate to profile
    await page.goto(profile_url)
    await random_delay(2, 5)  # Simulate reading
    
    # 2. Scroll down naturally
    await human_scroll(page)
    await random_delay(1, 3)
    
    # 3. Click Connect button
    connect_btn = await page.wait_for_selector(
        'button:has-text("Connect")'
    )
    await connect_btn.click()
    await random_delay(0.5, 1.5)
    
    # 4. Click "Add a note"
    add_note = await page.wait_for_selector(
        'button:has-text("Add a note")'
    )
    await add_note.click()
    await random_delay(0.5, 1)
    
    # 5. Type message with human delays
    textarea = await page.wait_for_selector('textarea')
    await human_type(textarea, message)
    await random_delay(1, 2)
    
    # 6. Send
    send_btn = await page.wait_for_selector(
        'button:has-text("Send")'
    )
    await send_btn.click()
    
    return True
```

### Human-Like Typing

```python
async def human_type(element, text: str):
    for char in text:
        await element.type(char, delay=random.randint(50, 150))
        
        # Occasional longer pause (thinking)
        if random.random() < 0.1:
            await asyncio.sleep(random.uniform(0.3, 0.8))
```

### Human-Like Scrolling

```python
async def human_scroll(page):
    scroll_amount = random.randint(200, 400)
    await page.evaluate(f"""
        window.scrollBy({{
            top: {scroll_amount},
            behavior: 'smooth'
        }})
    """)
```

## Session Persistence

```python
from playwright.async_api import async_playwright

async def get_browser_context():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    
    # Load existing session if available
    context = await browser.new_context(
        storage_state="linkedin_session.json"
    )
    
    return context
```

## Error Handling

### Common Errors

| Error | Cause | Action |
|-------|-------|--------|
| Connection limit reached | Weekly limit hit | Stop for week |
| Profile not found | Invalid URL | Skip, log error |
| Not logged in | Session expired | Re-authenticate |
| Rate limited | Too many actions | Exponential backoff |
| Security check | Suspicious activity | Stop, manual review |

### Recovery Strategy

```python
async def safe_execute(action, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await action()
        except RateLimitError:
            await exponential_backoff(attempt)
        except SecurityCheckError:
            logging.critical("Security check detected - stopping")
            raise
```

## Logging

All actions logged for audit:
```python
{
    "timestamp": "2024-01-15T10:30:00Z",
    "action": "send_connection",
    "profile_url": "linkedin.com/in/...",
    "status": "success",
    "message_preview": "Hi Sarah...",
    "execution_time_ms": 8500
}
```
