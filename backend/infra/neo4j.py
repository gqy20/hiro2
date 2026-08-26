"""Thin Neo4j adapter for rebuildable job capability projections."""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any


def _driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )


def check_neo4j() -> bool:
    try:
        with _driver() as driver:
            driver.verify_connectivity()
        return True
    except Exception:
        return False


def ensure_constraints(driver: Any) -> None:
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT job_version_id IF NOT EXISTS FOR (n:JobVersion) "
            "REQUIRE n.version_id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT capability_id IF NOT EXISTS FOR (n:Capability) "
            "REQUIRE n.skill_id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT skill_point_id IF NOT EXISTS FOR (n:SkillPoint) "
            "REQUIRE n.skill_id IS UNIQUE"
        )


def project_job_version(version: dict[str, Any]) -> None:
    """Idempotently project one published job version and its skill edges."""
    version_id = str(version.get("version_id") or version.get("id") or "")
    if not version_id:
        raise ValueError("version_id is required")
    with _driver() as driver:
        ensure_constraints(driver)
        with driver.session() as session:
            session.run(
                """
                MERGE (j:JobVersion {version_id: $version_id})
                SET j.job_id = $job_id, j.title = $title, j.version_hash = $version_hash
                WITH j
                OPTIONAL MATCH (j)-[r:REQUIRES|PREFERS]->()
                DELETE r
                """,
                version_id=version_id,
                job_id=version.get("job_id", ""),
                title=version.get("title", ""),
                version_hash=version.get("version_hash", ""),
            )
            _project_edges(session, version_id, version.get("required_skill_ids", []), "REQUIRES")
            _project_edges(session, version_id, version.get("preferred_skill_ids", []), "PREFERS")


def read_job_graph(version_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read a projected graph; callers decide how to enrich the API view model."""
    with _driver() as driver, driver.session() as session:
        records = session.run(
            """
            MATCH (j:JobVersion {version_id: $version_id})-[r]->(s)
            RETURN j.version_id AS version_id, s.skill_id AS skill_id,
                   s.name AS name, type(r) AS relation
            ORDER BY s.skill_id
            """,
            version_id=version_id,
        )
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        for record in records:
            skill_id = str(record["skill_id"])
            nodes[skill_id] = {
                "id": skill_id,
                "label": record["name"] or skill_id,
                "capability_id": skill_id.split(".", 1)[0],
                "role": "required" if record["relation"] == "REQUIRES" else "preferred",
            }
            edges.append(
                {
                    "id": f"e-root-{skill_id}",
                    "source": "root",
                    "target": skill_id,
                    "relation": record["relation"],
                }
            )
        return list(nodes.values()), edges


def _project_edges(session: Any, version_id: str, skills: Iterable[Any], relation: str) -> None:
    for item in skills:
        if isinstance(item, str):
            skill_id, label = item, item
        else:
            skill_id = str(item.get("skill_id", ""))
            label = str(item.get("name", skill_id))
        if not skill_id:
            continue
        label = label.replace("`", "")
        label = label or skill_id
        node_label = "SkillPoint" if "." in skill_id else "Capability"
        session.run(
            f"""
            MATCH (j:JobVersion {{version_id: $version_id}})
            MERGE (s:{node_label} {{skill_id: $skill_id}})
            SET s.name = $name
            MERGE (j)-[:{relation}]->(s)
            """,
            version_id=version_id,
            skill_id=skill_id,
            name=label,
        )
