"""Streamlit approval dashboard for AI Job Outreach Agent."""

import asyncio
from datetime import datetime

import streamlit as st
from sqlalchemy import func, select, update

st.set_page_config(
    page_title="AI Job Outreach - Approval Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

import sys
sys.path.insert(0, ".")

from src.core.database import get_db_context
from src.core.rate_limiter import rate_limiter
from src.models.db_models import (
    HiringManager,
    Job,
    OutreachQueue,
    OutreachStatus,
)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def get_stats():
    """Get dashboard statistics."""
    async with get_db_context() as db:
        jobs_count = await db.scalar(select(func.count(Job.id)))

        hm_count = await db.scalar(select(func.count(HiringManager.id)))

        pending_count = await db.scalar(
            select(func.count(OutreachQueue.id)).where(
                OutreachQueue.status == OutreachStatus.PENDING_APPROVAL
            )
        )

        approved_count = await db.scalar(
            select(func.count(OutreachQueue.id)).where(
                OutreachQueue.status == OutreachStatus.APPROVED
            )
        )

        sent_count = await db.scalar(
            select(func.count(OutreachQueue.id)).where(
                OutreachQueue.status == OutreachStatus.SENT
            )
        )

        accepted_count = await db.scalar(
            select(func.count(OutreachQueue.id)).where(
                OutreachQueue.status == OutreachStatus.ACCEPTED
            )
        )

    rate_status = await rate_limiter.get_status()

    return {
        "jobs_discovered": jobs_count or 0,
        "hiring_managers_found": hm_count or 0,
        "pending_approval": pending_count or 0,
        "approved": approved_count or 0,
        "sent": sent_count or 0,
        "accepted": accepted_count or 0,
        "connections_remaining": rate_status["connections_remaining"],
        "is_working_hours": rate_status["is_working_hours"],
        "is_optimal_window": rate_status.get("is_optimal_window", False),
        "is_send_time": rate_status.get("is_send_time", False),
        "next_optimal_window": rate_status.get("next_optimal_window", ""),
        "optimal_windows": rate_status.get("optimal_windows", {}),
    }


async def get_approval_queue(limit: int = 20):
    """Get pending approval queue."""
    async with get_db_context() as db:
        result = await db.execute(
            select(OutreachQueue, Job, HiringManager)
            .join(Job)
            .join(HiringManager)
            .where(OutreachQueue.status == OutreachStatus.PENDING_APPROVAL)
            .order_by(OutreachQueue.created_at.desc())
            .limit(limit)
        )
        return result.all()


async def approve_outreach(outreach_id: str, message: str = None):
    """Approve an outreach request."""
    async with get_db_context() as db:
        values = {"status": OutreachStatus.APPROVED}
        if message:
            values["message"] = message

        await db.execute(
            update(OutreachQueue)
            .where(OutreachQueue.id == outreach_id)
            .values(**values)
        )
        await db.commit()


async def reject_outreach(outreach_id: str, reason: str = None):
    """Reject an outreach request."""
    async with get_db_context() as db:
        await db.execute(
            update(OutreachQueue)
            .where(OutreachQueue.id == outreach_id)
            .values(
                status=OutreachStatus.REJECTED,
                rejection_reason=reason,
            )
        )
        await db.commit()


async def get_recent_sent(limit: int = 10):
    """Get recently sent outreach."""
    async with get_db_context() as db:
        result = await db.execute(
            select(OutreachQueue, Job, HiringManager)
            .join(Job)
            .join(HiringManager)
            .where(
                OutreachQueue.status.in_([
                    OutreachStatus.SENT,
                    OutreachStatus.ACCEPTED,
                    OutreachStatus.REPLIED,
                ])
            )
            .order_by(OutreachQueue.sent_at.desc())
            .limit(limit)
        )
        return result.all()


def main():
    """Main dashboard application."""
    st.title("🎯 AI Job Outreach Agent")
    st.markdown("---")

    with st.sidebar:
        st.header("📊 Dashboard")
        stats = run_async(get_stats())

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Jobs Found", stats["jobs_discovered"])
            st.metric("Pending", stats["pending_approval"])
            st.metric("Sent", stats["sent"])
        with col2:
            st.metric("Contacts", stats["hiring_managers_found"])
            st.metric("Approved", stats["approved"])
            st.metric("Accepted", stats["accepted"])

        st.markdown("---")
        st.subheader("⚡ Rate Limits")
        st.metric(
            "Connections Today",
            f"{20 - stats['connections_remaining']}/20"
        )

        st.markdown("---")
        st.subheader("🕐 Optimal Windows (PST)")
        
        windows = stats.get("optimal_windows", {})
        st.caption(f"Morning: {windows.get('morning', '8:00-10:00')}")
        st.caption(f"Afternoon: {windows.get('afternoon', '14:00-16:00')}")
        
        if stats.get("is_optimal_window"):
            st.success("🎯 In Optimal Window - Recruiters Active!")
        elif stats.get("is_send_time"):
            st.info("✅ Within Working Hours")
        else:
            next_window = stats.get("next_optimal_window", "")
            if next_window:
                st.warning(f"⏰ Next window: {next_window[:16]}")
            else:
                st.warning("⏰ Outside Optimal Hours")

        st.markdown("---")
        if st.button("🔄 Refresh Data"):
            st.rerun()

    tab1, tab2, tab3 = st.tabs([
        "📋 Approval Queue",
        "📤 Sent Outreach",
        "⚙️ Settings"
    ])

    with tab1:
        st.header("Pending Approval")

        queue = run_async(get_approval_queue(20))

        if not queue:
            st.info("No pending outreach to approve. Run job discovery and personalization first!")
        else:
            for outreach, job, hm in queue:
                with st.container():
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.subheader(f"🏢 {job.company} - {job.role}")
                        st.markdown(f"**Contact:** {hm.name} ({hm.title or 'N/A'})")
                        st.markdown(f"**Profile:** [{hm.linkedin_url}]({hm.linkedin_url})")
                        st.markdown(f"**Relevance Score:** {hm.relevance_score}/100")

                    with col2:
                        st.markdown(f"**Created:** {outreach.created_at.strftime('%Y-%m-%d %H:%M')}")

                    st.markdown("**Message:**")
                    edited_message = st.text_area(
                        "Edit message",
                        value=outreach.message or "",
                        key=f"msg_{outreach.id}",
                        max_chars=300,
                        label_visibility="collapsed",
                    )

                    char_count = len(edited_message)
                    if char_count > 300:
                        st.error(f"Message too long: {char_count}/300 characters")
                    else:
                        st.caption(f"{char_count}/300 characters")

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if st.button("✅ Approve", key=f"approve_{outreach.id}"):
                            run_async(approve_outreach(outreach.id, edited_message))
                            st.success("Approved!")
                            st.rerun()

                    with col2:
                        if st.button("❌ Reject", key=f"reject_{outreach.id}"):
                            run_async(reject_outreach(outreach.id))
                            st.warning("Rejected")
                            st.rerun()

                    with col3:
                        if st.button("⏭️ Skip", key=f"skip_{outreach.id}"):
                            st.info("Skipped")

                    st.markdown("---")

            st.subheader("Bulk Actions")
            col1, col2 = st.columns(2)

            with col1:
                bulk_limit = st.number_input(
                    "Approve first N items",
                    min_value=1,
                    max_value=20,
                    value=5,
                )

                if st.button("✅ Bulk Approve"):
                    approved = 0
                    for outreach, _, _ in queue[:bulk_limit]:
                        run_async(approve_outreach(outreach.id))
                        approved += 1
                    st.success(f"Approved {approved} items!")
                    st.rerun()

    with tab2:
        st.header("Recently Sent")

        sent = run_async(get_recent_sent(20))

        if not sent:
            st.info("No outreach sent yet. Approve some items first!")
        else:
            for outreach, job, hm in sent:
                with st.container():
                    status_emoji = {
                        OutreachStatus.SENT: "📤",
                        OutreachStatus.ACCEPTED: "✅",
                        OutreachStatus.REPLIED: "💬",
                    }.get(OutreachStatus(outreach.status), "❓")

                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.markdown(
                            f"{status_emoji} **{job.company}** - {job.role}"
                        )
                        st.markdown(f"To: {hm.name}")

                    with col2:
                        st.markdown(f"**Status:** {outreach.status}")
                        if outreach.sent_at:
                            st.markdown(
                                f"**Sent:** {outreach.sent_at.strftime('%Y-%m-%d %H:%M')}"
                            )

                    st.markdown("---")

    with tab3:
        st.header("Settings")

        st.subheader("🎯 Optimal Outreach Windows")
        st.markdown("""
        Connection requests are sent during peak recruiter activity:
        
        | Window | Time (PST) | Why |
        |--------|------------|-----|
        | **Morning Rush** | 8:00 AM - 10:00 AM | Recruiters check messages & review applicants |
        | **Afternoon Boost** | 2:00 PM - 4:00 PM | Final check before end of day |
        
        *Sending during these windows increases acceptance rates.*
        """)

        st.subheader("⚡ Rate Limiting")
        st.markdown("""
        Current safety settings:
        - **Max connections per day:** 20
        - **Delay between actions:** 45-120 seconds
        - **Typing delay:** 50-150ms per character (human-like)
        - **Random mouse movements:** Enabled
        """)

        st.warning(
            "⚠️ These settings are configured in `.env` for safety. "
            "Modifying them may risk your LinkedIn account."
        )

        st.subheader("📝 User Profile")
        st.info(
            "Configure your user profile in the database to enable "
            "better message personalization."
        )


if __name__ == "__main__":
    main()
