-- =============================================================================
-- Reconstruct team_user_daily_metrics from the agent-telemetry ClickHouse table
-- =============================================================================
--
-- Background:
--   The `team_user_daily_metrics` rollup table stopped receiving writes on
--   2024-11-25. This query rebuilds equivalent daily per-user aggregates
--   directly from the raw `agent-telemetry` event stream so the ADM / enterprise
--   team can continue reporting without asking customers to hit the
--   /teams/daily-user-metrics endpoint themselves.
--
-- Usage:
--   Replace {team_id} with the target team's ID (or use a parameterized query).
--   Adjust the date range in the WHERE clause as needed.
--
-- NOTE: The column names below are best-effort guesses based on the original
--   rollup table name and common telemetry patterns. If the actual
--   `agent-telemetry` schema differs, update the column references accordingly.
--   Run `DESCRIBE TABLE "agent-telemetry"` to confirm the schema.
-- =============================================================================

SELECT
    toDate(timestamp)                                           AS date,
    team_id,
    user_id,

    -- === Completion metrics ===
    countIf(event_type = 'completion_shown')                    AS completions_shown,
    countIf(event_type = 'completion_accepted')                 AS completions_accepted,
    countIf(event_type = 'completion_rejected')                 AS completions_rejected,

    -- acceptance rate (safe division)
    if(completions_shown > 0,
       round(completions_accepted / completions_shown, 4),
       0)                                                       AS acceptance_rate,

    -- === Chat / Composer metrics ===
    countIf(event_type = 'chat_message')                        AS chat_messages,
    countIf(event_type = 'composer_message')                    AS composer_messages,
    countIf(event_type IN ('chat_message', 'composer_message')) AS total_conversations,

    -- === Apply / edit metrics ===
    countIf(event_type = 'apply_accepted')                      AS applies_accepted,
    countIf(event_type = 'apply_rejected')                      AS applies_rejected,

    -- === Session / activity metrics ===
    uniqExact(
        toStartOfInterval(timestamp, INTERVAL 30 MINUTE)
    )                                                           AS active_half_hours,
    count()                                                     AS total_events,

    -- first and last activity timestamps for the day
    min(timestamp)                                              AS first_event_at,
    max(timestamp)                                              AS last_event_at

FROM `agent-telemetry`

WHERE
    team_id = {team_id:String}
    -- Adjust the date range as needed; default: everything since the rollup stopped
    AND toDate(timestamp) >= '2024-11-25'
    AND toDate(timestamp) <  today()

GROUP BY
    date,
    team_id,
    user_id

ORDER BY
    date  ASC,
    user_id ASC
;
