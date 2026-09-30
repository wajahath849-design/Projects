CREATE OR REPLACE VIEW decision.v_decision_ledger AS
SELECT i.id AS incident_id, i.detected_at, i.metric, i.problem, i.severity,
       (SELECT COUNT(*) FROM decision.evidence e WHERE e.incident_id=i.id) AS evidence_count,
       h.description AS hypothesis, r.recommendation_type AS recommendation,
       r.confidence AS recommendation_confidence, p.status AS approval_status,
       p.approved_by, a.action_type AS action_taken, a.execution_time,
       r.expected_impact, x.percentage_impact AS actual_impact,
       x.lower AS impact_lower, x.upper AS impact_upper, o.outcome,
       l.lesson, i.closed_at,
       CASE WHEN p.status='APPROVED' THEN true
            WHEN p.status IN ('REJECTED','EXPIRED') THEN false ELSE NULL END AS approved,
       (SELECT e.dimension || '=' || e.segment FROM decision.evidence e
        WHERE e.incident_id=i.id AND e.evidence_type='CONTRIBUTION'
        ORDER BY CASE WHEN e.dimension='country_device' THEN 0 ELSE 1 END,
                 ABS(e.difference) DESC LIMIT 1) AS evidence_summary
FROM decision.incidents i
LEFT JOIN decision.hypotheses h ON h.id=i.id
LEFT JOIN decision.recommendations r ON r.incident_id=i.id
LEFT JOIN decision.approvals p ON p.recommendation_id=r.id
LEFT JOIN decision.actions a ON a.recommendation_id=r.id
LEFT JOIN decision.actual_impacts x ON x.action_id=a.id
LEFT JOIN decision.outcomes o ON o.action_id=a.id
LEFT JOIN decision.lessons l ON l.incident_id=i.id
;
