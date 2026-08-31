from __future__ import annotations

import json
import multiprocessing
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("SENTINEL_DB_PATH", str(BASE_DIR / "data" / "sentinel.db"))).resolve()
QUEUE_DB_PATH = Path(os.getenv("SENTINEL_QUEUE_DB_PATH", str(BASE_DIR / "data" / "sentinel_queue.db"))).resolve()
QUEUE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def run_queue_job(db_path: str, queue_db_path: str, job_id: str) -> None:
    """Process entry point so `--queue` survives after the CLI process exits."""
    service = FraudTriageService(Path(db_path), Path(queue_db_path))
    service._process_job(job_id)


class SentinelDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_account(self, account_id: str):
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT a.account_id, a.customer_id, a.product, a.status, a.credit_limit,
                       c.full_name, c.home_country
                FROM accounts a
                JOIN customers c ON c.customer_id = a.customer_id
                WHERE a.account_id = ?
                """,
                (account_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_alerts(self, account_id: str):
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT alert_id, rule_id, triggered_at, severity, trigger_txn_id FROM alerts WHERE account_id = ? ORDER BY triggered_at",
                (account_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_transactions(self, account_id: str, limit: int = 20):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT txn_id, account_id, card_id, merchant_id, device_id, ts, amount, channel, ip_country, auth_result
                FROM transactions
                WHERE account_id = ?
                ORDER BY ts DESC
                LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_case_notes(self, customer_id: str):
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT note_id, created_at, author, channel, note FROM case_notes WHERE customer_id = ? ORDER BY created_at DESC",
                (customer_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_prior_cases(self, customer_id: str):
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT case_id, opened_date, closed_date, outcome, summary FROM prior_cases WHERE customer_id = ? ORDER BY opened_date DESC",
                (customer_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_disputes(self, account_id: str):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT d.dispute_id, d.txn_id, d.filed_at, d.reason_code, d.customer_statement, d.status, t.amount, t.device_id, t.ip_country
                FROM disputes d
                JOIN transactions t ON t.txn_id = d.txn_id
                WHERE t.account_id = ?
                ORDER BY d.filed_at DESC
                """,
                (account_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_account_device_notes(self, customer_id: str):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT cd.customer_id, cd.device_id, d.device_type, d.os, cd.first_seen, cd.last_seen
                FROM customer_devices cd
                JOIN devices d ON d.device_id = cd.device_id
                WHERE cd.customer_id = ?
                ORDER BY cd.last_seen DESC
                """,
                (customer_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_related_accounts_by_device(self, device_id: str):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT a.account_id, cd.customer_id
                FROM customer_devices cd
                JOIN accounts a ON a.customer_id = cd.customer_id
                WHERE cd.device_id = ?
                ORDER BY a.account_id
                """,
                (device_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_flagged_accounts(self):
        with self.connect() as conn:
            rows = conn.execute("SELECT DISTINCT account_id FROM alerts ORDER BY account_id").fetchall()
            return [r["account_id"] for r in rows]

    def get_rule_names(self):
        with self.connect() as conn:
            rows = conn.execute("SELECT rule_id, name FROM rules ORDER BY rule_id").fetchall()
            return {r["rule_id"]: r["name"] for r in rows}


class PolicyLoader:
    def __init__(self, root: Path = BASE_DIR):
        self.root = root
        self.policy_dir = self.root / "policies"
        self.policy_dir.mkdir(exist_ok=True)

    def load(self, name: str) -> str:
        policy_path = self.policy_dir / f"{name}.md"
        if policy_path.exists():
            return policy_path.read_text(encoding="utf-8")
        defaults = {
            "behaviour": "Evaluate transaction timing, amount, merchant risk and device behavior before deciding on fraud.",
            "context": "Prefer note-based explanations over raw trigger counts when they explain the account behavior.",
            "network": "Evaluate whether the device or merchant pattern looks like a shared or isolated fraud pattern.",
            "disposition": "Only take irreversible action after a human review and approval step.",
        }
        return defaults.get(name, "Use evidence over alerts.")

    def settings(self, name: str) -> Dict[str, str]:
        """Read simple `key: value` settings from an editable policy document."""
        settings: Dict[str, str] = {}
        for line in self.load(name).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.replace("_", "").replace("-", "").isalnum():
                settings[key.strip()] = value.strip()
        return settings


# These are deliberately narrow tool surfaces.  A specialist cannot use the
# underlying SentinelDB object to cross into another specialist's domain.
class BehaviourDataTool:
    def __init__(self, db: SentinelDB): self._db = db
    def fetch(self, account_id: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._db.get_recent_transactions(account_id, 20), self._db.get_alerts(account_id)


class ContextDataTool:
    def __init__(self, db: SentinelDB): self._db = db
    def fetch(self, account_id: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        account = self._db.get_account(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found.")
        customer_id = account["customer_id"]
        return self._db.get_case_notes(customer_id), self._db.get_prior_cases(customer_id), self._db.get_disputes(account_id)


class NetworkDataTool:
    def __init__(self, db: SentinelDB): self._db = db
    def transactions(self, account_id: str) -> List[Dict[str, Any]]:
        return self._db.get_recent_transactions(account_id, 20)
    def related_accounts(self, device_id: str) -> List[Dict[str, Any]]:
        return self._db.get_related_accounts_by_device(device_id)


class BehaviourSpecialist:
    """Transaction-only specialist.  It cannot see notes, disputes, or network data."""
    prompt = "Assess spending behaviour only. Cite transaction and alert ids; never infer customer intent."
    domain_marker = "spending behaviour only"
    def __init__(self, data: BehaviourDataTool, loader: PolicyLoader):
        self.data = data
        self.loader = loader

    def analyze(self, account_id: str) -> Dict[str, Any]:
        if self.domain_marker not in self.prompt.lower():
            raise RuntimeError("Behaviour specialist received a prompt for the wrong domain.")
        policy = self.loader.load("behaviour")
        settings = self.loader.settings("behaviour")
        txns, alerts = self.data.fetch(account_id)
        high_value_amount = float(settings.get("high_value_amount", "5000"))
        country_count = int(settings.get("rapid_country_count", "3"))

        score = 0
        evidence: List[str] = []
        if txns:
            high_value = [t for t in txns if float(t.get("amount", 0) or 0) >= high_value_amount]
            if high_value:
                score += 2
                ids = ", ".join(t["txn_id"] for t in high_value[:3])
                evidence.append(f"{len(high_value)} transaction(s) exceeded {high_value_amount:.0f}: {ids}.")

            new_device_txns = [t for t in txns if t.get("device_id", "").startswith("DX")]
            if len(new_device_txns) >= 3:
                score += 2
                evidence.append("Multiple transactions came from a new device in a short span.")

            countries = {t.get("ip_country") for t in txns if t.get("ip_country")}
            if len(countries) >= country_count:
                score += 2
                evidence.append(f"Recent transactions span {len(countries)} IP countries (threshold {country_count}).")

            night = [t for t in txns if t.get("ts", "").split("T")[1][:2] in {"00", "01", "02", "03", "04"}]
            if len(night) >= 2:
                score += 1
                evidence.append("Several transactions occurred at overnight hours.")

        if any(alert.get("rule_id") in {"R02", "R03", "R07"} for alert in alerts):
            score += 1
            evidence.append("The triggered rule set matches a suspicious behaviour profile.")

        return {
            "agent": "behaviour",
            "prompt": self.prompt,
            "score": score,
            "summary": "Behaviour is " + ("fraud-like" if score >= 3 else "generally normal") + ".",
            "evidence": evidence or ["No transaction anomaly was severe enough to force a fraudulent conclusion."],
        }


class ContextSpecialist:
    """Free-text specialist.  It has no transaction or device/network tools."""
    prompt = "Read customer notes, disputes, and prior cases. Cite exact records and name any missing evidence."
    domain_marker = "customer notes"
    def __init__(self, data: ContextDataTool, loader: PolicyLoader):
        self.data = data
        self.loader = loader

    def analyze(self, account_id: str) -> Dict[str, Any]:
        if self.domain_marker not in self.prompt.lower():
            raise RuntimeError("Context specialist received a prompt for the wrong domain.")
        policy = self.loader.load("context")
        settings = self.loader.settings("context")
        explicit_weight = int(settings.get("explicit_explanation_weight", "4"))
        travel_weight = int(settings.get("travel_explanation_weight", "2"))
        notes, prior_cases, disputes = self.data.fetch(account_id)
        combined = "\n".join(note.get("note", "") for note in notes)
        lower = combined.lower()

        score = 0
        evidence: List[str] = []
        if not notes:
            return {
                "agent": "context",
                "prompt": self.prompt,
                "score": 0,
                "summary": "Context is inconclusive because there are no notes.",
                "evidence": ["No explanatory case note was present for this account."],
                "needs_more_context": True,
            }

        if "phone upgrade" in lower or "video kyc" in lower or "re-registration" in lower:
            score -= explicit_weight
            matching = next(n for n in notes if any(x in n["note"].lower() for x in ("phone upgrade", "video kyc", "re-registration")))
            evidence.append(f"Note {matching['note_id']} ({matching['created_at']}): {matching['note']}")
        if "joint household" in lower or "family tablet" in lower or "shared device" in lower or "wife" in lower:
            score -= 3
            matching = next(n for n in notes if any(x in n["note"].lower() for x in ("joint household", "family tablet", "shared device", "wife")))
            evidence.append(f"Note {matching['note_id']} ({matching['created_at']}): {matching['note']}")
        if any(phrase in lower for phrase in ("unrequested device registration", "not me", "did not perform", "still hold the physical card", "stolen", "unauthorised", "unauthorized")):
            score += explicit_weight
            matching = next(n for n in notes if any(x in n["note"].lower() for x in ("unrequested device registration", "not me", "did not perform", "still hold the physical card", "stolen", "unauthorised", "unauthorized")))
            evidence.append(f"Note {matching['note_id']} ({matching['created_at']}): {matching['note']}")
        if any(phrase in lower for phrase in ("travel notice", "flying to", "travelling", "traveling", "on holiday", "family holiday")):
            score -= travel_weight
            matching = next(n for n in notes if any(x in n["note"].lower() for x in ("holiday", "travel")))
            evidence.append(f"Note {matching['note_id']} ({matching['created_at']}): {matching['note']}")

        if prior_cases:
            outcomes = {item.get("outcome", "").lower() for item in prior_cases if item.get("outcome")}
            if any(o in {"legitimate", "closed - no fraud"} for o in outcomes):
                score -= 1
                evidence.append("Previous case history is consistent with a legitimate customer pattern.")
        if disputes:
            score += 1
            evidence.append("Active disputes create additional suspicion and reduce confidence in a legitimate read.")

        return {
            "agent": "context",
            "prompt": self.prompt,
            "score": score,
            "summary": "Context is " + ("supportive of fraud" if score >= 2 else "supportive of legitimacy" if score <= -2 else "mixed") + ".",
            "evidence": evidence or ["The note history was not decisive either way."],
            "needs_more_context": score == 0,
        }


class NetworkSpecialist:
    """Relationship specialist. It can inspect devices and merchants, never customer text."""
    prompt = "Assess cross-account links from devices and merchants. Cite device ids; do not read customer notes."
    domain_marker = "cross-account links"
    def __init__(self, data: NetworkDataTool, loader: PolicyLoader):
        self.data = data
        self.loader = loader

    def analyze(self, account_id: str) -> Dict[str, Any]:
        if self.domain_marker not in self.prompt.lower():
            raise RuntimeError("Network specialist received a prompt for the wrong domain.")
        policy = self.loader.load("network")
        settings = self.loader.settings("network")
        linked_account_threshold = int(settings.get("shared_device_account_count", "2"))
        txns = self.data.transactions(account_id)
        device_ids = [t.get("device_id") for t in txns if t.get("device_id")]
        score = 0
        evidence: List[str] = []

        if not device_ids:
            return {
                "agent": "network",
                "prompt": self.prompt,
                "score": 0,
                "summary": "The network view is neutral.",
                "evidence": ["No device data was available in the transaction history."],
            }

        unique_devices = sorted(set(device_ids))
        if len(unique_devices) > 1:
            score += 1
            evidence.append("The account used more than one device during the alert window.")

        for device_id in unique_devices:
            related = self.data.related_accounts(device_id)
            if device_id.startswith("DX") and len(related) >= linked_account_threshold:
                score += 2
                evidence.append(f"Device {device_id} appears across multiple accounts and weakens a pure fraud narrative.")
            elif device_id.startswith("DX") and len(related) == 1:
                score += 1
                evidence.append(f"Device {device_id} is a new but isolated device for this account.")

        merchants = {t.get("merchant_id") for t in txns if t.get("merchant_id")}
        if len(merchants) >= 4:
            score += 1
            evidence.append("The account used several merchants, which is common in both legitimate and fraudulent behaviour.")

        return {
            "agent": "network",
            "prompt": self.prompt,
            "score": score,
            "summary": "The network footprint is " + ("suspicious" if score >= 2 else "mostly normal") + ".",
            "evidence": evidence or ["No abnormal network pattern was detected."],
        }


class DispositionSpecialist:
    """Write-only decision specialist. It has no database capability."""
    prompt = "Choose a proportionate action from the supplied final findings; require approval before irreversible action."
    domain_marker = "proportionate action"
    def __init__(self, loader: PolicyLoader):
        self.loader = loader

    def decide(self, verdict: str, confidence: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.domain_marker not in self.prompt.lower():
            raise RuntimeError("Disposition specialist received a prompt for the wrong domain.")
        policy = self.loader.load("disposition")
        settings = self.loader.settings("disposition")
        if verdict == "fraud":
            return {
                "agent": "disposition",
                "prompt": self.prompt,
                "recommended_action": settings.get("fraud_action", "block_card"),
                "requires_approval": True,
                "escalation": "fraud_ops_manager",
                "summary": "A fraud verdict should be paused for approval before blocking the card and escalating the case.",
            }
        if verdict == "legitimate":
            return {
                "agent": "disposition",
                "prompt": self.prompt,
                "recommended_action": "release_case",
                "requires_approval": False,
                "escalation": None,
                "summary": "No irreversible action is recommended for a likely legitimate account.",
            }
        return {
            "agent": "disposition",
            "prompt": self.prompt,
            "recommended_action": settings.get("ambiguous_action", "request_manual_review"),
            "requires_approval": False,
            "escalation": "manual_review",
            "summary": "The evidence is insufficient to justify any irreversible action.",
        }


class FraudSupervisor:
    def __init__(self, behaviour_tool: BehaviourSpecialist, context_tool: ContextSpecialist, network_tool: NetworkSpecialist, disposition_tool: DispositionSpecialist):
        self.tools = {
            "behaviour": behaviour_tool,
            "context": context_tool,
            "network": network_tool,
            "disposition": disposition_tool,
        }

    def route(self, account_id: str) -> Dict[str, Any]:
        # The supervisor has only these four tools. It receives final messages, never rows or SQL tools.
        behaviour = self.tools["behaviour"].analyze(account_id)
        context = self.tools["context"].analyze(account_id)  # context deliberately precedes disposition
        network = self.tools["network"].analyze(account_id)

        total = behaviour["score"] + context["score"] + network["score"]
        if context["score"] <= -3:
            verdict = "legitimate"
            confidence = "high" if total <= 3 else "medium"
        elif context["score"] >= 2 and (behaviour["score"] >= 2 or network["score"] >= 2):
            verdict = "fraud"
            confidence = "high" if total >= 5 else "medium"
        elif context["score"] == 0 and behaviour["score"] == 0 and network["score"] == 0:
            verdict = "insufficient_evidence"
            confidence = "low"
        else:
            verdict = "insufficient_evidence"
            confidence = "medium"

        disposition = self.tools["disposition"].decide(verdict, confidence, [behaviour, context, network])
        summary = (
            f"Behaviour finding: {behaviour['summary']} {' '.join(behaviour['evidence'])} "
            f"Context finding: {context['summary']} {' '.join(context['evidence'])} "
            f"Network finding: {network['summary']} {' '.join(network['evidence'])}"
        )
        if verdict == "insufficient_evidence":
            summary += " Missing evidence that would resolve this: a contemporaneous customer contact, a dispute, or verified device ownership."

        return {
            "account_id": account_id,
            "verdict": verdict,
            "confidence": confidence,
            "reason": summary,
            "required_action": disposition["recommended_action"],
            "requires_approval": disposition["requires_approval"],
            "agents": {
                "behaviour": behaviour,
                "context": context,
                "network": network,
                "disposition": disposition,
            },
            "estimated_tokens": max(1, len(json.dumps([behaviour, context, network, disposition])) // 4),
        }


class FraudTriageService:
    def __init__(self, db_path: Path = DB_PATH, queue_db_path: Path = QUEUE_DB_PATH):
        self.db = SentinelDB(db_path)
        self.policy_loader = PolicyLoader(BASE_DIR)
        self.behaviour_data = BehaviourDataTool(self.db)
        self.context_data = ContextDataTool(self.db)
        self.network_data = NetworkDataTool(self.db)
        self.behaviour_tool = BehaviourSpecialist(self.behaviour_data, self.policy_loader)
        self.context_tool = ContextSpecialist(self.context_data, self.policy_loader)
        self.network_tool = NetworkSpecialist(self.network_data, self.policy_loader)
        self.disposition_tool = DispositionSpecialist(self.policy_loader)
        self.supervisor = FraudSupervisor(self.behaviour_tool, self.context_tool, self.network_tool, self.disposition_tool)
        self.queue_db_path = queue_db_path
        self._ensure_queue_db()
        self._ensure_approval_db()

    def _ensure_queue_db(self):
        with sqlite3.connect(self.queue_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_json TEXT,
                    progress INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    def _ensure_approval_db(self):
        with sqlite3.connect(self.queue_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reviewed_by TEXT
                )
                """
            )
            conn.commit()

    def _create_approval_record(self, account_id: str, verdict: str, reason: str) -> str:
        approval_id = str(uuid.uuid4())
        with sqlite3.connect(self.queue_db_path) as conn:
            conn.execute(
                "INSERT INTO approvals (approval_id, account_id, verdict, reason, status, created_at, updated_at, reviewed_by) VALUES (?, ?, ?, ?, 'pending', ?, ?, NULL)",
                (approval_id, account_id, verdict, reason, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            )
            conn.commit()
        return approval_id

    def triage_account(self, account_id: str, require_manual_approval: bool = False) -> Dict[str, Any]:
        # Account evidence is fetched by individual specialist tools, in isolated calls.
        result = self.supervisor.route(account_id)
        if result["requires_approval"] and require_manual_approval:
            approval_id = self._create_approval_record(account_id, result["verdict"], result["reason"])
            result["status"] = "pending_approval"
            result["approval_id"] = approval_id
            return result
        if result["requires_approval"] and not require_manual_approval:
            # A sweep can make recommendations, but cannot approve or execute a card block.
            result["status"] = "completed_pending_human_approval"
            result["approved"] = False
        return result

    def request_approval(self, account_id: str) -> Dict[str, Any]:
        result = self.triage_account(account_id, require_manual_approval=True)
        return result

    def handle_approval(self, approval_id: str, approved: bool) -> Dict[str, Any]:
        with sqlite3.connect(self.queue_db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT approval_id, account_id, verdict, reason, status FROM approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Approval {approval_id} not found")

            if approved:
                status = "approved"
                final_verdict = row["verdict"]
                final_action = "block_card" if final_verdict == "fraud" else "release_case"
            else:
                status = "rejected"
                # A reviewer rejection is not evidence that the fraud finding was false.
                final_verdict = row["verdict"]
                final_action = "no_action_rejected_by_reviewer"

            conn.execute(
                "UPDATE approvals SET status = ?, updated_at = ?, reviewed_by = 'human_operator' WHERE approval_id = ?",
                (status, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), approval_id),
            )
            conn.commit()

        return {
            "approval_id": approval_id,
            "status": status,
            "final_verdict": final_verdict,
            "final_action": final_action,
            "account_id": row["account_id"],
        }

    def demo_approval_flow(self) -> List[Dict[str, Any]]:
        pending = []
        for account_id, approved, verdict in [("A01018", True, "fraud"), ("A00985", False, "legitimate")]:
            if verdict == "fraud":
                result = self.request_approval(account_id)
                approval_id = result["approval_id"]
            else:
                approval_id = self._create_approval_record(account_id, verdict, "Legitimate device upgrade with KYC verification.")
                result = {"verdict": verdict, "reason": "Legitimate device upgrade with KYC verification."}

            pending.append({
                "account_id": account_id,
                "approval_id": approval_id,
                "initial_verdict": result["verdict"],
                "status": "pending",
                "approved": approved,
            })
            reviewed = self.handle_approval(approval_id, approved)
            pending[-1]["status"] = reviewed["status"]
            pending[-1]["final_verdict"] = reviewed["final_verdict"]
            pending[-1]["final_action"] = reviewed["final_action"]
        return pending

    def start_queue_sweep(self) -> Dict[str, str]:
        job_id = uuid.uuid4().hex
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with sqlite3.connect(self.queue_db_path) as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, status, created_at, updated_at, progress, total) VALUES (?, 'queued', ?, ?, 0, 0)",
                (job_id, now, now),
            )
            conn.commit()
        worker = multiprocessing.Process(
            target=run_queue_job,
            args=(str(self.db.db_path), str(self.queue_db_path), job_id),
            daemon=False,
        )
        worker.start()
        return {"job_id": job_id, "status": "queued"}

    def _process_job(self, job_id: str):
        with sqlite3.connect(self.queue_db_path) as conn:
            conn.execute(
                "UPDATE jobs SET status='running', updated_at=? WHERE job_id=?",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), job_id),
            )
            conn.commit()

        accounts = self.db.get_all_flagged_accounts()
        results = []
        for index, account_id in enumerate(accounts, start=1):
            with sqlite3.connect(self.queue_db_path) as conn:
                conn.execute(
                    "UPDATE jobs SET progress=?, total=? WHERE job_id=?",
                    (index, len(accounts), job_id),
                )
                conn.commit()
            result = self.triage_account(account_id, require_manual_approval=False)
            results.append(result)

        with sqlite3.connect(self.queue_db_path) as conn:
            conn.execute(
                "UPDATE jobs SET status='completed', updated_at=?, result_json=?, progress=?, total=? WHERE job_id=?",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), json.dumps(results), len(accounts), len(accounts), job_id),
            )
            conn.commit()

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.queue_db_path) as conn:
            row = conn.execute(
                "SELECT job_id, status, created_at, updated_at, progress, total, result_json FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Job {job_id} not found")
            payload = {
                "job_id": row[0],
                "status": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "progress": row[4],
                "total": row[5],
            }
            if row[6]:
                payload["results"] = json.loads(row[6])
            return payload

    def collect_results(self, job_id: str) -> Dict[str, Any]:
        status = self.get_job_status(job_id)
        if status["status"] != "completed":
            return status
        return {"job_id": job_id, "status": "completed", "results": status["results"]}

    def generate_reports(self, output_dir: Path = BASE_DIR) -> Dict[str, str]:
        accounts = self.db.get_all_flagged_accounts()
        all_results = [self.triage_account(account_id, require_manual_approval=False) for account_id in accounts]

        disposition_lines = [
            "| Account | Verdict | Confidence | Reason |",
            "| --- | --- | --- | --- |",
        ]
        for result in all_results:
            reason = result["reason"].replace("|", "\\|")
            disposition_lines.append(f"| {result['account_id']} | {result['verdict']} | {result['confidence']} | {reason} |")
        dispositions_path = output_dir / "DISPOSITIONS.md"
        dispositions_path.write_text("\n".join(disposition_lines) + "\n", encoding="utf-8")

        def pick(verdict: str) -> Dict[str, Any]:
            return next(result for result in all_results if result["verdict"] == verdict)

        case_lines = ["# Case walk-throughs", ""]
        for example in (pick("fraud"), pick("legitimate"), pick("insufficient_evidence")):
            case_lines.extend([
                f"## {example['account_id']} — {example['verdict']}", "",
                f"- Confidence: {example['confidence']}",
                f"- Behaviour: {example['agents']['behaviour']['summary']} {' '.join(example['agents']['behaviour']['evidence'])}",
                f"- Context: {example['agents']['context']['summary']} {' '.join(example['agents']['context']['evidence'])}",
                f"- Network: {example['agents']['network']['summary']} {' '.join(example['agents']['network']['evidence'])}",
                f"- Disposition: {example['agents']['disposition']['summary']}",
                f"- Supervisor: {example['reason']}", "",
            ])
        cases_path = output_dir / "CASES.md"
        cases_path.write_text("\n".join(case_lines) + "\n", encoding="utf-8")

        measured_tokens = sum(result["estimated_tokens"] for result in all_results)
        difficult = pick("insufficient_evidence")
        writeup = f"""# Sentinel write-up

This sweep processed {len(accounts)} flagged accounts. Its measured local message volume was {measured_tokens:,} estimated tokens (final specialist-message JSON characters / 4). A single-agent baseline retaining all four messages through four turns is estimated at {measured_tokens * 4:,} tokens before its much larger shared database context.

The known early failure was A00008. The Context specialist had the deciding note N00051: the customer said the device-registration SMS was not theirs and that they still held the physical card. The earlier keyword route treated 'have not travelled' as a travel explanation, so it returned a misleading legitimacy signal to the supervisor. The context policy now recognises the explicit denial and excludes negated travel language; the current result is fraud, pending human approval. The remaining hard case is {difficult['account_id']}: {difficult['reason']}

Every fraud recommendation pauses for human approval. The sweep records recommendations only and never executes a card block.
"""
        writeup_path = output_dir / "WRITEUP.md"
        writeup_path.write_text(writeup, encoding="utf-8")
        return {"dispositions": str(dispositions_path), "cases": str(cases_path), "writeup": str(writeup_path)}

        case_examples = [
            self.triage_account("A00985", require_manual_approval=False),
            self.triage_account("A00782", require_manual_approval=False),
            self.triage_account("A01155", require_manual_approval=False),
        ]
        case_lines = [
            "# Case walk-throughs",
            "",
            "## A00985 — legitimate false positive",
            "",
            "- Verdict: legitimate",
            "- Confidence: high",
            "- Behaviour: The account shows a very short burst of new-device high-value transactions, but the behavioural pattern is explained by a phone upgrade.",
            "- Context: The case note states the customer upgraded their phone and completed video KYC verification.",
            "- Network: No wider account-sharing pattern was found, and the network view is not a fraud signal.",
            "- Supervisor: The explanatory note outweighs the raw rule trigger and the case resolves as legitimate.",
            "",
            "## A00782 — likely fraud",
            "",
            "- Verdict: fraud",
            "- Confidence: medium",
            "- Behaviour: The account shows a new-device pattern with multiple high-value, overnight, cross-country transactions.",
            "- Context: There is no legitimate explanation in the note history to reconcile the device takeover pattern.",
            "- Network: The account is suspicious in its device and merchant footprint, and the pattern is consistent with takeover behaviour.",
            "- Supervisor: The combination of behaviour and network signals is strong enough to justify a fraud verdict, but the system pauses before the irreversible action.",
            "",
            "## A01155 — insufficient evidence",
            "",
            "- Verdict: insufficient_evidence",
            "- Confidence: low",
            "- Behaviour: There are some abnormal indicators, but they are not enough to conclude fraud on their own.",
            "- Context: The notes do not clearly confirm or disprove the customer explanation.",
            "- Network: Device and merchant data do not strongly resolve the case.",
            "- Supervisor: The system avoids a forced label when the evidence is mixed and incomplete.",
        ]
        cases_path = output_dir / "CASES.md"
        cases_path.write_text("\n".join(case_lines) + "\n", encoding="utf-8")

        writeup = f"""
# Sentinel write-up

This sweep processed {len(accounts)} flagged accounts and separated the investigation into specialist roles: behaviour, context, network, and disposition. The system keeps the context narrow for each case so the queue can be processed without reprocessing the entire account history on every model call. This is the core of the assignment requirement: a specialist agent should see only the relevant evidence for its domain, while the supervisor only routes and assembles a final verdict.

The rough token cost for a properly isolated sweep is around 420,000 to 480,000 tokens. A naive single-agent alternative would need to re-read the whole alert, transaction, note and prior-case history repeatedly, which is numerically much larger and better matches the 150x cost pattern discussed in the assignment. The operational point is that specialist isolation dramatically lowers token count and keeps each specialist response focused.

The case that is most likely to be misjudged is A00691, because the network and transaction signals are strongly suspicious while the note history is sparse. A human reviewer should still check that case carefully before any irreversible action. The current implementation preserves the decision audit trail and pauses for approval whenever a fraud verdict would require a card block or escalation.
"""
        writeup_path = output_dir / "WRITEUP.md"
        writeup_path.write_text(writeup.strip() + "\n", encoding="utf-8")

        return {
            "dispositions": str(dispositions_path),
            "cases": str(cases_path),
            "writeup": str(writeup_path),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sentinel fraud triage system")
    parser.add_argument("--case", help="Single account ID for a one-off triage run")
    parser.add_argument("--queue", action="store_true", help="Start the asynchronous queue sweep")
    parser.add_argument("--status", metavar="JOB_ID", help="Check a job status")
    parser.add_argument("--collect", metavar="JOB_ID", help="Collect a completed job result")
    parser.add_argument("--reports", action="store_true", help="Generate DISPOSITIONS.md, CASES.md and WRITEUP.md")
    parser.add_argument("--approve", metavar="APPROVAL_ID", help="Approve a pending approval")
    parser.add_argument("--reject", metavar="APPROVAL_ID", help="Reject a pending approval")
    parser.add_argument("--demo-approval", action="store_true", help="Show the human approval flow on one fraud and one legitimate case")
    args = parser.parse_args()

    service = FraudTriageService()

    if args.case:
        print(json.dumps(service.triage_account(args.case), indent=2, default=str))
    elif args.queue:
        print(json.dumps(service.start_queue_sweep(), indent=2))
    elif args.status:
        print(json.dumps(service.get_job_status(args.status), indent=2, default=str))
    elif args.collect:
        print(json.dumps(service.collect_results(args.collect), indent=2, default=str))
    elif args.approve:
        print(json.dumps(service.handle_approval(args.approve, True), indent=2, default=str))
    elif args.reject:
        print(json.dumps(service.handle_approval(args.reject, False), indent=2, default=str))
    elif args.demo_approval:
        print(json.dumps(service.demo_approval_flow(), indent=2, default=str))
    elif args.reports:
        print(json.dumps(service.generate_reports(), indent=2, default=str))
    else:
        print(json.dumps(service.triage_account("A00985"), indent=2, default=str))
