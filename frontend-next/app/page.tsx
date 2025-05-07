'use client';

import { useState } from 'react';
import QueryInterface from '../src/components/QueryInterface';
import ResultsDisplay from '../src/components/ResultsDisplay';
import { Container, Typography, Box } from '@mui/material';

export default function Home() {
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h3" component="h1" align="center" gutterBottom>
          Natural Language SQL Query Interface
        </Typography>
        
        <QueryInterface 
          onResult={setResult} 
          onError={setError} 
        />

        <ResultsDisplay 
          result={result}
          error={error}
        />
      </Box>
    </Container>
  );
} 