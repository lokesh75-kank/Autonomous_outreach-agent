# AI Personalization Engine

## Overview

The Personalization Engine uses OpenAI GPT-4 to generate unique, contextual LinkedIn connection messages that avoid detection and maximize response rates.

## Message Requirements

### LinkedIn Constraints
- Maximum 300 characters for connection note
- No links in free connection requests
- Must feel personal and authentic

### Quality Guidelines
- Reference specific job details
- Mention relevant experience
- Avoid generic phrases
- Sound human, not templated

## Prompt Engineering

### System Prompt

```
You are an expert at writing LinkedIn connection requests that get accepted.

Your messages must:
1. Be warm and professional
2. Reference the specific role and company
3. Show genuine interest
4. Highlight relevant experience alignment
5. Be concise (under 300 characters)
6. Avoid salesy or desperate language
7. Sound like a real person, not a template

Never use:
- "I hope this message finds you well"
- "I'm reaching out because..."
- "I'd love to connect"
- Generic compliments
- Excessive enthusiasm
```

### Message Template

```
Context:
- Job: {role} at {company}
- Hiring Manager: {hm_name}, {hm_title}
- Key Skills Required: {skills}
- User Background: {user_summary}
- User's Relevant Experience: {relevant_experience}

Write a LinkedIn connection request (max 300 chars) that:
1. Addresses {hm_name} by first name
2. References the {role} position
3. Mentions a specific skill alignment
4. Feels authentic and personalized
```

## Message Variation

To avoid detection, each message is unique:

1. **Temperature**: Use 0.8-1.0 for variation
2. **Multiple generations**: Generate 3 options, pick best
3. **Style rotation**: Rotate between approaches
4. **Dynamic elements**: Company research, recent news

### Example Outputs

**For ML Engineer at Waymo:**
```
Hi Sarah — saw you're hiring for Applied ML at Waymo. My recent work on 
production ML monitoring for safety-critical systems closely aligns 
with the challenges in the posting. Would love to connect!
```

**For Data Scientist at Stripe:**
```
Hi Michael — noticed the Data Science role on your team. I've spent 
3 years building fraud detection models at scale, which seems 
relevant to Stripe's challenges. Happy to share more!
```

## Implementation

```python
from openai import AsyncOpenAI

class PersonalizationEngine:
    def __init__(self):
        self.client = AsyncOpenAI()
        
    async def generate_message(
        self,
        job: JobListing,
        hiring_manager: HiringManager,
        user_profile: UserProfile
    ) -> str:
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_prompt(
                    job, hiring_manager, user_profile
                )}
            ],
            temperature=0.9,
            max_tokens=150
        )
        
        message = response.choices[0].message.content
        return self._validate_message(message)
```

## Quality Checks

Before queuing a message:
1. Verify under 300 characters
2. Check for banned phrases
3. Ensure personalization tokens replaced
4. Validate tone (not too formal/casual)

## Usage

```python
from src.agents.personalization import PersonalizationEngine

engine = PersonalizationEngine()
message = await engine.generate(
    job_id="uuid",
    hiring_manager_id="uuid"
)
```
