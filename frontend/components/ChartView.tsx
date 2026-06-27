'use client';

import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function ChartView({ figureJson }: { figureJson: string }) {
  let fig: { data?: unknown[]; layout?: Record<string, unknown> };
  try {
    fig = JSON.parse(figureJson);
  } catch {
    return null;
  }
  return (
    <div className="chart">
      <Plot
        data={(fig.data as never[]) || []}
        layout={{
          ...(fig.layout || {}),
          autosize: true,
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#8b8f9b', family: 'Inter, system-ui, sans-serif', size: 12 },
          title: {
            ...((fig.layout?.title as Record<string, unknown>) || {}),
            font: { color: '#d6c79e', family: 'Fraunces, Georgia, serif', size: 15 },
          },
          xaxis: { gridcolor: '#262a33', zerolinecolor: '#262a33', ...((fig.layout?.xaxis as object) || {}) },
          yaxis: { gridcolor: '#262a33', zerolinecolor: '#262a33', ...((fig.layout?.yaxis as object) || {}) },
          colorway: ['#c8a96a', '#7fb38a', '#d6c79e', '#a98a4e', '#8b9bb3', '#d98a7b'],
          legend: { font: { color: '#8b8f9b' } },
          margin: { l: 54, r: 22, t: 46, b: 44 },
        }}
        config={{ displayModeBar: false, responsive: true }}
        useResizeHandler
        style={{ width: '100%', height: '380px' }}
      />
    </div>
  );
}
