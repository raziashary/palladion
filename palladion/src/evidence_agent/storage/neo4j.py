"""Fixed parameterized Neo4j projection queries; no arbitrary Cypher from a model."""

from __future__ import annotations

import re
from typing import Any

from neo4j import GraphDatabase, Query
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

from evidence_agent.core.errors import DependencyUnavailable


class Neo4jIndex:
    def __init__(
        self,
        *,
        uri: str = "bolt://127.0.0.1:17687",
        partition: str = "palladion_graph_v1",
        timeout_seconds: float = 2.0,
    ) -> None:
        if not re.fullmatch(r"bolt://127\.0\.0\.1:[0-9]{4,5}", uri):
            raise ValueError("Synthetic graph requires loopback Bolt")
        if not re.fullmatch(r"[a-zA-Z0-9_]{1,100}", partition) or not 0 < timeout_seconds <= 10:
            raise ValueError("Graph configuration bounds exceeded")
        self.uri, self.partition, self.timeout_seconds = uri, partition, timeout_seconds
        self.driver = GraphDatabase.driver(
            uri,
            auth=None,
            max_connection_pool_size=4,
            connection_timeout=timeout_seconds,
            connection_acquisition_timeout=timeout_seconds,
            max_transaction_retry_time=0,
            telemetry_disabled=True,
        )

    @property
    def worker_configuration(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "partition": self.partition,
            "timeout_seconds": self.timeout_seconds,
        }

    def _run(
        self, cypher: str, *, _timeout: float | None = None, **parameters: Any
    ) -> list[dict[str, Any]]:
        try:
            with self.driver.session(database="neo4j", fetch_size=128) as session:
                result = session.run(
                    Query(
                        cypher,
                        timeout=min(self.timeout_seconds, _timeout)
                        if _timeout is not None
                        else self.timeout_seconds,
                    ),
                    partition=self.partition,
                    **parameters,
                )
                return [record.data() for record in result]
        except (Neo4jError, ServiceUnavailable, SessionExpired, OSError) as exc:
            raise DependencyUnavailable("Graph unavailable") from exc

    def ensure_constraints(self) -> None:
        for name, label in (
            ("palladion_entity_key", "PalladionEntity"),
            ("palladion_chunk_key", "PalladionChunk"),
            ("palladion_edge_key", "PalladionEdge"),
        ):
            self._run(
                f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.key IS UNIQUE"
            )

    def ready(self) -> bool:
        return bool(self._run("RETURN 1 AS ready")[0]["ready"] == 1)

    def upsert_chunk(
        self,
        tenant: str,
        case: str,
        revision: str,
        generation: str,
        chunk_id: str,
        sha256: str,
        entity_keys: tuple[str, ...],
        *,
        allowed_principal_ids: tuple[str, ...] = (),
    ) -> None:
        if len(entity_keys) > 32:
            raise ValueError("Entity projection bound")
        self._run(
            "MERGE (c:PalladionChunk {key:$key}) SET c.partition=$partition, "
            "c.tenant=$tenant,c.case=$case,c.revision=$revision,c.generation=$generation,"
            "c.chunk_id=$chunk_id,c.sha256=$sha256,c.allowed_principal_ids=$allowed "
            "WITH c OPTIONAL MATCH (old:PalladionEntity)-[mention:MENTIONED_IN]->(c) "
            "DELETE mention WITH DISTINCT c UNWIND $entities AS entity "
            "MERGE (e:PalladionEntity {key:entity.key}) SET e.partition=$partition,"
            "e.tenant=$tenant,e.case=$case,e.entity_key=entity.id MERGE (e)-[:MENTIONED_IN]->(c)",
            key=self._key(tenant, case, "chunk", chunk_id),
            tenant=tenant,
            case=case,
            revision=revision,
            generation=generation,
            chunk_id=chunk_id,
            sha256=sha256,
            allowed=list(allowed_principal_ids),
            entities=[{"key": self._key(tenant, case, "entity", e), "id": e} for e in entity_keys],
        )

    def upsert_edge(
        self,
        tenant: str,
        case: str,
        edge_id: str,
        from_key: str,
        to_key: str,
        relation_type: str,
        evidence_chunk_id: str,
        evidence_kind: str,
        *,
        revision: str | None = None,
        generation: str | None = None,
    ) -> None:
        from evidence_agent.graph.relations import RelationCandidate

        # Validate vocabulary before fixed query; the relation type is data, not syntax.
        RelationCandidate.model_validate(
            {
                "from_key": from_key,
                "to_key": to_key,
                "relation_type": relation_type,
                "evidence_chunk_id": evidence_chunk_id,
            }
        )
        self._run(
            "MERGE (a:PalladionEntity {key:$a}) SET a.partition=$partition,"
            "a.tenant=$tenant,a.case=$case,a.entity_key=$from_key "
            "MERGE (b:PalladionEntity {key:$b}) SET b.partition=$partition,"
            "b.tenant=$tenant,b.case=$case,b.entity_key=$to_key "
            "MERGE (r:PalladionEdge {key:$key}) SET r.partition=$partition,r.tenant=$tenant,"
            "r.case=$case,r.edge_id=$edge_id,r.relation_type=$kind,r.evidence_chunk_id=$chunk,"
            "r.evidence_kind=$state,r.revision=$revision,r.generation=$generation "
            "WITH a,b,r OPTIONAL MATCH ()-[old_from:FROM]->(r) DELETE old_from "
            "WITH DISTINCT a,b,r OPTIONAL MATCH (r)-[old_to:TO]->() DELETE old_to "
            "WITH DISTINCT a,b,r MERGE (a)-[:FROM]->(r) MERGE (r)-[:TO]->(b)",
            a=self._key(tenant, case, "entity", from_key),
            b=self._key(tenant, case, "entity", to_key),
            key=self._key(tenant, case, "edge", edge_id),
            tenant=tenant,
            case=case,
            edge_id=edge_id,
            kind=relation_type,
            chunk=evidence_chunk_id,
            state=evidence_kind,
            from_key=from_key,
            to_key=to_key,
            revision=revision,
            generation=generation,
        )

    def projection_readback(self, tenant: str, revision: str, generation: str) -> dict[str, str]:
        from evidence_agent.graph.relations import ProjectedRelation, projection_digest

        rows = self._run(
            "MATCH (c:PalladionChunk {partition:$partition,tenant:$tenant,"
            "revision:$revision,generation:$generation}) OPTIONAL MATCH "
            "(e:PalladionEntity)-[:MENTIONED_IN]->(c) RETURN c.chunk_id AS id,c.sha256 AS hash,"
            "collect(DISTINCT e.entity_key) AS entities ORDER BY id LIMIT 4097",
            tenant=tenant,
            revision=revision,
            generation=generation,
        )
        if len(rows) > 4096:
            raise ValueError("Graph projection readback invalid")
        manifest = {
            "c:" + r["id"]: projection_digest([r["hash"], sorted(r["entities"])]) for r in rows
        }
        edges = self._run(
            "MATCH(e:PalladionEdge {partition:$partition,tenant:$tenant,"
            "revision:$revision,generation:$generation}) OPTIONAL MATCH (a:PalladionEntity)-[:FROM]->(e) "
            "WITH e,collect(DISTINCT a.entity_key) AS origins OPTIONAL MATCH (e)-[:TO]->(b:PalladionEntity) "
            "RETURN e.edge_id AS edge_id,origins,collect(DISTINCT b.entity_key) AS targets,"
            "e.relation_type AS relation_type,e.evidence_chunk_id AS evidence_chunk_id,"
            "e.evidence_kind AS evidence_kind ORDER BY edge_id LIMIT 4097",
            tenant=tenant,
            revision=revision,
            generation=generation,
        )
        if len(edges) > 4096:
            raise ValueError("Graph edge readback bound")
        for row in edges:
            if len(row["origins"]) != 1 or len(row["targets"]) != 1:
                manifest["r:" + row["edge_id"]] = "INVALID_ADJACENCY"
                continue
            item = ProjectedRelation.model_validate(
                {
                    k: row[k]
                    for k in ("edge_id", "relation_type", "evidence_chunk_id", "evidence_kind")
                }
                | {"from_key": row["origins"][0], "to_key": row["targets"][0]}
            )
            manifest["r:" + item.edge_id] = projection_digest(item.model_dump(mode="json"))
        return manifest

    def readback(self, tenant: str, revision: str, generation: str) -> dict[str, str]:
        rows = self._run(
            "MATCH (c:PalladionChunk {partition:$partition,tenant:$tenant,"
            "revision:$revision,generation:$generation}) RETURN c.chunk_id AS id,c.sha256 AS hash "
            "ORDER BY id LIMIT 4097",
            tenant=tenant,
            revision=revision,
            generation=generation,
        )
        if len(rows) > 4096:
            raise ValueError("Graph manifest exceeds bound")
        return {row["id"]: row["hash"] for row in rows}

    def neighbors(
        self,
        tenant: str,
        case: str,
        chunk_ids: tuple[str, ...],
        *,
        fanout: int,
        principal_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= fanout <= 32 or len(chunk_ids) > 12:
            raise ValueError("Graph query bounds")
        # One fixed one-hop query per bounded anchor; never unbounded variable paths.
        rows = self._run(
            "MATCH (c:PalladionChunk {partition:$partition,tenant:$tenant,case:$case})"
            "<-[:MENTIONED_IN]-(a:PalladionEntity) WHERE c.chunk_id IN $anchors "
            "AND (c.allowed_principal_ids=[] OR $principal IN c.allowed_principal_ids) "
            "MATCH (a)-[:FROM|TO]-(r:PalladionEdge {partition:$partition,tenant:$tenant,case:$case})"
            "-[:FROM|TO]-(b:PalladionEntity)-[:MENTIONED_IN]->(n:PalladionChunk "
            "{partition:$partition,tenant:$tenant,case:$case}) WHERE a<>b "
            "AND (n.allowed_principal_ids=[] OR $principal IN n.allowed_principal_ids) "
            "MATCH (proof:PalladionChunk {partition:$partition,tenant:$tenant,case:$case}) "
            "WHERE proof.chunk_id=r.evidence_chunk_id "
            "AND (proof.allowed_principal_ids=[] OR $principal IN proof.allowed_principal_ids) "
            "RETURN DISTINCT r.edge_id AS edge_id,n.chunk_id AS chunk_id,"
            "n.generation AS generation ORDER BY edge_id,chunk_id LIMIT $limit",
            tenant=tenant,
            case=case,
            anchors=list(chunk_ids),
            limit=fanout,
            principal=principal_id,
            _timeout=timeout_seconds,
        )
        return tuple(rows)

    def entity_count(self, tenant: str, case: str, entity_key: str) -> int:
        rows = self._run(
            "MATCH (e:PalladionEntity {key:$key}) RETURN count(e) AS count",
            key=self._key(tenant, case, "entity", entity_key),
        )
        return int(rows[0]["count"])

    def _key(self, tenant: str, case: str, kind: str, identifier: str) -> str:
        import hashlib
        import json

        return hashlib.sha256(
            json.dumps([self.partition, tenant, case, kind, identifier]).encode()
        ).hexdigest()

    def close(self) -> None:
        self.driver.close()
