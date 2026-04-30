MATCH (candidate:Person)-[:HAS_SKILL]->(:Skill {name: "Python"})
MATCH (candidate)-[:WORKED_ON]->(project:Project)<-[:WORKED_ON]-(:Person {name: "Alice"})
MATCH (project)-[:USES]->(:Technology {name: "Neo4j"})
RETURN candidate.name AS candidate, project.name AS project;
