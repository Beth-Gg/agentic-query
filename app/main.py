from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# from sqlalchemy.orm import Session
from typing import Dict, Any
import pandas as pd
import plotly.express as px
from pydantic import BaseModel
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .sql_agent_workflow import process_sql_query
app = FastAPI(title="Natural Language to SQL API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str


@app.post("/langgraph-query/")
async def process_langgraph_query(request: QueryRequest) -> Dict[str, Any]:
    """Process a query using the LangGraph workflow"""
    try:
        logger.info(f"Processing query with LangGraph: {request.query}")
        
        # Process using LangGraph workflow
        result = process_sql_query(request.query)
        
        if not result:
            logger.error("LangGraph query returned empty result")
            raise HTTPException(status_code=500, detail="LangGraph workflow returned an empty result")
            
        # Log a truncated version of the result for debugging
        result_str = str(result)
        logger.info(f"LangGraph query result type: {type(result)}")
        logger.info(f"LangGraph query result: {result_str[:200]}...")  
        
        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get("error", "Unknown error in query processing")
            logger.error(f"Error in LangGraph query processing: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Get the payload and API response
        payload = result.get("payload", {}) if isinstance(result, dict) else {}
        api_response = result.get("api_response", {}) if isinstance(result, dict) else {}
        
        # Combine the information for the response
        response_data = {
            "status": "success",
            "message": result.get("message", "Query processed successfully") if isinstance(result, dict) else "Query processed",
            "payload": payload,
            "api_response": api_response
        }
        
        logger.info("LangGraph request processed successfully")
        return response_data
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing LangGraph request: {str(e)}")
        logger.exception("Full exception details:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Simple health check without database dependency
        return {
            "status": "healthy", 
            "service": "agentic-sql-query", 
            "version": "1.0.0",
            "timestamp": pd.Timestamp.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)} 