"""Deterministic-primary memory categories; cosine is optional evidence, never authority."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Literal, Sequence

from evidence_agent.core.ids import digest_bytes
from evidence_agent.retrieval.embeddings import DenseEncoder

Category = Literal["EPISODIC", "SEMANTIC", "PROCEDURAL"]
CATEGORIES: tuple[Category, ...] = ("EPISODIC", "SEMANTIC", "PROCEDURAL")
PROTOTYPES: tuple[tuple[Category, str], ...] = (
    ("SEMANTIC", "I prefer concise answers and short explanations."),
    ("SEMANTIC", "Please reply to me in Indonesian."),
    ("SEMANTIC", "I like detailed explanations with examples."),
    ("SEMANTIC", "Short explanations work better for me."),
    ("SEMANTIC", "Saya lebih suka jawaban singkat."),
    ("PROCEDURAL", "Observed tool experience: search_knowledge returned SUCCEEDED."),
    ("PROCEDURAL", "Observed tool experience: evaluate_policy returned FAILED."),
    ("PROCEDURAL", "This unapproved workflow first searches and then checks policy."),
    ("EPISODIC", "What happened to this transaction in this case?"),
    ("EPISODIC", "The current settlement result is missing and needs verification."),
    ("EPISODIC", "The user asked a question during this conversation."),
)
_TOOLS = {"search_knowledge", "evaluate_policy", "lookup_live_data", "recall_memory"}
_BLOCKED = re.compile(
    r"\b(transaction|settlement|merchant|refund|reverse|payment|policy|approve|"
    r"system|ignore|instruction|credential|password|secret|token|api.?key|tenant|scope|"
    r"transaksi|pembayaran|rekening|kebijakan)\b",
    re.IGNORECASE,
)
_EXPLICIT = re.compile(
    r"^(?:please remember[,:]?\s*)?(?:i (?:prefer|like)|my preference is|"
    r"please (?:reply|respond) (?:to me )?in|(?:please )?call me|saya (?:lebih )?suka)\s+",
    re.IGNORECASE,
)
_WEAK = re.compile(r"\b(?:for me|suits me|works better|lebih nyaman bagi saya)\b", re.IGNORECASE)
_ATTRIBUTED = re.compile(
    r"\b(?:she said|he said|they said|document says|user says|reported that|quote)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Classification:
    category: Category
    rule_id: str
    scores: dict[str, float]
    loss: float | None = None
    semantic_eligible: bool = False
    model_fingerprint: str | None = None


def deterministic(text: str, *, field_name: str, tool: str | None = None) -> Classification:
    if not text or len(text.encode()) > 4096:
        raise ValueError("Memory classification input bound")
    if field_name == "tool_summary" and tool in _TOOLS:
        return Classification("PROCEDURAL", "OBSERVED_TOOL_EXPERIENCE", {"path_a": 1.0})
    if (
        field_name != "query"
        or _BLOCKED.search(text)
        or _ATTRIBUTED.search(text)
        or any(c in text for c in ('"', "`", "?", "\n"))
    ):
        return Classification("EPISODIC", "HARD_EPISODIC_BOUNDARY", {"path_a": 1.0})
    stripped = text.strip()
    if _EXPLICIT.match(stripped) and len(stripped) <= 512:
        return Classification(
            "SEMANTIC", "EXPLICIT_USER_PREFERENCE", {"path_a": 1.0}, semantic_eligible=True
        )
    if (
        _WEAK.search(stripped)
        and len(stripped) <= 512
        and stripped.lower().startswith(
            (
                "short",
                "brief",
                "concise",
                "detailed",
                "long",
                "indonesian",
                "english",
                "jawaban",
                "penjelasan",
            )
        )
    ):
        return Classification(
            "EPISODIC", "AMBIGUOUS_PERSONAL_PREFERENCE", {"path_a": 0.6}, semantic_eligible=True
        )
    return Classification("EPISODIC", "SESSION_CONTEXT", {"path_a": 1.0})


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right) or any(not math.isfinite(x) for x in (*left, *right)):
        raise ValueError("Invalid similarity vectors")
    denominator = math.sqrt(math.fsum(x * x for x in left) * math.fsum(x * x for x in right))
    if denominator == 0:
        raise ValueError("Zero similarity vector")
    return max(
        -1.0, min(1.0, math.fsum(a * b for a, b in zip(left, right, strict=True)) / denominator)
    )


class SimilaritySupplement:
    def __init__(
        self,
        encoder: DenseEncoder,
        *,
        rule_weight: float = 0.8,
        threshold: float = 0.75,
        margin: float = 0.1,
        combined_threshold: float = 0.65,
    ) -> None:
        if (
            not 0.5 < rule_weight <= 1
            or not 0 <= threshold <= 1
            or not 0 <= margin <= 1
            or not 0 <= combined_threshold <= 1
        ):
            raise ValueError("Similarity configuration bounds")
        self.encoder, self.rule_weight, self.threshold, self.margin = (
            encoder,
            rule_weight,
            threshold,
            margin,
        )
        self.combined_threshold = combined_threshold
        self.embedding_calls = 0
        self.embedding_texts = 0

    @property
    def profile(self) -> dict[str, object]:
        return {
            "version": "promotion-1",
            "prototypes_sha256": digest_bytes(
                json.dumps(PROTOTYPES, ensure_ascii=False, separators=(",", ":")).encode()
            ),
            "rule_weight": self.rule_weight,
            "threshold": self.threshold,
            "margin": self.margin,
            "combined_threshold": self.combined_threshold,
            "model_fingerprint": self.encoder.fingerprint,
            "loss": "max(0,margin-(top-second))",
            "trained": False,
            "calibrated": False,
        }

    def classify(self, text: str, primary: Classification) -> Classification:
        # A hard rejection/decisive rule always wins; do not load a model for it.
        if primary.rule_id != "AMBIGUOUS_PERSONAL_PREFERENCE" or not primary.semantic_eligible:
            return primary
        vectors = self.encoder.embed_documents([*(p[1] for p in PROTOTYPES), text])
        self.embedding_calls += 1
        self.embedding_texts += len(PROTOTYPES) + 1
        if len(vectors) != len(PROTOTYPES) + 1:
            raise ValueError("Invalid embedding batch")
        scores = {
            category: max(
                cosine(vectors[-1], vectors[i])
                for i, p in enumerate(PROTOTYPES)
                if p[0] == category
            )
            for category in CATEGORIES
        }
        ranked = sorted(scores, key=lambda c: scores[c], reverse=True)
        loss = max(0.0, self.margin - (scores[ranked[0]] - scores[ranked[1]]))
        # Lower-influence similarity supplements a weak deterministic preference cue.
        combined = self.rule_weight * primary.scores["path_a"] + (1 - self.rule_weight) * max(
            0.0, scores["SEMANTIC"]
        )
        accepted = (
            ranked[0] == "SEMANTIC"
            and scores["SEMANTIC"] >= self.threshold
            and loss == 0
            and combined >= self.combined_threshold
        )
        return Classification(
            "SEMANTIC" if accepted else "EPISODIC",
            "COSINE_SUPPORTED_PREFERENCE" if accepted else "COSINE_ABSTENTION",
            {
                **primary.scores,
                **{"cosine_" + k: v for k, v in scores.items()},
                "combined": combined,
                "rule_weight": self.rule_weight,
            },
            loss,
            True,
            self.encoder.fingerprint,
        )
