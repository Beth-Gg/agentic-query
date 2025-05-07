# Agentic SQL Query Interface

This application allows non-technical users to query databases using natural language. It converts natural language queries into SQL, executes them, and provides visualizations of the results.

## Features

- Natural language to SQL conversion using OpenAI's GPT model
- Interactive web interface
- Automatic visualization suggestion and generation
- Real-time query execution
- Beautiful and responsive UI

## Prerequisites

- Python 3.8+
- Node.js 14+
- OpenAI API key
- SQL database (SQLite by default)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd agentic-query
```

2. Set up the backend:
```bash
# Create and activate virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file and add your OpenAI API key
echo "OPENAI_API_KEY=your_api_key_here" > .env
echo "DATABASE_URL=sqlite:///./sql_app.db" >> .env
```

3. Set up the frontend:
```bash
cd frontend
npm install
```

## Running the Application

1. Start the backend server:
```bash
# From the root directory
uvicorn app.main:app --reload
```

2. Start the frontend development server:
```bash
# From the frontend directory
npm start
```

3. Open your browser and navigate to `http://localhost:3000`

## Usage

1. Enter your query in natural language in the text field
   - Example: "Show me the total sales by product category for the last month"
   - Example: "What are the top 5 customers by revenue?"

2. Click "Generate Results" to process your query

3. View the results:
   - The generated SQL query
   - A visualization of the data (if applicable)
   - The raw data results

## Configuration

- Backend configuration can be modified in the `.env` file
- Database schema can be modified in `app/database.py`
- Frontend API endpoint can be configured in `frontend/src/App.tsx`

## License

MIT 