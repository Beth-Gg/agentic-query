# from openai import OpenAI
# import os
# from dotenv import load_dotenv
# import json

# load_dotenv()

# api_key = os.getenv("OPENAI_API_KEY")
# if not api_key:
#     raise ValueError("OPENAI_API_KEY environment variable is not set")

# client = OpenAI(
#     api_key=api_key,
# )

# def process_natural_language(query: str, table_schema: str) -> dict:
#     """
#     Convert natural language query to SQL using OpenAI's GPT model.
    
#     Args:
#         query (str): Natural language query
#         table_schema (str): Database schema information
    
#     Returns:
#         dict: Contains SQL query and visualization suggestions
#     """
#     prompt = f"""Given the following database schema:
#     {table_schema}
    
#     Convert this natural language query to SQL and suggest appropriate visualization:
#     "{query}"
    
#     Return the response in the following JSON format:
#     {{
#         "sql_query": "the SQL query",
#         "visualization": {{
#             "type": "suggested visualization type (bar, line, pie, scatter, etc.)",
#             "x_axis": "suggested x-axis column",
#             "y_axis": "suggested y-axis column(s)"
#         }}
#     }}
#     """
    
#     try:
#         response = client.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[
#                 {"role": "system", "content": "You are a SQL expert that converts natural language to SQL queries."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.1
#         )
        
#         result = response.choices[0].message.content
#         return json.loads(result)
#     except Exception as e:
#         return {"error": str(e)} 

import os
from dotenv import load_dotenv
import json
import google.generativeai as genai
from typing import List, Dict, Any, Tuple
import sqlparse
from sqlalchemy import text, inspect
from .models import Product, Customer, Order, OrderItem
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

# Configure the Gemini client
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

class QueryProcessor: 
    def __init__(self):
        self.table_schemas = {
            'products': {
                'columns': ['id', 'name', 'category', 'price', 'stock'],
                'relationships': {'order_items': 'one_to_many'}
            },
            'customers': {
                'columns': ['id', 'name', 'email', 'location'],
                'relationships': {'orders': 'one_to_many'}
            },
            'orders': {
                'columns': ['id', 'customer_id', 'order_date', 'total_amount', 'status'],
                'relationships': {
                    'customers': 'many_to_one',
                    'order_items': 'one_to_many'
                }
            },
            'order_items': {
                'columns': ['id', 'order_id', 'product_id', 'quantity', 'unit_price'],
                'relationships': {
                    'orders': 'many_to_one',
                    'products': 'many_to_one'
                }
            }
        }
        
        self.query_types = {
            'SELECT': ['show', 'display', 'list', 'what', 'how many', 'find', 'get'],
            'AGGREGATE': ['average', 'sum', 'total', 'count', 'maximum', 'minimum'],
            'GROUP': ['by', 'per', 'for each'],
            'ORDER': ['sort', 'order', 'arrange'],
            'FILTER': ['where', 'with', 'filter', 'only']
        }

    def extract_tables(self, query: str) -> List[str]:
        """Extract relevant tables from the natural language query."""
        prompt = f"""
        Given these available tables: {list(self.table_schemas.keys())}
        
        Identify which tables are needed to answer this query:
        "{query}"
        
        Return only a JSON array of table names, nothing else.
        """
        
        try:
            response = model.generate_content(prompt)
            # Clean up the response text to handle potential markdown formatting
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]  # Remove ```json and ```
            elif response_text.startswith('```'):
                response_text = response_text[3:-3]  # Remove ``` and ```
            
            tables = json.loads(response_text)
            return [table for table in tables if table in self.table_schemas]
        except Exception as e:
            logger.error(f"Error in extract_tables: {str(e)}")
            raise ValueError(f"Error extracting tables: {str(e)}")

    def classify_query_intent(self, query: str) -> Dict[str, bool]:
        """Classify the type of query and its components."""
        query = query.lower()
        return {
            'is_select': any(term in query for term in self.query_types['SELECT']),
            'is_aggregate': any(term in query for term in self.query_types['AGGREGATE']),
            'is_grouped': any(term in query for term in self.query_types['GROUP']),
            'is_ordered': any(term in query for term in self.query_types['ORDER']),
            'has_filter': any(term in query for term in self.query_types['FILTER'])
        }

    def suggest_visualization(self, query_intent: Dict[str, bool], sql_query: str) -> Dict[str, str]:
        """Suggest appropriate visualization based on query type and structure."""
        if query_intent['is_aggregate'] and query_intent['is_grouped']:
            return {
                "type": "bar",
                "x_axis": "group_by_column",
                "y_axis": "aggregate_value"
            }
        elif query_intent['is_aggregate']:
            return {
                "type": "number",
                "value": "aggregate_value"
            }
        elif 'ORDER BY' in sql_query.upper() and 'date' in sql_query.lower():
            return {
                "type": "line",
                "x_axis": "date",
                "y_axis": "value"
            }
        else:
            return {
                "type": "table",
                "columns": "all"
            }

    def validate_sql(self, sql_query: str) -> Tuple[bool, str]:
        """Validate the generated SQL query."""
        try:
            # Parse the SQL query
            parsed = sqlparse.parse(sql_query)
            if not parsed:
                return False, "Empty or invalid SQL query"
            
            # Basic syntax validation
            stmt = parsed[0]
            
            # Allow any valid SQL query that starts with SELECT
            if not stmt.get_type().upper() == 'SELECT':
                return False, "Query must start with SELECT"
            
            return True, "Valid query"
        except Exception as e:
            return False, f"Invalid SQL query: {str(e)}"

    def process_natural_language(self, query: str) -> Dict[str, Any]:
        """
        Enhanced natural language to SQL conversion with validation and visualization suggestions.
        """
        try:
            # 1. Extract relevant tables
            tables = self.extract_tables(query)
            if not tables:
                raise ValueError("No relevant tables identified for this query")

            # 2. Classify query intent
            query_intent = self.classify_query_intent(query)

            # 3. Generate SQL query
            prompt = f"""
You are a smart assistant that converts natural language queries into structured payloads for querying a PostgreSQL database via predefined SQL templates.
Your Task
For any natural language query from the user:
Take input from users (Text)
Identify key words like all required filters mentioned in the text (e.g., by sector, region, gender, loan product).
Identify the closest matching SQL query template 
Constract the payload as a JSON with the following structure:
 {{
  "name": "string",
  "description": "string",
  "query_template": "string",
  "target_tables": [
    "string"
  ],
  "params_metadata": {{}},
  "groupby_options": {{}},
  "chart_type": "category",
  "default_values": {{}},
  "result_display_types": {{}},
  "user_type": "string",
  "priority": 2147483647
 }}
Use known possible values for filters (from metadata). If a filter is unknown, ask the user to provide values.
Always include target_tables, even if there's only one.
Set result_display_types based on the type of chart being returned (bar, pie, area etc.).
Return both data and payload for visualization (plot) after execution.

Choosing Target Tables from the Database
You are tasked with converting natural language questions into SQL queries for MERL. The database is composed of well-structured tables related to customers, businesses, and loans. Here's how to select the right target tables:
How to Choose the Right Table(s)
Use keyword-to-table field mapping:
Match question terms to table and column names based on semantic meaning, not just exact string match. For instance, a query mentioning "total disbursed loans" may relate to CustomerLoan.disbursed_amount.
The important columns include:
loan_id, customer_id, business_id, disbursed_amount, disbursement_date, status, bank, region, sector, enterprise, loan_products, area_type, gender, age_group, vulnerable_groups, migration_status, business_establishment_year, business_current_no_of_employees
Determine the question intent:
Is the user asking about customers, loan repayments, business details, locations, or performance?
Examples:
"What is the average loan size?" → CustomerLoan
"Which businesses have the highest capital?" → CustomerBusiness
"How many repayments were late?" → InPaymentLatest or LoanRepayment
Leverage relationships:
Use foreign key relationships (e.g., customer_id, loan_id) to join related tables. For example:
Customer demographics → Customer, CustomerEducation, CustormerAddress, CustomerMaritalStatus, 
Loan behavior → CustomerLoan, LoanRepayment, LoanAccount, InPaymentLatest
Business performance → CustomerBusiness
Default to materialized or combined views when available:
Use materialized view by default go to table if the information can’t be found 
Use full_data materialized view for most of your task but if the table doesn’t satisfy the task look for there tables or materialized view for the queries. 
Use the bank, region, gender, loan_product, etc. as filters:
Common filters include columns like bank, region, loan_product_code, disbursement_date, etc.
Ensure you ask the user for possible values if the query includes unknown filter values.

Payload Structure Rules
name: generate a suitable title for the query that fits it correctly.
description: generate best explanation of what the plot is trying to display and information it conveys.
query_template: this is the converted sql queries from the text provided by the user.
target_tables: this is the name of the tables we use to extract the information asked. 
params_metadata: includes group and filter dictionary. In each one it takes info (date, array)  and possible values. Only use known values. If not known, ask the user.
groupby_options: it takes columns to be shown as x axis. It takes the group by field name and in that it contains a list of columns to be used as an x axis filter.
chart_type: can be null, category, or time_series.
default_values: Always include all filters with either selected or full options.
result_display_types: Use based on plot type required. Based on the need assign the result of the query to wither bar, area or pie accordingly.
user_type: ask the user which user they are preparing the data. 
category: can be null
Get the user types from this endpoint given provided the right credentials
http://54.159.60.214/api/v1/kft-visualizer/user/users/
priority: this is to assign order for the plots generated, with small numbers having high priority. Assign default values if not provided. 

Examples of Filters with Known possible_values
bank: ["Amhara", "Bunna", "Coop", "Enat", "Wegagen", "Zemzem"]
enterprise: ["Micro", "Nano", "Other loans"]
loan_products: ["ANSL", "Derash", "Ediget", "Fetan", "Maleda", "Melegna", "Meqenet", "Meri", "Michu-Kiyya-Micro", "Michu-Kiyya-Nano", "Rai", "SAME", "SASE"]
gender: ["Female", "Male", "Unknown"]
region: [ "Addis Ababa", "Afar", "Amhara", "Benishangul Gumuz", "Central Ethiopia", "Dire Dawa", "Gambela", "Harar", "Oromia", "Sidama", "SNNP", "Somali", "SWEP", "Tigray", "Unknown"]
sector: ["Agriculture", "Building and Construction", "Domestic Trade Service", "Healthcare", "Manufacturing", "Retail", "Services", "Technology", "Other", "Unknown"]
area_type: ["Urban", "Pre-Urban", "Rural", "Unknown"]
age_group: ["Adult", "Youth"]
vulnerable_groups: ["Women", "Youth", "Disabled", "Unknown"]
migration_status: ["IDP", "Returnee", "Unknown"]
How You Handle Unknown Filters
If the query includes a filter not listed above:
Ask the user:
“What are the possible values for [filter_name]?”
How You Return Results
After constructing and successfully generating the query and returned correct data submit the payload to this endpoint: 
http://54.159.60.214/api/v1/kft-visualizer/query/rawqueries/
Return both the result data and then send the payload to the endpoint and make sure it returns success if not ask the user again for missing fields or the reason for the error.

Your Behavior Summary
You are a structured query agent that:
Matches queries to templates.
Builds fully qualified payloads.
Validates and applies filters.
Outputs charts and data together.
Learns from existing structure but generalizes to future queries.

"""
            response = model.generate_content(prompt)
            sql_query = response.text.strip()
            
            # Remove any markdown formatting if present
            if sql_query.startswith('```sql'):
                sql_query = sql_query[6:-3]
            elif sql_query.startswith('```'):
                sql_query = sql_query[3:-3]
            
            sql_query = sql_query.strip()
            logger.info(f"Generated SQL query: {sql_query}")
            
            # 4. Validate the generated SQL
            is_valid, validation_message = self.validate_sql(sql_query)
            if not is_valid:
                raise ValueError(validation_message)

            # 5. Suggest visualization
            visualization = self.suggest_visualization(query_intent, sql_query)

            return {
                "sql_query": sql_query,
                "tables_used": tables,
                "query_intent": query_intent,
                "visualization": visualization
            }

        except Exception as e:
            logger.error(f"Error in process_natural_language: {str(e)}")
            return {
                "error": str(e),
                "query": query
            }

# Initialize the processor
query_processor = QueryProcessor()

def process_natural_language_query(query: str) -> Dict[str, Any]:
    """
    Public interface for processing natural language queries.
    """
    return query_processor.process_natural_language(query)

# Example queries
# result = process_natural_language_query("Show me total sales by category for last month")

# result = process_natural_language_query("What are the top 5 customers by order value?")
# result = process_natural_language_query("List all orders with their customer details")