import os
from dotenv import load_dotenv
from sql_agent_workflow import process_sql_query
import json

# Load environment variables
load_dotenv()

def main():
    """Run the SQL Query Agent with a sample query"""
    
    # Example natural language queries
    sample_queries = [
        "Show me the total sales by product category",
        "What are the top 5 customers by order value?",
        "List all orders placed in the last month with their total amounts",
        "What is the average order value per customer?"
    ]
    
    print("SQL Query Agent Demo")
    print("===================")
    
    # Allow user to select a sample query or enter their own
    print("\nSample queries:")
    for i, query in enumerate(sample_queries):
        print(f"{i+1}. {query}")
    print(f"{len(sample_queries)+1}. Enter your own query")
    
    choice = input("\nSelect an option (1-5): ")
    
    try:
        choice_num = int(choice)
        if 1 <= choice_num <= len(sample_queries):
            query = sample_queries[choice_num-1]
        elif choice_num == len(sample_queries)+1:
            query = input("\nEnter your query: ")
        else:
            print("Invalid choice. Using the first sample query.")
            query = sample_queries[0]
    except ValueError:
        print("Invalid choice. Using the first sample query.")
        query = sample_queries[0]
    
    print(f"\nProcessing query: \"{query}\"\n")
    print("This may take a moment...\n")
    
    # Process the query
    result = process_sql_query(query)
    
    # Display the results
    print("\nResults:")
    print("========")
    
    if result.get("status") == "success":
        print("\n Query processed successfully!\n")
        
        payload = result.get("payload", {})
        
        print(f"Name: {payload.get('name', 'N/A')}")
        print(f"Description: {payload.get('description', 'N/A')}")
        print(f"Chart type: {payload.get('chart_type', 'N/A')}")
        
        print("\nSQL Query Template:")
        print("-----------------")
        print(payload.get("query_template", "N/A"))
        
        print("\nTarget Tables:")
        print("-------------")
        if isinstance(payload.get("target_tables"), list):
            for table in payload.get("target_tables", []):
                print(f"- {table}")
        else:
            print(f"- {payload.get('target_tables', 'N/A')}")
        
        # Display API response if available
        if "api_response" in result:
            print("\nAPI Response:")
            print("------------")
            api_response = result.get("api_response", {})
            
            # Try to extract relevant information from the API response
            if isinstance(api_response, dict):
                if "status" in api_response:
                    print(f"Status: {api_response.get('status')}")
                if "message" in api_response:
                    print(f"Message: {api_response.get('message')}")
                if "id" in api_response:
                    print(f"Query ID: {api_response.get('id')}")
                if "created_at" in api_response:
                    print(f"Created at: {api_response.get('created_at')}")
            else:
                # If it's not a dict, just print it
                print(api_response)
            
        # Pretty print the full payload
        print("\nFull Payload:")
        print("-----------")
        print(json.dumps(payload, indent=2))
        
    else:
        print("\nError processing query:\n")
        print(f"Error: {result.get('error', 'Unknown error')}")
        
        if "diagnosis" in result:
            diagnosis = result["diagnosis"]
            print("\nDiagnosis:")
            print("---------")
            
            if isinstance(diagnosis, dict):
                for key, value in diagnosis.items():
                    print(f"{key.capitalize()}: {value}")
            else:
                print(diagnosis)

if __name__ == "__main__":
    main() 