"""Generate deterministic logs, alerts, and resolutions from canonical incidents and metrics."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class EvidencePattern:
    source: str
    component: str
    codes: tuple[str, str, str, str, str]
    messages: tuple[str, str, str, str, str]
    action_type: str
    action_description: str
    action_result: str
    role: str


PATTERNS = {
    "cooling failure": EvidencePattern(
        "cooling_controller", "cooling",
        ("COOLING_BASELINE", "TEMP_HIGH", "COOL_FLOW_LOW", "COOLING_INCIDENT", "COOLING_RECOVERED"),
        (
            "Cooling telemetry baseline captured before the incident window.",
            "Rack inlet temperature warning detected for the affected rack.",
            "Cooling-flow signal degraded before service impact.",
            "Cooling-related incident opened for the affected server and rack.",
            "Cooling signals returned to the recorded operating range after resolution.",
        ),
        "cooling_system_check",
        "Inspected cooling circulation, controller state, and rack inlet conditions.",
        "Cooling-related checks completed and service was restored; the canonical incident is classified as cooling failure.",
        "facilities_engineer",
    ),
    "network outage": EvidencePattern(
        "network_switch", "network",
        ("NETWORK_BASELINE", "LATENCY_HIGH", "PACKET_LOSS_HIGH", "LINK_SERVICE_IMPACT", "LINK_RESTORED"),
        (
            "Network telemetry baseline captured before the incident window.",
            "Latency warning detected on the affected facility path.",
            "Packet-delivery degradation detected before service impact.",
            "Network service-impact event opened for the affected server.",
            "Network path returned to the recorded operating range after resolution.",
        ),
        "network_path_check",
        "Checked switch path, interface state, and facility network telemetry.",
        "Network checks completed and connectivity was restored; the canonical incident is classified as network outage.",
        "network_engineer",
    ),
    "power failure": EvidencePattern(
        "ups", "power",
        ("POWER_BASELINE", "VOLTAGE_UNSTABLE", "UPS_TRANSFER", "POWER_SERVICE_IMPACT", "POWER_RESTORED"),
        (
            "Power telemetry baseline captured before the incident window.",
            "Power-quality warning detected for the affected facility feed.",
            "UPS transfer event recorded before service impact.",
            "Power-related service-impact event opened for the affected server.",
            "Power feed returned to the recorded operating state after resolution.",
        ),
        "power_path_check",
        "Checked UPS state, distribution path, and recorded power telemetry.",
        "Power-path checks completed and service was restored; the canonical incident is classified as power failure.",
        "facilities_engineer",
    ),
    "hardware failure": EvidencePattern(
        "server_os", "hardware",
        ("HARDWARE_BASELINE", "HW_HEALTH_WARNING", "DEVICE_IO_ERROR", "SERVER_SERVICE_IMPACT", "HARDWARE_RECOVERED"),
        (
            "Server health baseline captured before the incident window.",
            "Hardware-health warning detected on the affected server.",
            "Device I/O error recorded before service impact.",
            "Hardware-related service-impact event opened for the server.",
            "Server health checks completed after service recovery.",
        ),
        "hardware_diagnostic",
        "Ran hardware diagnostics and isolated the affected server component.",
        "Hardware diagnostics completed and service was restored; the canonical incident is classified as hardware failure.",
        "hardware_technician",
    ),
    "software failure": EvidencePattern(
        "application", "application",
        ("APPLICATION_BASELINE", "APP_ERROR_RATE_HIGH", "SERVICE_UNRESPONSIVE", "APPLICATION_SERVICE_IMPACT", "APPLICATION_RECOVERED"),
        (
            "Application telemetry baseline captured before the incident window.",
            "Application error-rate warning detected on the affected server.",
            "Service health check became unresponsive before impact.",
            "Software-related service-impact event opened for the server.",
            "Application health checks passed after service recovery.",
        ),
        "application_recovery",
        "Reviewed application health, service state, and related server telemetry.",
        "Application checks completed and service was restored; the canonical incident is classified as software failure.",
        "application_engineer",
    ),
    "scheduled maintenance": EvidencePattern(
        "monitoring_agent", "maintenance",
        ("MAINT_BASELINE", "MAINT_WINDOW_NOTICE", "COMPONENT_DRAIN", "MAINT_ACTIVITY", "MAINT_COMPLETE"),
        (
            "Operational baseline captured before the scheduled maintenance window.",
            "Scheduled maintenance window notice recorded.",
            "Affected service was drained in preparation for maintenance.",
            "Scheduled maintenance activity began for the affected server.",
            "Scheduled maintenance completed and service health was verified.",
        ),
        "scheduled_maintenance",
        "Completed the recorded maintenance activity and post-maintenance health checks.",
        "Scheduled work completed and service health was verified; the canonical incident is classified as scheduled maintenance.",
        "operations_engineer",
    ),
}


def metric_context(connection: sqlite3.Connection, incident: sqlite3.Row) -> dict[str, float]:
    date = incident["start_time"][:10]
    facility = incident["facility_id"]
    server = incident["server_id"]
    power = connection.execute(
        "SELECT pue, power_draw_kw, cooling_power_kw FROM power_metrics WHERE facility_id=? AND timestamp=?",
        (facility, date),
    ).fetchone()
    network = connection.execute(
        "SELECT latency_ms, packet_loss_pct, network_availability_pct FROM network_metrics WHERE facility_id=? AND timestamp=?",
        (facility, date),
    ).fetchone()
    server_metrics = connection.execute(
        "SELECT cpu_utilization_pct, memory_utilization_pct, disk_utilization_pct FROM server_metrics WHERE server_id=? AND timestamp=?",
        (server, date),
    ).fetchone()
    values = {}
    if power:
        values.update(dict(power))
    if network:
        values.update(dict(network))
    if server_metrics:
        values.update(dict(server_metrics))
    return {key: float(value) for key, value in values.items()}


def threshold_alert(cause: str, values: dict[str, float]) -> tuple[str, float, float] | None:
    candidates = {
        "cooling failure": (("pue", 1.60, "pue_high"), ("cooling_power_kw", 2000.0, "cooling_power_high")),
        "network outage": (("latency_ms", 20.0, "latency_high"), ("packet_loss_pct", 1.0, "packet_loss_high")),
        "power failure": (("power_draw_kw", 7000.0, "power_draw_high"),),
        "hardware failure": (("disk_utilization_pct", 75.0, "disk_utilization_high"), ("cpu_utilization_pct", 85.0, "cpu_utilization_high")),
        "software failure": (("memory_utilization_pct", 85.0, "memory_utilization_high"), ("cpu_utilization_pct", 85.0, "cpu_utilization_high")),
    }.get(cause, ())
    for metric, threshold, alert_type in candidates:
        observed = values.get(metric)
        if observed is not None and observed >= threshold:
            return alert_type, observed, threshold
    return None


def build(database: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    connection = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        incidents = connection.execute(
            """SELECT i.*, s.rack_id
            FROM uptime_incidents AS i
            JOIN servers AS s ON s.server_id = i.server_id
            ORDER BY i.start_time, i.incident_id"""
        ).fetchall()
        logs, alerts, actions = [], [], []
        log_number = alert_number = action_number = 0
        for incident in incidents:
            pattern = PATTERNS[incident["root_cause"]]
            start = datetime.fromisoformat(incident["start_time"])
            end = datetime.fromisoformat(incident["end_time"])
            timestamps = (
                start - timedelta(minutes=15), start - timedelta(minutes=10),
                start - timedelta(minutes=5), start, end,
            )
            levels = (
                "INFO",
                "INFO" if incident["root_cause"] == "scheduled maintenance" else "WARNING",
                "INFO" if incident["root_cause"] == "scheduled maintenance" else "ERROR",
                "CRITICAL" if incident["severity"] == "critical" else "ERROR",
                "INFO",
            )
            values = metric_context(connection, incident)
            context_message = ", ".join(
                f"{key}={value:.3f}" for key, value in sorted(values.items())
            )
            for offset, (timestamp, level, code, message) in enumerate(
                zip(timestamps, levels, pattern.codes, pattern.messages)
            ):
                log_number += 1
                if offset == 0 and context_message:
                    message = f"{message} Observed daily context: {context_message}."
                logs.append({
                    "log_id": f"LOG-{log_number:07d}",
                    "timestamp": timestamp.isoformat(timespec="minutes"),
                    "facility_id": incident["facility_id"],
                    "server_id": incident["server_id"],
                    "rack_id": incident["rack_id"],
                    "source": pattern.source,
                    "component": pattern.component,
                    "log_level": level,
                    "event_code": code,
                    "message": message,
                })

            alert = threshold_alert(incident["root_cause"], values)
            if alert is not None:
                alert_type, observed, threshold = alert
                alert_number += 1
                alerts.append({
                    "alert_id": f"ALERT-{alert_number:06d}",
                    "timestamp": (start - timedelta(minutes=5)).isoformat(timespec="minutes"),
                    "facility_id": incident["facility_id"],
                    "server_id": incident["server_id"],
                    "component": pattern.component,
                    "severity": incident["severity"],
                    "alert_type": alert_type,
                    "metric_name": alert_type.removesuffix("_high"),
                    "observed_value": round(observed, 4),
                    "threshold_value": threshold,
                    "status": "resolved",
                    "resolved_at": end.isoformat(timespec="minutes"),
                })
            if incident["downtime_minutes"] >= 30 and incident["root_cause"] != "scheduled maintenance":
                alert_number += 1
                alert_time = min(start + timedelta(minutes=30), end)
                alerts.append({
                    "alert_id": f"ALERT-{alert_number:06d}",
                    "timestamp": alert_time.isoformat(timespec="minutes"),
                    "facility_id": incident["facility_id"],
                    "server_id": incident["server_id"],
                    "component": pattern.component,
                    "severity": incident["severity"],
                    "alert_type": "service_downtime_threshold",
                    "metric_name": "downtime_minutes",
                    "observed_value": min(float(incident["downtime_minutes"]), 30.0),
                    "threshold_value": 30.0,
                    "status": "resolved",
                    "resolved_at": end.isoformat(timespec="minutes"),
                })

            action_number += 1
            actions.append({
                "action_id": f"ACT-{action_number:06d}",
                "incident_id": incident["incident_id"],
                "facility_id": incident["facility_id"],
                "server_id": incident["server_id"],
                "timestamp": end.isoformat(timespec="minutes"),
                "action_type": pattern.action_type,
                "description": pattern.action_description,
                "result": pattern.action_result,
                "performed_by_role": pattern.role,
            })
    finally:
        connection.close()

    log_frame = pd.DataFrame(logs)
    alert_frame = pd.DataFrame(alerts)
    action_frame = pd.DataFrame(actions)
    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_incidents": len(incidents),
        "system_logs": len(log_frame),
        "alerts": len(alert_frame),
        "maintenance_actions": len(action_frame),
        "logs_per_incident": int(len(log_frame) / len(incidents)),
        "root_causes": sorted(PATTERNS),
        "rule": "Evidence is deterministically derived from canonical incident windows, confirmed root-cause categories, affected assets, and observed daily metrics.",
    }
    return log_frame, alert_frame, action_frame, audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--audit", type=Path, default=Path("evaluation/results/operational_evidence_generation.json"))
    args = parser.parse_args()
    logs, alerts, actions, audit = build(args.database)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logs.to_csv(args.output_dir / "system_logs.csv", index=False)
    alerts.to_csv(args.output_dir / "alerts.csv", index=False)
    actions.to_csv(args.output_dir / "maintenance_actions.csv", index=False)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
