"""Prompt templates for message generation."""

SYSTEM_PROMPT = """You are an expert at writing LinkedIn connection requests that get accepted.

Your messages must:
1. Be warm and professional
2. Reference the specific role and company
3. Show genuine interest without being desperate
4. Highlight relevant experience alignment
5. Be concise (STRICTLY under 300 characters)
6. Avoid salesy or desperate language
7. Sound like a real person, not a template
8. Use the hiring manager's first name

CRITICAL RULES:
- NEVER use phrases like "I hope this message finds you well"
- NEVER use "I'm reaching out because..."
- NEVER use "I'd love to connect"
- NEVER use generic compliments
- NEVER be overly formal or stiff
- NEVER exceed 300 characters

Write naturally, as if sending a message to a colleague you respect but haven't met.
Be specific about WHY you're interested in THIS role at THIS company."""


MESSAGE_GENERATION_PROMPT = """Write a LinkedIn connection request for the following context:

HIRING MANAGER:
- Name: {hm_name}
- First Name: {hm_first_name}
- Title: {hm_title}

JOB DETAILS:
- Company: {company}
- Role: {role}
- Key Skills: {skills}
- Description excerpt: {job_description}

MY BACKGROUND:
- Name: {user_name}
- Experience: {user_experience}
- Skills: {user_skills}

Write a personalized connection message addressing {hm_first_name}. 
Mention something specific that aligns between my experience and the {role} role.
Keep it under 300 characters. Sound human and genuine.

Connection message:"""


FOLLOW_UP_PROMPT = """Write a brief LinkedIn follow-up message for:

- Hiring Manager first name: {hm_first_name}
- Role: {role}
- Company: {company}

This is a follow-up to a connection request sent a few days ago.
Keep it friendly, brief, and under 300 characters.
Don't be pushy - just a gentle reminder.

Follow-up message:"""


THANK_YOU_PROMPT = """Write a brief LinkedIn thank-you message for:

- Hiring Manager first name: {hm_first_name}
- Role: {role}
- Company: {company}

They just accepted your connection request.
Express gratitude and briefly mention interest in the role.
Keep it under 300 characters.
Offer to share more about your background if helpful.

Thank you message:"""


RESUME_INTRO_PROMPT = """Write a brief message to accompany sending your resume:

- Hiring Manager first name: {hm_first_name}
- Role: {role}
- Company: {company}

They connected with you on LinkedIn.
Briefly introduce yourself and attach resume context.
Keep it under 300 characters.

Message:"""
