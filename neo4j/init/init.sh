#!/bin/bash
# Wait for Neo4j to be ready then run seed Cypher
echo "Waiting for Neo4j..."
until cypher-shell -u neo4j -p viralpass123 "RETURN 1" 2>/dev/null; do
  sleep 3
done
echo "Neo4j ready. Running seed..."
cypher-shell -u neo4j -p viralpass123 --file /docker-entrypoint-initdb.d/seed.cypher || true
echo "Seed complete."
