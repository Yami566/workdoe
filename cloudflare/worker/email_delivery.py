from __future__ import annotations

# These predicates are shared by bounded fanout and individual delivery reads.
OPEN_PROJECT = """
    jobs.status = 'open'
    AND clients.role = 'client' AND clients.status = 'active'
    AND NOT EXISTS (
        SELECT 1 FROM match_requests AS approved_request
        WHERE approved_request.job_id = jobs.id AND approved_request.status = 'approved'
    )
"""
OPEN_BID_WINDOW = """
    AND datetime(jobs.bidding_closes_at) > datetime('now')
    AND (
        SELECT COUNT(*) FROM match_requests WHERE match_requests.job_id = jobs.id
    ) < jobs.bid_limit
"""
LEAD_FIT = """
    AND contractor_lead_preferences.saved_at IS NOT NULL
    AND contractor_lead_preferences.lead_alert_preference = 'email'
    AND contractor_lead_preferences.lead_alert_consent_at IS NOT NULL
    AND contractor_lead_preferences.availability_status != 'unavailable'
    AND (contractor_lead_preferences.saved_category = ''
         OR contractor_lead_preferences.saved_category = jobs.category)
    AND (contractor_lead_preferences.saved_service_group_slug = ''
         OR contractor_lead_preferences.saved_service_group_slug = jobs.service_group_slug)
    AND (contractor_lead_preferences.saved_service_slug = ''
         OR contractor_lead_preferences.saved_service_slug = jobs.service_slug)
    AND (contractor_lead_preferences.saved_query = ''
         OR instr(lower(jobs.title || ' ' || jobs.category || ' ' || jobs.city || ' ' || jobs.state),
                  lower(contractor_lead_preferences.saved_query)) > 0)
    AND EXISTS (
        SELECT 1 FROM contractor_service_capabilities
        WHERE contractor_service_capabilities.contractor_id = users.id
          AND contractor_service_capabilities.service_slug = jobs.service_slug
    )
    AND EXISTS (
        SELECT 1 FROM contractor_service_zones
        WHERE contractor_service_zones.contractor_id = users.id
          AND contractor_service_zones.zone_slug = jobs.service_zone_slug
    )
    AND NOT EXISTS (
        SELECT 1 FROM match_requests
        WHERE match_requests.job_id = jobs.id AND match_requests.contractor_id = users.id
    )
"""


def lead_alert_candidates_query(*, delivery: bool = False) -> str:
    target = "contractor_lead_alert_deliveries.id = ?" if delivery else "jobs.id = ?"
    state = (
        "contractor_lead_alert_deliveries.status IN ('pending', 'queued', 'failed')"
        if delivery else
        "(contractor_lead_alert_deliveries.id IS NULL "
        "OR contractor_lead_alert_deliveries.status IN ('pending', 'failed'))"
    )
    order_limit = "ORDER BY users.id LIMIT 1" if delivery else "ORDER BY users.id LIMIT 50"
    # Compose only fixed clauses; all resource identities stay bound.
    clauses = ("""
        SELECT jobs.id AS job_id, jobs.title AS job_title, jobs.category, jobs.service_slug,
               jobs.city, jobs.state, users.id AS contractor_id,
               users.email AS contractor_email, users.email AS recipient_email,
               contractor_lead_alert_deliveries.id AS delivery_id,
               contractor_lead_alert_deliveries.status AS delivery_status
        FROM jobs
        JOIN users AS clients ON clients.id = jobs.client_id
        JOIN users ON users.role = 'contractor' AND users.status = 'active' AND users.email_verified = 1
        JOIN contractor_lead_preferences ON contractor_lead_preferences.contractor_id = users.id
        LEFT JOIN contractor_lead_alert_deliveries
          ON contractor_lead_alert_deliveries.contractor_id = users.id
         AND contractor_lead_alert_deliveries.job_id = jobs.id
    """, "WHERE", target, "AND", OPEN_PROJECT, OPEN_BID_WINDOW, LEAD_FIT, "AND", state, order_limit)
    return "\n".join(clauses)


def positive_reference(value: object) -> bool:
    return type(value) is int and 0 < value <= 9_223_372_036_854_775_807


def marketplace_email_delivery_query(body: dict) -> tuple[str, tuple[int, ...]] | None:
    kind = body.get("type")
    if kind == "contractor-new-lead":
        identity = body.get("lead_alert_delivery_id")
        return (lead_alert_candidates_query(delivery=True), (identity,)) if positive_reference(identity) else None
    if kind == "stale-match-reminder":
        identity = body.get("match_request_id")
        if not positive_reference(identity):
            return None
        clauses = ("""
            SELECT jobs.id AS job_id, jobs.title AS job_title, jobs.city, jobs.state,
                   clients.email AS recipient_email, contractors.display_name AS contractor_name
            FROM match_requests
            JOIN jobs ON jobs.id = match_requests.job_id
            JOIN users AS clients ON clients.id = jobs.client_id
            JOIN client_profiles ON client_profiles.user_id = clients.id
            JOIN users AS contractors ON contractors.id = match_requests.contractor_id
            WHERE match_requests.id = ? AND match_requests.status = 'pending'
              AND
        """, OPEN_PROJECT, """
              AND clients.email_verified = 1
              AND contractors.role = 'contractor' AND contractors.status = 'active'
              AND client_profiles.notification_preference = 'email'
              AND client_profiles.email_reminder_consent_at IS NOT NULL
            LIMIT 1
        """)
        return "\n".join(clauses), (identity,)
    if kind == "repeat-provider-invitation":
        contractor_id, job_id = body.get("contractor_id"), body.get("job_id")
        if not positive_reference(contractor_id) or not positive_reference(job_id):
            return None
        clauses = ("""
            SELECT jobs.id AS job_id, jobs.title AS job_title, jobs.city, jobs.state,
                   contractors.email AS recipient_email
            FROM repeat_provider_invitations AS invitation
            JOIN jobs ON jobs.id = invitation.job_id AND jobs.client_id = invitation.client_id
            JOIN users AS clients ON clients.id = jobs.client_id
            JOIN users AS contractors ON contractors.id = invitation.contractor_id
            WHERE invitation.job_id = ? AND invitation.contractor_id = ? AND invitation.status = 'pending'
              AND
        """, OPEN_PROJECT, OPEN_BID_WINDOW, """
              AND contractors.role = 'contractor' AND contractors.status = 'active'
              AND contractors.email_verified = 1
              AND NOT EXISTS (
                  SELECT 1 FROM match_requests
                  WHERE match_requests.job_id = jobs.id AND match_requests.contractor_id = contractors.id
              )
            LIMIT 1
        """)
        return "\n".join(clauses), (job_id, contractor_id)
    return None
