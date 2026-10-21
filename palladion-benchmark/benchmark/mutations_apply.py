"""Applying a mutation to a system through the interface it has (B07-T07.02, BADR-0039).

A system is a :class:`MutationTarget`: it says which operations it cannot carry and why, applies the rest through its
own interface, and reports what it holds. Two targets exist. :class:`RebuildTarget` is an arm that builds its index from
the published corpus: a mutation is a changed corpus and a rebuild. :class:`PalladionTarget` is Palladion over HTTP:
upload, approve and revoke. Operations that live in the request (a query, a clock, a chat claim) are *carried*, not
applied: they are returned for the runner to put in the question.

The result of one application is an :class:`Application`. A mutation a system cannot take is recorded as
FEATURE_NOT_SUPPORTED with the reasons, or NOT_RUN when the caller could not try; it is never a pass. After an
application the target's holdings are compared with what the declared patch should have made them, and any difference
is listed. :func:`violations` is the other half of the contract: given what an answer cited and said, it counts the
reads the expectation forbids (an unauthorized read of a revoked passage is one).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from benchmark.adapters.common import AdapterError
from benchmark.adapters.palladion import PalladionArm
from benchmark.contracts import ArmUnavailable, EvidenceStatus, TransientInfrastructureError
from benchmark.fixtures.documents import Document
from benchmark.fixtures.manifest import ManifestRecord
from benchmark.fixtures.mutations import (
    CORPUS_OPS,
    MutationError,
    MutationInstance,
    Op,
    OpKind,
    apply_corpus,
)

CARRIED = frozenset({OpKind.SET_QUERY, OpKind.SET_CLOCK, OpKind.CHAT_CLAIM})
RETRIEVABLE_STATES = frozenset({"approved", "retired", "non_normative"})
APPLY_ERRORS = (MutationError, AdapterError, ArmUnavailable, TransientInfrastructureError, TimeoutError)


class Outcome(StrEnum):
    APPLIED = "applied"
    NOT_RUN = "not_run"
    FEATURE_NOT_SUPPORTED = "feature_not_supported"
    FAILED = "failed"


@dataclass(frozen=True)
class Application:
    """What happened when one mutation instance met one system."""

    instance_id: str
    system: str
    outcome: Outcome
    reasons: tuple[str, ...] = ()
    applied: tuple[OpKind, ...] = ()
    carried: tuple[Op, ...] = ()
    mismatches: tuple[str, ...] = ()

    @property
    def verified(self) -> bool:
        """Applied, and the system holds exactly what the patch declares for the documents it touched."""
        return self.outcome is Outcome.APPLIED and not self.mismatches


class MutationTarget(Protocol):
    name: str

    def unsupported(self, op: Op) -> str | None: ...

    def apply(self, ops: Sequence[Op]) -> None: ...

    def held(self) -> Mapping[str, bool]: ...

    def restore(self) -> tuple[str, ...]:
        """Undo what ``apply`` did so the next case starts from the base state; return what could not be undone."""
        ...


def expected_held(base: Sequence[Document], ops: Sequence[Op]) -> dict[str, bool]:
    """Whether each document the corpus operations touch should be retrievable once they are applied."""
    touched = {op.document.doc_id for op in ops if op.document is not None}
    touched |= {op.target for op in ops if op.kind in CORPUS_OPS and op.kind is not OpKind.ADD_DOCUMENT}
    after = {d.doc_id: d for d in apply_corpus(base, ops)}
    return {doc_id: after[doc_id].registry_state in RETRIEVABLE_STATES for doc_id in touched}


def unsupported_reasons(target: MutationTarget, instance: MutationInstance) -> tuple[str, ...]:
    """Why the target cannot take this instance, one entry per operation kind; empty when it can."""
    ops = (*instance.precondition, *instance.patch)
    return tuple(sorted({f"{op.kind.value}: {why}" for op in ops if (why := target.unsupported(op))}))


def apply_instance(
    target: MutationTarget, instance: MutationInstance, base: Sequence[Document], *, not_run: str | None = None
) -> Application:
    """Apply the precondition and the patch to ``target``, or record why that is not possible.

    Nothing is applied when any operation is unsupported, so a system is never left half-mutated.
    """
    ops = (*instance.precondition, *instance.patch)
    if not_run is not None:
        return Application(instance.instance_id, target.name, Outcome.NOT_RUN, (not_run,))
    reasons = unsupported_reasons(target, instance)
    if reasons:
        return Application(instance.instance_id, target.name, Outcome.FEATURE_NOT_SUPPORTED, reasons)
    applied = [op for op in ops if op.kind not in CARRIED]
    try:
        target.apply(applied)
    except APPLY_ERRORS as exc:
        return Application(instance.instance_id, target.name, Outcome.FAILED, (f"{type(exc).__name__}: {exc}",))
    held = target.held()
    expected = expected_held(base, ops)
    mismatches = tuple(
        f"{doc_id}: expected {'retrievable' if want else 'not retrievable'}, holds {held.get(doc_id)}"
        for doc_id, want in sorted(expected.items())
        if held.get(doc_id) != want
    )
    return Application(
        instance.instance_id,
        target.name,
        Outcome.APPLIED,
        applied=tuple(op.kind for op in applied),
        carried=tuple(op for op in ops if op.kind in CARRIED),
        mismatches=mismatches,
    )


class RebuildTarget:
    """An arm that builds its index from the published corpus: apply the corpus operations, then rebuild.

    ``rebuild`` receives the mutated corpus and must publish it and rebuild the arm's index from it; the target holds
    what it was given. The registry and the index are one thing for such an arm, so an index entry cannot be dropped
    alone, and it has no conversation, live tool or graph to change.
    """

    def __init__(self, name: str, corpus: Sequence[Document], rebuild: Callable[[tuple[Document, ...]], None]) -> None:
        self.name = name
        self._base = tuple(corpus)
        self._corpus = self._base
        self._rebuild = rebuild

    def unsupported(self, op: Op) -> str | None:
        reasons = {
            OpKind.DROP_FROM_INDEX: "the index is built from the registry, so no entry can be dropped alone",
            OpKind.SET_LIVE: "the arm has no live-state tool",
            OpKind.ADD_EDGE: "the arm has no graph",
            OpKind.CHAT_CLAIM: "the arm answers one question at a time and has no conversation",
        }
        return reasons.get(op.kind)

    def apply(self, ops: Sequence[Op]) -> None:
        self._corpus = apply_corpus(self._corpus, ops)
        self._rebuild(self._corpus)

    def held(self) -> dict[str, bool]:
        return {d.doc_id: d.registry_state in RETRIEVABLE_STATES for d in self._corpus}

    @property
    def corpus(self) -> tuple[Document, ...]:
        return self._corpus

    def restore(self) -> tuple[str, ...]:
        self._corpus = self._base
        self._rebuild(self._base)
        return ()


class PalladionTarget:
    """Palladion over its HTTP interface: upload and approve a document, revoke one.

    ``record_for`` builds the manifest record the upload needs (family, validity, supersession) for a document the
    patch adds. Palladion has no per-role access list, no re-approval of a revoked document, no clock or live mode set
    from outside, no index entry to drop and, with the graph off, no link to add; those are reported, not emulated.
    """

    def __init__(self, name: str, arm: PalladionArm, record_for: Callable[[Document], ManifestRecord]) -> None:
        self.name = name
        self._arm = arm
        self._record_for = record_for
        self._added: list[str] = []
        self._revoked: list[str] = []

    def unsupported(self, op: Op) -> str | None:
        if op.kind is OpKind.SET_REGISTRY_STATE:
            ok = op.value == "withdrawn"
            return None if ok else "Palladion has no route that approves a revoked document again"
        reasons = {
            OpKind.EDIT_TEXT: "a document id maps to one Palladion revision; an edit would change its identity",
            OpKind.REVOKE_ROLE: "Palladion has no per-role access list; its access is by case",
            OpKind.GRANT_ROLE: "Palladion has no per-role access list; its access is by case",
            OpKind.SET_TITLE: "a title is the file name of an upload; renaming is a new revision with a new identity",
            OpKind.SET_CLOCK: "the evaluation clock is fixed when the server starts",
            OpKind.SET_LIVE: "no interface sets the live mock's behavior for a running server",
            OpKind.DROP_FROM_INDEX: "no interface removes index entries of an approved revision",
            OpKind.ADD_EDGE: "the graph is off in the evaluated configuration",
        }
        return reasons.get(op.kind)

    def apply(self, ops: Sequence[Op]) -> None:
        for op in ops:
            if op.kind is OpKind.ADD_DOCUMENT and op.document is not None:
                record = self._record_for(op.document)
                self._arm.publish(record, op.document.text, supersedes=record.supersedes)
                self._added.append(record.doc_id)
            elif op.kind is OpKind.SET_REGISTRY_STATE:
                self._arm.revoke(op.target)
                self._revoked.append(op.target)
            else:
                raise MutationError(f"{op.kind.value} reached Palladion although it is unsupported")

    def held(self) -> dict[str, bool]:
        return {doc_id: state == "APPROVED" for doc_id, state in self._arm.held_states().items()}

    def restore(self) -> tuple[str, ...]:
        """Revoke the documents this target added. A base document it revoked stays revoked (no route undoes it)."""
        for doc_id in self._added:
            if self._arm.held_states().get(doc_id) == "APPROVED":
                self._arm.revoke(doc_id)
        residue = tuple(f"{doc_id} revoked and not restorable" for doc_id in self._revoked)
        self._added, self._revoked = [], []
        return residue


@dataclass(frozen=True)
class Violations:
    """What an answer did that the expectation forbids, and what it left out."""

    cited_forbidden: tuple[str, ...]
    exposed: tuple[str, ...]
    missing_citations: tuple[str, ...]
    status_allowed: bool | None  # None when the expectation does not constrain the status

    @property
    def unauthorized_reads(self) -> int:
        """Forbidden documents cited plus forbidden strings shown: each is a read the expectation rules out."""
        return len(self.cited_forbidden) + len(self.exposed)


def violations(
    instance: MutationInstance, cited_doc_ids: Iterable[str], answer_text: str, status: EvidenceStatus
) -> Violations:
    """Score one answer against the instance's expectation."""
    expectation = instance.expectation
    cited = {c.split("#", 1)[0] for c in cited_doc_ids}  # a clause locator names its document
    lowered = answer_text.lower()
    return Violations(
        cited_forbidden=tuple(i for i in expectation.must_not_cite if i in cited),
        exposed=tuple(s for s in expectation.must_not_expose if s.lower() in lowered),
        missing_citations=tuple(i for i in expectation.must_cite if i not in cited),
        status_allowed=None if not expectation.statuses else status in expectation.statuses,
    )
