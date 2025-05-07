'use client';

import { useState } from 'react';
import { TextField, Button, Paper, CircularProgress } from '@mui/material';
import axios from 'axios';

interface QueryInterfaceProps {
  onResult: (result: any) => void;
  onError: (error: string | null) => void;
}

export default function QueryInterface({ onResult, onError }: QueryInterfaceProps) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    onError(null);
    
    try {
      const response = await axios.post('http://localhost:8000/process-query/', {
        query: query
      });
      
      onResult(response.data);
    } catch (err: any) {
      onError(err.response?.data?.detail || 'An error occurred');
      onResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
      <form onSubmit={handleSubmit}>
        <TextField
          fullWidth
          label="Enter your query in natural language"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          multiline
          rows={3}
          variant="outlined"
          sx={{ mb: 2 }}
          placeholder="Example: Show me the total sales by product category for the last month"
        />
        <Button
          type="submit"
          variant="contained"
          color="primary"
          fullWidth
          disabled={loading || !query.trim()}
        >
          {loading ? <CircularProgress size={24} /> : 'Generate Results'}
        </Button>
      </form>
    </Paper>
  );
} 