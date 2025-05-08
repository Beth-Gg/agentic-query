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

COLUMN_NAMES = ['loan_id', 'customer_id', 'business_id', 'disbursed_amount', 'disbursement_date', 'status', 'bank', 'region', 'sector', 'enterprise', 'loan_products', 'area_type', 'gender', 'age_group', 'vulnerable_groups', 'migration_status', 'business_establishment_year', 'business_current_no_of_employees']

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

genai.configure(api_key=api_key)
llm = genai.GenerativeModel('gemini-2.0-flash')

# Node 1: Parse user query and identify tables
def parse_query(state: AgentState) -> AgentState:   
    try:

        state["target_tables"] = 'full_data'
        state["next_step"] = "extract_filters"
        
    except Exception as e:
        state["error"] = f"Error parsing tables: {str(e)}"
        state["next_step"] = "handle_error"
    
    return state

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
    Generate an SQL query for this natural language query and make sure the SQL query is syntactically and logically correct:
    "{state['query']}"
    
    Using this table: {state['target_tables']}
    
    Applying these filters: {state['filters']}
    
    Using these columns: {COLUMN_NAMES}
    
    Consider these guidelines:
    1. Use WHERE clauses for any filters
    2. Include GROUP BY if aggregations are needed
    3. Use appropriate ORDER BY clauses
    4. For array filters, ALWAYS use the syntax: filter_column = ANY(%(filter_name)s)
       Example: bank = ANY(%(bank)s) AND gender = ANY(%(gender)s)
    5. For date filters, use: date_column >= %(start_date)s AND date_column <= %(end_date)s
    6. All string comparison operators should use the exact column names
    7. Make sure to create meaningful column aliases for aggregated values
    
    Return ONLY the SQL query template as a string, nothing else.
    """
    
    # Combine prompts for Gemini API
    combined_prompt = f"{system_prompt}\n\n{human_prompt}"
    
    response = llm.generate_content(combined_prompt)
    
    try:
        # Extract the response
        content = response.text
        # Clean up the response if needed
        if "```sql" in content:
            content = content.split("```sql")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
            
        sql_query = content.strip()
        
        # Update state
        state["query_template"] = sql_query
        state["next_step"] = "generate_metadata"
        
    except Exception as e:
        state["error"] = f"Error generating SQL query: {str(e)}"
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

def generate_query_name(user_query: str) -> str:
    """Generate a descriptive name for the query based on the user query."""
    # Create a descriptive name from the user query
    query = user_query.strip()
    
    # Remove question marks and standardize the format
    query = query.replace("?", "").strip()
    
    # If query starts with "what is", replace it with a more descriptive prefix
    if query.lower().startswith("what is"):
        query = query[8:].strip()
        return f"Analysis of {query}"
    elif query.lower().startswith("show me"):
        query = query[7:].strip()
        return f"Analysis of {query}"
    elif query.lower().startswith("calculate"):
        query = query[9:].strip()
        return f"Calculation of {query}"
    
    # Capitalize the first letter of each word for Title Case
    words = query.split()
    return " ".join(words).title()

# Node 5: Construct final payload
def construct_payload(state: AgentState) -> AgentState:
    """Construct the final payload for the API"""
    
    # First, get the query details to determine the right payload structure
    system_prompt = """
    You are an expert at analyzing SQL queries.
    Your task is to extract key information from a SQL query to create an appropriate visualization.
    Focus on identifying the main metric, the appropriate grouping, and visualization type.
    """
    
    human_prompt = f"""
    Given this natural language query: "{state['query']}"
    And this SQL query: {state['query_template']}
    
    Please provide the following information:
    
    1. A concise, descriptive name for this query (e.g., "Average Loan Maturity")
    2. A brief description explaining what this query calculates or shows (e.g., "Calculates the average loan duration (in days) for each loan product type")
    3. The most appropriate visualization type for the result (one of: "bar", "line", "pie", "area")
    4. The main metric column name from the SQL query (e.g., "Average_Loan_Duration")
    5. The table being queried (e.g., "full_data_inpaymentlatest")
    
    Return a JSON object with these properties.
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
            
        query_analysis = json.loads(content)
        
        # Extract the information
        query_name = query_analysis.get("name") or generate_query_name(state["query"])
        query_description = query_analysis.get("description", "Analysis of database information")
        visualization_type = query_analysis.get("visualization_type", "bar")
        metric_name = query_analysis.get("main_metric", "Value")
        table_name = query_analysis.get("table", "full_data_inpaymentlatest")
        
        payload = {
            "name": query_name,
            "description": query_description,
            "query_template": state["query_template"],
            "target_tables": [
                table_name
            ],
            "params_metadata": {
                "group": {
                    "groupby_fields": {
                        "info": [
                            "scalar",
                            "String"
                        ],
                        "possible_values": [
                            "bank",
                            "sector",
                            "gender",
                            "region",
                            "age_range",
                            "product_type",
                            "education_level",
                            "migration_status",
                            "vulnerable_groups"
                        ]
                    }
                },
                "filter": {
                    "bank": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "Amhara",
                            "Bunna",
                            "Coop",
                            "Enat",
                            "Wegagen",
                            "Zemzem"
                        ]
                    },
                    "product_type": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "15 days loan",
                            "30 days loan"
                        ]
                    },
                    "gender": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "Female",
                            "Male",
                            "Unknown"
                        ]
                    },
                    "region": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "Addis Ababa",
                            "Afar",
                            "Amhara",
                            "Benishangul Gumuz",
                            "Central Ethiopia",
                            "Dire Dawa",
                            "Gambela",
                            "Harar",
                            "Oromia",
                            "Sidama",
                            "SNNP",
                            "Somali",
                            "SWEP",
                            "Tigray",
                            "Unknown"
                        ]
                    },
                    "sector": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "Agriculture",
                            "Building and Construction",
                            "Domestic Trade Service",
                            "Healthcare",
                            "Manufacturing",
                            "Retail",
                            "Services",
                            "Technology",
                            "Other",
                            "Unknown"
                        ]
                    },
                    "age_range": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "18-24",
                            "25-30",
                            "31-35",
                            "36-40",
                            "45+"
                        ]
                    },
                    "area_type": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "Urban",
                            "Pre-Urban",
                            "Rural",
                            "Unknown"
                        ]
                    },
                    "loan_products": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "ANSL",
                            "Derash",
                            "Ediget",
                            "Fetan",
                            "Maleda",
                            "Melegna",
                            "Meqenet",
                            "Meri",
                            "Michu-Kiyya-Micro",
                            "Michu-Kiyya-Nano",
                            "Rai",
                            "SAME",
                            "SASE"
                        ]
                    },
                    "migration_status": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "IDP",
                            "Returnee",
                            "Unknown"
                        ]
                    },
                    "vulnerable_groups": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "Disabled",
                            "Women",
                            "Youth",
                            "Unknown"
                        ]
                    },
                    "education_level": {
                        "info": [
                            "array",
                            "String"
                        ],
                        "possible_values": [
                            "Primary",
                            "Diploma",
                            "Bachelor Degree",
                            "Masters Degree",
                            "PhD and Above"
                        ]
                    },
                    "start_date": {
                        "info": [
                            "scalar",
                            "Date"
                        ],
                        "possible_values": []
                    },
                    "end_date": {
                        "info": [
                            "scalar",
                            "Date"
                        ],
                        "possible_values": []
                    }
                }
            },
            "groupby_options": {
                "groupby_fields": [
                    "bank",
                    "sector",
                    "gender",
                    "region",
                    "age_range",
                    "product_type",
                    "education_level",
                    "migration_status",
                    "vulnerable_groups"
                ]
            },
            "chart_type": "category",
            "default_values": {
                "start_date": "2020-01-01",
                "end_date": "2030-01-01",
                "bank": [
                    "Amhara",
                    "Bunna",
                    "Coop",
                    "Enat",
                    "Wegagen",
                    "Zemzem"
                ],
                "gender": [
                    "Female",
                    "Male",
                    "Unknown"
                ],
                "region": [
                    "Addis Ababa",
                    "Afar",
                    "Amhara",
                    "Benishangul Gumuz",
                    "Central Ethiopia",
                    "Dire Dawa",
                    "Gambela",
                    "Harar",
                    "Oromia",
                    "Sidama",
                    "SNNP",
                    "Somali",
                    "SWEP",
                    "Tigray",
                    "Unknown"
                ],
                "sector": [
                    "Agriculture",
                    "Building and Construction",
                    "Domestic Trade Service",
                    "Healthcare",
                    "Manufacturing",
                    "Retail",
                    "Services",
                    "Technology",
                    "Other",
                    "Unknown"
                ],
                "age_range": [
                    "18-24",
                    "25-30",
                    "31-35",
                    "36-40",
                    "45+"
                ],
                "area_type": [
                    "Urban",
                    "Pre-Urban",
                    "Rural",
                    "Unknown"
                ],
                "product_type":[
                    "15 days loan",
                    "30 days loan"
                ],
                "loan_products": [
                    "ANSL",
                    "Derash",
                    "Ediget",
                    "Fetan",
                    "Maleda",
                    "Melegna",
                    "Meqenet",
                    "Meri",
                    "Michu-Kiyya-Micro",
                    "Michu-Kiyya-Nano",
                    "Rai",
                    "SAME",
                    "SASE"
                ],
                "migration_status": [
                    "IDP",
                    "Returnee",
                    "Unknown"
                ],
                "vulnerable_groups": [
                    "Disabled",
                    "Women",
                    "Youth",
                    "Unknown"
                ],
                "education_level": [
                    "Primary",
                    "Diploma",
                    "Bachelor Degree",
                    "Masters Degree",
                    "PhD and Above"
                ],
                "groupby_fields": "bank"
            },
            "result_display_types": {
                metric_name: "bar"
            },
            "dashboard_type": "cpm",
            "user_type": "TLF_USER",
            "priority": 1
        }
        
        # Update state with the final payload
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
        
        # Get authentication tokens from environment variables
        bearer_token = os.getenv("KFT_BEARER_TOKEN")  # Access/Bearer token
        refresh_token = os.getenv("KFT_REFRESH_TOKEN")  # Refresh token
        
        logger = logging.getLogger(__name__)
        logger.info(f"Submitting payload to {api_url}")
        
        # First, check if we have credentials
        if not bearer_token:
            print("\n⚠️ WARNING: No bearer token found!")
            print("Set KFT_BEARER_TOKEN in your .env file.")
            print("Attempting request without authentication, which will likely fail...\n")
        
        # Setup headers based on available auth method
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add token authentication
        if bearer_token:
            # Token-based auth (Bearer token)
            headers["Authorization"] = f"Bearer {bearer_token}"
            print("\n==== SUBMITTING PAYLOAD TO API WITH BEARER TOKEN ====")
            print(f"URL: {api_url}") 
            logger.info("Using bearer token authentication for API call")
            
            response = requests.post(
                api_url, 
                json=state["payload"], 
                headers=headers
            )
            
            # Check if token expired (typically 401 response)
            if response.status_code == 401 and refresh_token:
                print("Bearer token appears to be expired. Attempting to refresh...")
                
                # Here we would normally implement token refresh logic
                # For example:
                # new_token = refresh_auth_token(refresh_token)
                # if new_token:
                #     headers["Authorization"] = f"Bearer {new_token}"
                #     response = requests.post(api_url, json=state["payload"], headers=headers)
                
                # For now, we'll just simulate this with a message
                print(" Token refresh not implemented. Please update your KFT_BEARER_TOKEN manually.")
        else:
            # No auth as fallback
            print("\n==== SUBMITTING PAYLOAD TO API WITHOUT AUTH ====")
            print(f"URL: {api_url}")
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