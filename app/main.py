from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Dict, Any
import pandas as pd
import plotly.express as px
from pydantic import BaseModel
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from . import models
from .database import get_db, engine
from .nl_to_sql import process_natural_language_query
from .seed_data import seed_database

# Create database tables
models.Base.metadata.create_all(bind=engine)

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

@app.on_event("startup")
async def startup_event():
    """Seed the database with sample data on startup"""
    try:
        logger.info("Initializing database...")
        db = next(get_db())
        seed_database(db)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

@app.post("/process-query/")
async def process_query(
    request: QueryRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        logger.info(f"Processing query: {request.query}")
        
        # Process natural language to SQL
        result = process_natural_language_query(request.query)
        logger.info(f"NL to SQL result: {result}")
        
        if "error" in result:
            logger.error(f"Error in query processing: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Execute SQL query
        logger.info(f"Executing SQL query: {result['sql_query']}")
        df = pd.read_sql_query(result["sql_query"], engine)
        logger.info(f"Query execution successful, got {len(df)} rows")
        
        # Create visualization
        viz_config = result["visualization"]
        fig = None
        
        try:
            if viz_config["type"] == "bar":
                fig = px.bar(df, x=viz_config["x_axis"], y=viz_config["y_axis"])
            elif viz_config["type"] == "line":
                fig = px.line(df, x=viz_config["x_axis"], y=viz_config["y_axis"])
            elif viz_config["type"] == "number":
                # For single number results, no visualization needed
                fig = None
            elif viz_config["type"] == "table":
                # For table type, we'll just return the data
                fig = None
            
            logger.info(f"Visualization created with type: {viz_config['type']}")
        except Exception as e:
            logger.error(f"Error creating visualization: {str(e)}")
            # Continue without visualization if it fails
            
        # Convert the visualization to JSON if it exists
        plot_json = fig.to_json() if fig else None
        
        response_data = {
            "sql_query": result["sql_query"],
            "tables_used": result["tables_used"],
            "query_intent": result["query_intent"],
            "data": df.to_dict(orient="records"),
            "visualization": {
                "config": viz_config,
                "plot": plot_json
            }
        }
        
        logger.info("Request processed successfully")
        return response_data
    
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db = next(get_db())
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)} 