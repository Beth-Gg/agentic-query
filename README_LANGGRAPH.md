# LangGraph SQL Query Agent

This project implements a LangGraph workflow for a smart SQL Query Agent that converts natural language queries into structured payloads for querying a PostgreSQL database.

## Overview

The SQL Query Agent processes natural language queries through multiple steps:

1. **Parse Query**: Identifies the relevant database tables needed for the query
2. **Extract Filters**: Identifies filter conditions based on the query text
3. **Generate Query Template**: Creates a SQL query template with parameterized filters
4. **Generate Metadata**: Creates visualization metadata based on the query structure
5. **Construct Payload**: Builds a complete JSON payload with all required fields
6. **Submit Payload**: Submits the payload to the API endpoint (simulated in this demo)

The workflow handles errors gracefully and provides detailed diagnostics when issues occur.

## Requirements

- Python 3.8+
- Required packages in requirements.txt

## Installation

1. Clone this repository
2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file with the following variables:

```
GEMINI_API_KEY=your_gemini_api_key  # Required for the Gemini LLM model
KFT_API_USERNAME=your_api_username  # For authentication with the visualization API
KFT_API_PASSWORD=your_api_password  # For authentication with the visualization API
```

## Usage

### Running the Command-Line Demo

```bash
python -m app.run_sql_agent
```

This will launch an interactive demo that allows you to:
- Select from sample queries
- Enter your own query
- See the generated SQL query template and payload

### Using the FastAPI Endpoint

The project also includes a FastAPI endpoint that you can use to process queries via HTTP:

Start the server:

```bash
uvicorn app.main:app --reload
```

Make a POST request to the endpoint:

```bash
curl -X POST "http://localhost:8000/langgraph-query/" \
     -H "Content-Type: application/json" \
     -d '{"query": "Show me total sales by product category"}'
```

## Examples

Here are some example queries you can try:

- "Show me the total sales by product category"
- "What are the top 5 customers by order value?"
- "List all orders placed in the last month with their total amounts"
- "What is the average order value per customer?"

## LangGraph Architecture

The workflow is implemented using LangGraph, a framework for building stateful multi-step AI applications. The workflow consists of:

- **Nodes**: Individual functions that perform specific tasks
- **Edges**: Connections between nodes that define the flow of execution
- **State**: A shared state object that is passed between nodes
- **Conditional Routing**: Logic to handle different execution paths based on state

## Customization

To customize this implementation:

1. Modify the `FILTER_VALUES` dictionary in `sql_agent_workflow.py` to match your database schema
2. Update the table structure descriptions in the prompts
3. Implement the actual API call in the `submit_payload` function
4. Add additional validation or processing steps as needed 