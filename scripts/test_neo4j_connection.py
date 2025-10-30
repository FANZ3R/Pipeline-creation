#!/usr/bin/env python3
"""
Neo4j Connection Tester
Tests different Neo4j connection configurations to find the working one
"""

from neo4j import GraphDatabase
import sys

def test_connection(uri, username, password):
    """Test a Neo4j connection"""
    print(f"Testing: {uri}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            test_value = result.single()['test']

            print(f"✅ SUCCESS! Connection works!")

            # Get Neo4j version
            try:
                result = session.run("CALL dbms.components() YIELD name, versions, edition")
                for record in result:
                    print(f"   Version: {record['versions'][0]}")
                    print(f"   Edition: {record['edition']}")
            except:
                pass

            # Count nodes
            try:
                result = session.run("MATCH (n) RETURN count(n) as count")
                count = result.single()['count']
                print(f"   Total nodes: {count:,}")
            except:
                pass

            driver.close()
            return True

    except Exception as e:
        print(f"❌ FAILED: {str(e)[:100]}")
        return False

    print()


def main():
    print("="*80)
    print("NEO4J CONNECTION TESTER")
    print("="*80)
    print()

    # Test common configurations
    configs = [
        {"uri": "bolt://localhost:7688", "username": "neo4j", "password": "test12345"},
        {"uri": "bolt://localhost:7687", "username": "neo4j", "password": "test12345"},
        {"uri": "bolt://localhost:7688", "username": "neo4j", "password": "password"},
        {"uri": "bolt://localhost:7687", "username": "neo4j", "password": "password"},
        {"uri": "bolt://localhost:7688", "username": "neo4j", "password": "neo4j"},
    ]

    working_config = None

    for i, config in enumerate(configs, 1):
        print(f"\n[Test {i}/{len(configs)}]")
        success = test_connection(**config)
        if success:
            working_config = config
            break
        print("-" * 80)

    print("\n" + "="*80)

    if working_config:
        print("✅ WORKING CONFIGURATION FOUND!")
        print("="*80)
        print()
        print("Use this command to import:")
        print()
        print(f"python scripts/import_csv_to_neo4j.py \\")
        print(f"  --entities data/output/entities/entities_20251029_191434.csv \\")
        print(f"  --relationships data/output/relationships/relationships_20251029_191434.csv \\")
        print(f"  --uri {working_config['uri']} \\")
        print(f"  --username {working_config['username']} \\")
        print(f"  --password {working_config['password']} \\")
        print(f"  --batch-size 10000 \\")
        print(f"  --confidence 0.6")
        print()
        return 0
    else:
        print("❌ NO WORKING CONFIGURATION FOUND")
        print("="*80)
        print()
        print("Troubleshooting steps:")
        print()
        print("1. Check if Neo4j is running:")
        print("   docker ps | grep neo4j")
        print("   OR check Neo4j Desktop application")
        print()
        print("2. Check Neo4j logs:")
        print("   docker logs <container-name>")
        print()
        print("3. Try accessing Neo4j Browser:")
        print("   http://localhost:7474")
        print("   http://localhost:7688")
        print()
        print("4. Reset Neo4j password:")
        print("   - Stop Neo4j")
        print("   - Start with: docker run --rm neo4j:5.13.0 neo4j-admin set-initial-password test12345")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
