from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any, Optional, Annotated, Union
from pydantic import BaseModel, Field
import os
import json
import requests
from dotenv import load_dotenv
import logging
import google.generativeai as genai


# Load environment variables
load_dotenv()

# Define the state for our graph
class AgentState(TypedDict):
    # Input from user
    query: str
    # Extracted information
    target_tables: str
    filters: Dict[str, Any]
    # Generated query details
    query_template: str
    params_metadata: Dict[str, Any]
    groupby_options: Dict[str, Any]
    # Output payload
    payload: Dict[str, Any]
    # Final response
    response: Optional[Dict[str, Any]]
    # Error handling
    error: Optional[str]
    # Flow control
    next_step: str

# Known filter values
FILTER_VALUES = {
    "bank": ["Amhara", "Bunna", "Coop", "Enat", "Wegagen", "Zemzem"],
    "enterprise": ["Micro", "Nano", "Other loans"],
    "loan_products": ["ANSL", "Derash", "Ediget", "Fetan", "Maleda", "Melegna", "Meqenet", "Meri", 
                     "Michu-Kiyya-Micro", "Michu-Kiyya-Nano", "Rai", "SAME", "SASE"],
    "gender": ["Female", "Male", "Unknown"],
    "region": ["Addis Ababa", "Afar", "Amhara", "Benishangul Gumuz", "Central Ethiopia", 
               "Dire Dawa", "Gambela", "Harar", "Oromia", "Sidama", "SNNP", "Somali", "SWEP", "Tigray", "Unknown"],
    "sector": ["Agriculture", "Building and Construction", "Domestic Trade Service", "Healthcare", 
               "Manufacturing", "Retail", "Services", "Technology", "Other", "Unknown"],
    "area_type": ["Urban", "Pre-Urban", "Rural", "Unknown"],
    "age_group": ["Adult", "Youth"],
    "vulnerable_groups": ["Women", "Youth", "Disabled", "Unknown"],
    "migration_status": ["IDP", "Returnee", "Unknown"]
}

# Create LLM instance
# llm = ChatOpenAI(
#     model="gpt-3.5-turbo",
#     temperature=0,
#     api_key=os.getenv("OPENAI_API_KEY")
# )

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

# Configure the Gemini client
genai.configure(api_key=api_key)
llm = genai.GenerativeModel('gemini-2.0-flash')

# Node 1: Parse user query and identify tables
def parse_query(state: AgentState) -> AgentState:
    # """Extract target tables from user query"""
    
    # system_prompt = """
    # You are an expert at identifying relevant database tables for SQL queries.
    # Given a natural language query, identify which tables from the database are needed to answer it.
    # Consider relationships between tables and the specific information requested.
    # """
    
    # human_prompt = f"""
    # Given the following database tables:
    # - products: Information about products (id, name, category, price)
    # - customers: Customer information (id, name, email)
    # - orders: Order information (id, customer_id, order_date, total_amount)
    # - order_items: Items within orders (id, order_id, product_id, quantity, unit_price)
    
    # Identify which tables are needed to answer this query:
    # "{state['query']}"
    
    # Return ONLY a JSON list of table names, nothing else.
    # """
    
    # response = llm.invoke([
    #     {"role": "system", "content": system_prompt},
    #     {"role": "user", "content": human_prompt}
    # ])
    
    try:
    #     # Extract the JSON response
    #     content = response.content
    #     # Clean up the response if needed
    #     if "```json" in content:
    #         content = content.split("```json")[1].split("```")[0].strip()
    #     elif "```" in content:
    #         content = content.split("```")[1].strip()
            
    #     target_tables = json.loads(content)
        
    #     # Update state
        state["target_tables"] = 'full_data'
        state["next_step"] = "extract_filters"
        
    except Exception as e:
        state["error"] = f"Error parsing tables: {str(e)}"
        state["next_step"] = "handle_error"
    
    return state

# Node 2: Extract filters from query
def extract_filters(state: AgentState) -> AgentState:
    """Extract filter conditions from user query"""
    
    system_prompt = """
    You are an expert at identifying filter conditions in database queries.
    Given a natural language query, identify any filter conditions that should be applied.
    Focus on extracting specific values for parameters like banks, regions, sectors, etc.
    """
    
    human_prompt = f"""
    Given this natural language query:
    "{state['query']}"
    
    Extract all filter conditions that should be applied. Consider these common filter fields:
    {list(FILTER_VALUES.keys())}
    
    For each filter, identify if the query specifies a value that matches the known possible values:
    {json.dumps(FILTER_VALUES, indent=2)}
    
    Return a JSON object with filter names as keys and their values. For example:
    {{
      "region": "Addis Ababa",
      "gender": "Female"
    }}
    
    If no filters are specified, return an empty JSON object.
    """
    
    # Combine prompts for Gemini API
    combined_prompt = f"{system_prompt}\n\n{human_prompt}"
    
    response = llm.generate_content(combined_prompt)
    
    try:
        # Extract the JSON response
        content = response.text
        # Clean up the response if needed
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
            
        filters = json.loads(content)
        
        # Update state
        state["filters"] = filters
        state["next_step"] = "generate_query_template"
        
    except Exception as e:
        state["error"] = f"Error extracting filters: {str(e)}"
        state["next_step"] = "handle_error"
    
    return state

# Node 3: Generate SQL query template
def generate_query_template(state: AgentState) -> AgentState:
    """Generate SQL query template based on extracted information"""
    
    system_prompt = """
    You are an expert SQL developer for PostgreSQL databases.
    Your task is to convert natural language queries into SQL query templates.
    Create precise, efficient SQL that answers the user's question.
    """
    
    human_prompt = f"""
    Generate an SQL query template for this natural language query:
    "{state['query']}"
    
    Using these tables: {state['target_tables']}
    
    Applying these filters: {state['filters']}
    
    Consider these guidelines:
    1. Include appropriate JOINs between tables
    2. Use WHERE clauses for any filters
    3. Include GROUP BY if aggregations are needed
    4. Use appropriate ORDER BY clauses
    5. Use parameterized queries with placeholders like :param_name for filters
    
    Return ONLY the SQL query template as a string, nothing else.
    """
    
    # Combine prompts for Gemini API
    combined_prompt = f"{system_prompt}\n\n{human_prompt}"
    
    response = llm.generate_content(combined_prompt)
    
    try:
        query_template = response.text.strip()
        
        # Clean up the template if it contains markdown code blocks
        if query_template.startswith("```sql"):
            query_template = query_template.split("```sql")[1].split("```")[0].strip()
        elif query_template.startswith("```"):
            query_template = query_template.split("```")[1].split("```")[0].strip()
            
        # Update state
        state["query_template"] = query_template
        state["next_step"] = "generate_metadata"
        
    except Exception as e:
        state["error"] = f"Error generating query template: {str(e)}"
        state["next_step"] = "handle_error"
    
    return state

# Node 4: Generate metadata for visualization
def generate_metadata(state: AgentState) -> AgentState:
    """Generate metadata for visualization"""
    
    system_prompt = """
    You are an expert data visualization specialist.
    Your task is to determine the appropriate metadata for visualizing SQL query results.
    Focus on creating effective visualizations based on the query structure and data types.
    """
    
    human_prompt = f"""
    Based on this SQL query template:
    {state['query_template']}
    
    And this natural language query:
    "{state['query']}"
    
    Generate the following metadata to support visualization:
    
    1. params_metadata: Information about parameters used in the query.
       For each filter parameter, include:
       - data type (date, array, string, etc.)
       - possible values (use the predefined list if available)
    
    2. groupby_options: Fields that can be used for grouping in the visualization.
       For each groupby field, include the column name.
    
    Return a JSON object with these two properties:
    {{
      "params_metadata": {{ ... }},
      "groupby_options": {{ ... }}
    }}
    """
    
    # Combine prompts for Gemini API
    combined_prompt = f"{system_prompt}\n\n{human_prompt}"
    
    response = llm.generate_content(combined_prompt)
    
    try:
        # Extract the JSON response
        content = response.text
        # Clean up the response if needed
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
            
        metadata = json.loads(content)
        
        # Update state
        state["params_metadata"] = metadata.get("params_metadata", {})
        state["groupby_options"] = metadata.get("groupby_options", {})
        state["next_step"] = "construct_payload"
        
    except Exception as e:
        state["error"] = f"Error generating metadata: {str(e)}"
        state["next_step"] = "handle_error"
    
    return state

# Node 5: Construct final payload
def construct_payload(state: AgentState) -> AgentState:
    """Construct the final payload for the API"""
    
    system_prompt = """
    You are an expert at constructing structured payloads for database APIs.
    Your task is to build a complete payload for a SQL query API.
    Ensure all required fields are included and properly formatted.
    """
    
    human_prompt = f"""
    Construct a complete payload for the SQL query API with the following structure:
    
    {{
      "name": "string",
      "description": "string",
      "query_template": "string",
      "target_tables": ["string"],
      "params_metadata": {{}},
      "groupby_options": {{}},
      "chart_type": "category",
      "default_values": {{}},
      "result_display_types": {{}},
      "user_type": "string",
      "priority": 2147483647
    }}
    
    Use the following information:
    - Natural language query: "{state['query']}"
    - SQL query template: {state['query_template']}
    - Target tables: {state['target_tables']}
    - Filters: {state['filters']}
    - Params metadata: {state['params_metadata']}
    - Groupby options: {state['groupby_options']}
    
    Guidelines:
    1. Generate a descriptive name and explanation based on the query
    2. Set chart_type to "category" for categorical data, "time_series" for time-based data, or null if neither applies
    3. Include all filters in default_values
    4. Set result_display_types based on the type of visualization (bar, pie, area, etc.)
    5. Set user_type to "de" unless specified differently
    6. Set priority to a reasonable integer value
    
    Return a complete JSON object with all required fields.
    """
    
    # Combine prompts for Gemini API
    combined_prompt = f"{system_prompt}\n\n{human_prompt}"
    
    response = llm.generate_content(combined_prompt)
    
    try:
        # Extract the JSON response
        content = response.text
        # Clean up the response if needed
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
            
        payload = json.loads(content)
        
        # Update state
        state["payload"] = payload
        
        # Print the payload for debugging
        print("\n==== CONSTRUCTED PAYLOAD ====")
        print(json.dumps(state["payload"], indent=2))
        print("=============================\n")
        
        state["next_step"] = "submit_payload"
        
    except Exception as e:
        state["error"] = f"Error constructing payload: {str(e)}"
        state["next_step"] = "handle_error"
    
    return state
  
# Node 6: Submit payload to API endpoint
def submit_payload(state: AgentState) -> AgentState:
    """Submit the payload to the API endpoint"""
    try:
        # API endpoint
        api_url = "http://54.159.60.214/api/v1/kft-visualizer/query/rawqueries/"
        
        # Get authentication credentials from environment variables
        api_username = os.getenv("KFT_API_USERNAME")
        api_password = os.getenv("KFT_API_PASSWORD")
        
        # Setup headers and auth
        headers = {
            "Content-Type": "application/json"
        }
        
        logger = logging.getLogger(__name__)
        logger.info(f"Submitting payload to {api_url}")
        logger.debug(f"Payload: {json.dumps(state['payload'])}")
        
        print("\n==== SUBMITTING PAYLOAD TO API ====")
        print(f"URL: {api_url}")
        print(f"Using authentication: {bool(api_username and api_password)}")
        
        # Execute the actual API call with authentication if credentials are provided
        if api_username and api_password:
            logger.info("Using authentication for API call")
            response = requests.post(
                api_url, 
                json=state["payload"], 
                headers=headers,
                auth=(api_username, api_password)
            )
        else:
            logger.warning("No API credentials found, making unauthenticated request")
            response = requests.post(
                api_url, 
                json=state["payload"], 
                headers=headers
            )
        
        print(f"Response status code: {response.status_code}")
        
        # Process the API response
        if response.status_code == 200 or response.status_code == 201:
            # Success case
            response_data = response.json()
            
            print("\n==== API RESPONSE ====")
            print(json.dumps(response_data, indent=2)[:500] + "..." if len(json.dumps(response_data)) > 500 else json.dumps(response_data, indent=2))
            print("======================\n")
            
            state["response"] = {
                "status": "success",
                "message": "Payload submitted successfully",
                "api_response": response_data,
                "payload": state["payload"]
            }
            logger.info(f"API call successful: {response.status_code}")
            state["next_step"] = END
        else:
            # Error case
            error_message = f"API error: {response.status_code}"
            try:
                error_detail = response.json()
                error_message += f" - {json.dumps(error_detail)}"
                
                print("\n==== API ERROR RESPONSE ====")
                print(json.dumps(error_detail, indent=2))
                print("===========================\n")
                
            except:
                error_message += f" - {response.text}"
                
                print("\n==== API ERROR RESPONSE ====")
                print(response.text)
                print("===========================\n")
                
            logger.error(error_message)
            state["error"] = error_message
            state["next_step"] = "handle_error"
        
    except requests.RequestException as e:
        error_message = f"Network error: {str(e)}"
        logger.error(error_message)
        state["error"] = error_message
        state["next_step"] = "handle_error"
        
        print("\n==== NETWORK ERROR ====")
        print(str(e))
        print("=====================\n")
        
    except Exception as e:
        error_message = f"Error submitting payload: {str(e)}"
        logger.error(error_message)
        state["error"] = error_message
        state["next_step"] = "handle_error"
        
        print("\n==== GENERAL ERROR ====")
        print(str(e))
        print("=====================\n")
    
    return state

# Node 7: Handle errors
def handle_error(state: AgentState) -> AgentState:
    """Handle errors in the workflow"""
    
    print("\n==== ERROR ENCOUNTERED ====")
    print(f"Error: {state['error']}")
    print(f"Current state: query=\"{state['query']}\", tables={state.get('target_tables', '')}")
    print("==========================\n")
    
    system_prompt = """
    You are an expert troubleshooter for SQL query generation.
    Your task is to diagnose and explain errors that occurred during query processing.
    Provide clear explanations of what went wrong and suggest possible fixes.
    """
    
    human_prompt = f"""
    An error occurred during SQL query generation:
    
    Error: {state['error']}
    
    Current state:
    - Query: "{state['query']}"
    - Target tables: {state.get('target_tables', [])}
    - Filters: {state.get('filters', {})}
    - Query template: {state.get('query_template', '')}
    
    Provide:
    1. A diagnosis of what went wrong
    2. A clear explanation for the user
    3. Suggestions for fixing the issue
    
    Return your analysis as a JSON object with these properties.
    """
    
    # Combine prompts for Gemini API
    combined_prompt = f"{system_prompt}\n\n{human_prompt}"
    
    response = llm.generate_content(combined_prompt)
    
    try:
        # Extract the JSON response
        content = response.text
        # Clean up the response if needed
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
            
        error_analysis = json.loads(content)
        
        print("\n==== ERROR ANALYSIS ====")
        print(json.dumps(error_analysis, indent=2))
        print("=======================\n")
        
        # Update state
        state["response"] = {
            "status": "error",
            "error": state["error"],
            "diagnosis": error_analysis
        }
        state["next_step"] = END
        
    except Exception as e:
        # If error handling itself fails, provide a simple error message
        print(f"\n==== ERROR HANDLING FAILED ====")
        print(f"Error while handling original error: {str(e)}")
        print(f"Original error: {state['error']}")
        print(f"==========================\n")
        
        state["response"] = {
            "status": "error",
            "error": state["error"],
            "message": "An unexpected error occurred during query processing."
        }
        state["next_step"] = END
    
    return state

# Define the router function to determine the next step
def router(state: AgentState) -> str:
    return state["next_step"]

# Create and configure the graph
def create_sql_agent_graph() -> StateGraph:
    # Initialize the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("parse_query", parse_query)
    workflow.add_node("extract_filters", extract_filters)
    workflow.add_node("generate_query_template", generate_query_template)
    workflow.add_node("generate_metadata", generate_metadata)
    workflow.add_node("construct_payload", construct_payload)
    workflow.add_node("submit_payload", submit_payload)
    workflow.add_node("handle_error", handle_error)
    
    # Add edges
    workflow.add_edge("parse_query", "extract_filters")
    workflow.add_edge("extract_filters", "generate_query_template")
    workflow.add_edge("generate_query_template", "generate_metadata")
    workflow.add_edge("generate_metadata", "construct_payload")
    workflow.add_edge("construct_payload", "submit_payload")
    
    # Set entry point
    workflow.set_entry_point("parse_query")
    
    # Add conditional routing
    workflow.add_conditional_edges(
        "parse_query",
        router,
        {
            "extract_filters": "extract_filters",
            "handle_error": "handle_error"
        }
    )
    
    workflow.add_conditional_edges(
        "extract_filters",
        router,
        {
            "generate_query_template": "generate_query_template",
            "handle_error": "handle_error"
        }
    )
    
    workflow.add_conditional_edges(
        "generate_query_template",
        router,
        {
            "generate_metadata": "generate_metadata",
            "handle_error": "handle_error"
        }
    )
    
    workflow.add_conditional_edges(
        "generate_metadata",
        router,
        {
            "construct_payload": "construct_payload",
            "handle_error": "handle_error"
        }
    )
    
    workflow.add_conditional_edges(
        "construct_payload",
        router,
        {
            "submit_payload": "submit_payload",
            "handle_error": "handle_error"
        }
    )
    
    workflow.add_conditional_edges(
        "submit_payload",
        router,
        {
            END: END,
            "handle_error": "handle_error"
        }
    )
    
    workflow.add_edge("handle_error", END)
    
    return workflow.compile()

# Create a function to run the workflow
def process_sql_query(query: str) -> Dict[str, Any]:
    """
    Process a natural language query through the SQL agent workflow
    
    Args:
        query: Natural language query string
        
    Returns:
        Dict with the response from the workflow
    """
    # Create the graph
    graph = create_sql_agent_graph()
    
    # Initialize the state
    initial_state = AgentState(
        query=query,
        target_tables="FullData",  # Default to FullData table
        filters={},
        query_template="",
        params_metadata={},
        groupby_options={},
        payload={},
        response=None,
        error=None,
        next_step=""
    )
    
    # Execute the graph
    result = graph.invoke(initial_state)
    
    # Return the final response
    return result["response"] 