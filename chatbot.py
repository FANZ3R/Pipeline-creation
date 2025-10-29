import streamlit as st
from neo4j import GraphDatabase
from openai import OpenAI
import re
import logging

# ========== CONFIG ==========
OPENROUTER_API_KEY = "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"

# UPDATE THESE WITH YOUR NEO4J CREDENTIALS
NEO4J_URI = "bolt://localhost:7687"  # Your local Docker Neo4j
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "your_secure_password"  # Your actual password

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== NEO4J CONNECTION ==========
@st.cache_resource
def init_neo4j_driver():
    """Initialize Neo4j driver with caching"""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        # Test connection
        with driver.session() as session:
            session.run("RETURN 1")
        logger.info("✅ Connected to Neo4j successfully")
        return driver
    except Exception as e:
        logger.error(f"❌ Failed to connect to Neo4j: {e}")
        st.error(f"Failed to connect to Neo4j: {e}")
        return None

driver = init_neo4j_driver()

def query_neo4j_advanced(question: str, limit: int = 15):
    """Enhanced Neo4j querying adapted for your Entity-based knowledge graph"""
    if not driver:
        return []
    
    # Multiple query strategies for better results
    queries = []
    
    # Strategy 1: Direct entity text search with relationships
    queries.append({
        "name": "Direct Entity Search",
        "cypher": """
        MATCH (source:Entity)-[r]->(target:Entity)
        WHERE source.text IS NOT NULL 
          AND target.text IS NOT NULL
          AND toString(source.text) <> 'NaN'
          AND toString(target.text) <> 'NaN'
          AND (toLower(toString(source.text)) CONTAINS toLower($q) 
               OR toLower(toString(target.text)) CONTAINS toLower($q))
        RETURN source.text AS source_entity, 
               type(r) AS relationship, 
               target.text AS target_entity,
               r.confidence AS confidence,
               source.label AS source_type,
               target.label AS target_type
        ORDER BY r.confidence DESC
        LIMIT $limit
        """,
        "format": lambda record: f"{record['source_entity']} --[{record['relationship']}]--> {record['target_entity']} (confidence: {record.get('confidence', 0.0):.2f})"
    })
    
    # Strategy 2: Multi-word search (split query into keywords)
    queries.append({
        "name": "Keyword-based Search",
        "cypher": """
        MATCH (source:Entity)-[r]->(target:Entity)
        WHERE source.text IS NOT NULL 
          AND target.text IS NOT NULL
          AND toString(source.text) <> 'NaN'
          AND toString(target.text) <> 'NaN'
          AND (any(word IN split(toLower($q), ' ') WHERE 
               word <> '' AND size(word) > 2 AND
               (toLower(toString(source.text)) CONTAINS word OR 
                toLower(toString(target.text)) CONTAINS word)))
        RETURN source.text AS source_entity, 
               type(r) AS relationship, 
               target.text AS target_entity,
               r.confidence AS confidence,
               source.label AS source_type,
               target.label AS target_type
        ORDER BY r.confidence DESC
        LIMIT $limit
        """,
        "format": lambda record: f"{record['source_entity']} --[{record['relationship']}]--> {record['target_entity']}"
    })
    
    # Strategy 3: Entity neighborhood exploration
    queries.append({
        "name": "Entity Neighborhood",
        "cypher": """• [Entity Neighborhood] Center: Active supplier risk management → resiliency via RELATED → management
• [High Confidence] ⭐ The supplier risk management framework --[RELATED]--> a high level (confidence: 1.00)
• [Direct Entity Search] } Supplier Risk Management Framework Potential Risks Stages --[RELATED]--> modified_time.split("T")[0 (confidence: 1.00)
• [Entity Neighborhood] Center: Active supplier risk management → supply chain efficiency via RELATED → resiliency
• [Direct Entity Search] supplier risk management --[RELATED]--> supplier (confidence: 0.90)
• [Entity Neighborhood] Center: Active supplier risk management → resiliency via RELATED → supplier
• [Keyword-based Search] suppliers --[RELATED]--> contractual obligations
• [High Confidence] ⭐ supplier risk management --[RELATED]--> supplier (confidence: 0.90)
• [Direct Entity Search] supplier risk management --[RELATED]--> business tensions (confidence: 1.00)
        MATCH (center:Entity)
        WHERE center.text IS NOT NULL 
          AND toString(center.text) <> 'NaN'
          AND toLower(toString(center.text)) CONTAINS toLower($q)
        MATCH (center)-[r1]-(neighbor:Entity)
        WHERE neighbor.text IS NOT NULL 
          AND toString(neighbor.text) <> 'NaN'
        OPTIONAL MATCH (neighbor)-[r2]-(second_neighbor:Entity)
        WHERE second_neighbor.text IS NOT NULL 
          AND toString(second_neighbor.text) <> 'NaN'
          AND second_neighbor <> center
        RETURN center.text AS main_entity,
               neighbor.text AS connected_entity,
               type(r1) AS relationship,
               neighbor.label AS connected_type,
               second_neighbor.text AS extended_entity
        LIMIT $limit
        """,
        "format": lambda record: f"Center: {record['main_entity']} → {record['connected_entity']} via {record['relationship']}" + (f" → {record['extended_entity']}" if record.get('extended_entity') else "")
    })
    
    # Strategy 4: High-confidence relationships only
    queries.append({
        "name": "High Confidence",
        "cypher": """
        MATCH (source:Entity)-[r]->(target:Entity)
        WHERE source.text IS NOT NULL 
          AND target.text IS NOT NULL
          AND toString(source.text) <> 'NaN'
          AND toString(target.text) <> 'NaN'
          AND r.confidence > 0.7
          AND (toLower(toString(source.text)) CONTAINS toLower($q) 
               OR toLower(toString(target.text)) CONTAINS toLower($q))
        RETURN source.text AS source_entity, 
               type(r) AS relationship, 
               target.text AS target_entity,
               r.confidence AS confidence
        ORDER BY r.confidence DESC
        LIMIT $limit
        """,
        "format": lambda record: f"⭐ {record['source_entity']} --[{record['relationship']}]--> {record['target_entity']} (confidence: {record['confidence']:.2f})"
    })
    
    all_facts = []
    
    with driver.session() as session:
        for query_info in queries:
            try:
                results = session.run(query_info["cypher"], q=question, limit=limit)
                facts = []
                for record in results:
                    formatted_fact = query_info["format"](record)
                    facts.append(formatted_fact)
                
                if facts:
                    all_facts.extend([f"[{query_info['name']}] {fact}" for fact in facts])
                    
            except Exception as e:
                logger.warning(f"Query '{query_info['name']}' failed: {e}")
                continue
    
    return list(set(all_facts))  # Remove duplicates

def get_entity_statistics():
    """Get basic statistics about the knowledge graph"""
    if not driver:
        return {}
    
    with driver.session() as session:
        try:
            # Get basic counts
            result = session.run("""
                MATCH (n:Entity)
                WHERE n.text IS NOT NULL AND toString(n.text) <> 'NaN'
                OPTIONAL MATCH (n)-[r]-()
                RETURN count(DISTINCT n) as total_entities,
                       count(r) as total_relationships,
                       count(DISTINCT n.label) as entity_types
            """)
            stats = result.single()
            
            # Get top entity types
            result = session.run("""
                MATCH (n:Entity)
                WHERE n.text IS NOT NULL AND toString(n.text) <> 'NaN'
                RETURN n.label as type, count(*) as count
                ORDER BY count DESC
                LIMIT 5
            """)
            top_types = [(record["type"], record["count"]) for record in result]
            
            return {
                "total_entities": stats["total_entities"],
                "total_relationships": stats["total_relationships"],
                "entity_types": stats["entity_types"],
                "top_entity_types": top_types
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

# ========== OPENROUTER CLIENT ==========
@st.cache_resource
def init_openai_client():
    """Initialize OpenAI client with caching"""
    return OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )

client = init_openai_client()

# -------- Enhanced keyword extraction --------
def extract_keywords_simple(question: str):
    """Simple keyword extraction with domain-specific terms"""
    stopwords = {
        "what", "is", "a", "an", "the", "who", "where", "when", "why", "how",
        "in", "of", "and", "to", "for", "with", "by", "from", "up", "about",
        "into", "through", "during", "before", "after", "above", "below",
        "do", "does", "are", "was", "were", "been", "have", "has", "had",
        "will", "would", "could", "should", "may", "might", "can", "?", "!",
        "tell", "me", "show", "find", "get", "give"
    }
    
    # Extract words and clean
    words = re.findall(r'\w+', question.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 2]
    
    # Join with space for broad matching
    return " ".join(keywords)

def extract_keywords_llm(question: str):
    """LLM-assisted keyword extraction with domain focus"""
    prompt = f"""
    Extract the most important search keywords from this question for querying a knowledge graph about business, suppliers, risk management, and organizational data.
    
    Focus on:
    - Key business concepts and entities
    - Names of organizations, people, or systems
    - Process names and technical terms
    - Risk-related terminology
    
    Question: {question}
    
    Return only the essential keywords separated by spaces (no explanations):
    """
    
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM keyword extraction failed: {e}")
        return extract_keywords_simple(question)  # Fallback

def generate_answer(question: str, context: list):
    """Generate answer using Llama3 model with enhanced prompting"""
    if not context:
        context_text = "No relevant facts found in the knowledge graph."
    else:
        context_text = "\n".join(context[:20])  # Limit context to avoid token limits
    
    prompt = f"""
You are an AI assistant with access to a comprehensive knowledge graph containing information about business processes, supplier relationships, risk management, organizations, and related business concepts.

User Question: {question}

Knowledge Graph Facts:
{context_text}

Instructions:
1. If the graph facts directly answer the question, provide a clear, comprehensive response based on those facts.
2. If the facts are partially relevant, use them to provide the best possible answer and explain what information is available.
3. If the facts contain relationships or connections, explain how the entities are related.
4. If no relevant facts are found, suggest alternative ways to phrase the question or related topics that might be in the knowledge graph.
5. Always cite specific facts when possible (e.g., "According to the knowledge graph, X is connected to Y through Z relationship").

Keep your response informative but concise.
"""
    
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Answer generation failed: {e}")
        return f"I encountered an error while generating the response: {e}"

# ========== STREAMLIT UI ==========
st.set_page_config(
    page_title="Knowledge Graph RAG Chatbot", 
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Knowledge Graph RAG Chatbot")
st.caption("Ask questions about your business knowledge graph")

# Sidebar with statistics
if driver:
    with st.sidebar:
        st.header("📊 Graph Statistics")
        with st.spinner("Loading statistics..."):
            stats = get_entity_statistics()
        
        if stats:
            st.metric("Total Entities", f"{stats.get('total_entities', 0):,}")
            st.metric("Total Relationships", f"{stats.get('total_relationships', 0):,}")
            st.metric("Entity Types", stats.get('entity_types', 0))
            
            if stats.get('top_entity_types'):
                st.subheader("Top Entity Types")
                for entity_type, count in stats['top_entity_types']:
                    st.text(f"• {entity_type}: {count:,}")
        
        st.subheader("💡 Try asking about:")
        st.text("• Supplier risk management")
        st.text("• Risk assessment processes")
        st.text("• Organizational relationships")
        st.text("• Business processes")
        st.text("• Compliance procedures")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Chat input
user_input = st.chat_input("Ask me about the knowledge graph...")

if user_input and driver:
    # Save user input
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.spinner("Searching knowledge graph..."):
        # Try simple keyword extraction first
        processed_query = extract_keywords_simple(user_input)
        st.info(f"🔍 Searching for: {processed_query}")
        
        context = query_neo4j_advanced(processed_query)
        
        # If nothing found, try LLM-assisted keyword extraction
        if not context:
            st.info("No direct matches found. Trying enhanced keyword extraction...")
            processed_query = extract_keywords_llm(user_input)
            st.info(f"🔍 Enhanced search: {processed_query}")
            context = query_neo4j_advanced(processed_query)
    
    with st.spinner("Generating response..."):
        # Generate answer
        answer = generate_answer(user_input, context)
    
    # Save bot answer
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    
    # Show found context in expander
    if context:
        with st.expander(f"📋 Found {len(context)} relevant facts from knowledge graph"):
            for fact in context[:10]:  # Show first 10 facts
                st.text(f"• {fact}")

elif user_input and not driver:
    st.error("Cannot process questions - Neo4j connection failed. Please check your configuration.")

# Display the chat
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Connection status
if not driver:
    st.error("⚠️ Neo4j connection failed. Please check your Neo4j configuration and ensure the database is running.")
    st.text("Troubleshooting:")
    st.text("1. Make sure your Neo4j Docker container is running")
    st.text("2. Verify the connection URI and credentials")
    st.text("3. Check if port 7687 is accessible")
else:
    st.success("✅ Connected to Neo4j knowledge graph")