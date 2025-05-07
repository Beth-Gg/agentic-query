'use client';

import { Paper, Typography, Box } from '@mui/material';
import dynamic from 'next/dynamic';

// Dynamically import Plot with SSR disabled
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface ResultsDisplayProps {
  result: any;
  error: string | null;
}

export default function ResultsDisplay({ result, error }: ResultsDisplayProps) {
  if (error) {
    return (
      <Paper elevation={3} sx={{ p: 2, mb: 3, bgcolor: '#ffebee' }}>
        <Typography color="error">{error}</Typography>
      </Paper>
    );
  }

  if (!result) {
    return null;
  }

  return (
    <>
      <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Generated SQL Query</Typography>
        <Typography component="pre" sx={{ 
          bgcolor: '#f5f5f5',
          p: 2,
          borderRadius: 1,
          overflow: 'auto'
        }}>
          {result.sql_query}
        </Typography>
      </Paper>

      {result.visualization?.plot && (
        <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Visualization</Typography>
          <Box sx={{ width: '100%', height: '400px' }}>
            <Plot
              data={JSON.parse(result.visualization.plot).data}
              layout={{
                ...JSON.parse(result.visualization.plot).layout,
                autosize: true
              }}
              useResizeHandler
              style={{ width: '100%', height: '100%' }}
            />
          </Box>
        </Paper>
      )}

      <Paper elevation={3} sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>Results</Typography>
        <Box sx={{ overflow: 'auto' }}>
          <pre>{JSON.stringify(result.data, null, 2)}</pre>
        </Box>
      </Paper>
    </>
  );
} 