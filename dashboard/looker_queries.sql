-- =====================================================
-- LOOKER STUDIO DASHBOARD QUERIES
-- Connect Looker Studio to BigQuery and use these queries
-- =====================================================

-- 1. OVERVIEW METRICS (Scorecard widgets)
-- Total requests in last 7 days
SELECT
  COUNT(*) as total_requests,
  COUNT(DISTINCT user_id) as unique_users,
  COUNT(DISTINCT agent_id) as unique_agents,
  COUNTIF(has_pii = true) as pii_incidents,
  ROUND(COUNTIF(has_pii = true) * 100.0 / COUNT(*), 2) as pii_rate_percent,
  ROUND(AVG(processing_time_ms), 2) as avg_response_time_ms
FROM `ai-governance-demo-2025.ai_governance.audit_logs`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY);


-- 2. REQUESTS OVER TIME (Time series chart)
SELECT
  DATE(timestamp) as date,
  COUNT(*) as total_requests,
  COUNTIF(status = 'blocked') as blocked_requests,
  COUNTIF(status = 'passed') as passed_requests,
  COUNTIF(has_pii = true) as pii_incidents
FROM `ai-governance-demo-2025.ai_governance.audit_logs`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date;


-- 3. DEPARTMENT BREAKDOWN (Pie/Bar chart)
SELECT
  COALESCE(department, 'Unknown') as department,
  COUNT(*) as total_requests,
  COUNT(DISTINCT user_id) as unique_users,
  COUNT(DISTINCT agent_id) as agents_used,
  COUNTIF(has_pii = true) as pii_incidents,
  ROUND(COUNTIF(has_pii = true) * 100.0 / COUNT(*), 2) as pii_rate
FROM `ai-governance-demo-2025.ai_governance.audit_logs`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY department
ORDER BY total_requests DESC;


-- 4. TOP AGENTS BY USAGE (Bar chart)
SELECT
  a.agent_id,
  COALESCE(ag.agent_name, a.agent_id) as agent_name,
  COALESCE(ag.department, 'Unknown') as department,
  COUNT(*) as total_requests,
  COUNT(DISTINCT a.user_id) as unique_users,
  COUNTIF(a.has_pii = true) as pii_incidents,
  ROUND(AVG(a.processing_time_ms), 2) as avg_response_time_ms
FROM `ai-governance-demo-2025.ai_governance.audit_logs` a
LEFT JOIN `ai-governance-demo-2025.ai_governance.agents` ag ON a.agent_id = ag.agent_id
WHERE a.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY a.agent_id, ag.agent_name, ag.department
ORDER BY total_requests DESC
LIMIT 10;


-- 5. PII TYPE BREAKDOWN (Pie chart)
-- Extract PII types from metadata JSON
SELECT
  pii_type,
  COUNT(*) as occurrences
FROM `ai-governance-demo-2025.ai_governance.audit_logs`,
UNNEST(JSON_EXTRACT_ARRAY(metadata, '$.pii_types')) as pii_type
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND has_pii = true
GROUP BY pii_type
ORDER BY occurrences DESC;


-- 6. HOURLY USAGE PATTERN (Heatmap)
SELECT
  EXTRACT(DAYOFWEEK FROM timestamp) as day_of_week,
  EXTRACT(HOUR FROM timestamp) as hour_of_day,
  COUNT(*) as request_count
FROM `ai-governance-demo-2025.ai_governance.audit_logs`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY day_of_week, hour_of_day
ORDER BY day_of_week, hour_of_day;


-- 7. USER ACTIVITY (Table)
SELECT
  user_id,
  COALESCE(department, 'Unknown') as department,
  COUNT(*) as total_requests,
  COUNTIF(has_pii = true) as pii_incidents,
  COUNT(DISTINCT agent_id) as agents_used,
  MAX(timestamp) as last_activity
FROM `ai-governance-demo-2025.ai_governance.audit_logs`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND user_id IS NOT NULL
GROUP BY user_id, department
ORDER BY total_requests DESC
LIMIT 50;


-- 8. RECENT PII INCIDENTS (Table for monitoring)
SELECT
  timestamp,
  request_id,
  agent_id,
  user_id,
  department,
  JSON_EXTRACT_ARRAY(metadata, '$.pii_types') as pii_types,
  SUBSTR(original_prompt, 1, 100) as prompt_preview,
  redacted_prompt
FROM `ai-governance-demo-2025.ai_governance.audit_logs`
WHERE has_pii = true
ORDER BY timestamp DESC
LIMIT 100;


-- 9. AGENT REGISTRY (Table)
SELECT
  agent_id,
  agent_name,
  department,
  team,
  owner_email,
  environment,
  created_at,
  is_active
FROM `ai-governance-demo-2025.ai_governance.agents`
ORDER BY department, agent_name;


-- 10. RESPONSE TIME PERCENTILES (Performance monitoring)
SELECT
  DATE(timestamp) as date,
  COUNT(*) as request_count,
  APPROX_QUANTILES(processing_time_ms, 100)[OFFSET(50)] as p50_ms,
  APPROX_QUANTILES(processing_time_ms, 100)[OFFSET(90)] as p90_ms,
  APPROX_QUANTILES(processing_time_ms, 100)[OFFSET(99)] as p99_ms
FROM `ai-governance-demo-2025.ai_governance.audit_logs`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date;