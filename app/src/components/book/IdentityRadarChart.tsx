import type { Book } from '../../types';
import './IdentityRadarChart.css';

const SIZE = 220;
const CENTER = SIZE / 2;
const RADIUS = 80;
const LABEL_RADIUS = RADIUS + 20;

function pointAt(index: number, total: number, radius: number) {
  const angle = -Math.PI / 2 + index * ((2 * Math.PI) / total);
  return {
    x: CENTER + radius * Math.cos(angle),
    y: CENTER + radius * Math.sin(angle),
  };
}

interface IdentityRadarChartProps {
  vectors: Book['identityVectors'];
}

export function IdentityRadarChart({ vectors }: IdentityRadarChartProps) {
  const total = vectors.length;
  const polygonPoints = vectors
    .map((vector, i) => {
      const r = (vector.score / 100) * RADIUS;
      const { x, y } = pointAt(i, total, r);
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg className="radar-chart" viewBox={`0 0 ${SIZE} ${SIZE}`}>
      {vectors.map((vector, i) => {
        const axisEnd = pointAt(i, total, RADIUS);
        return (
          <line
            key={vector.trait}
            x1={CENTER}
            y1={CENTER}
            x2={axisEnd.x}
            y2={axisEnd.y}
            stroke="var(--color-border)"
          />
        );
      })}
      <polygon
        points={polygonPoints}
        fill="var(--color-accent)"
        fillOpacity={0.25}
        stroke="var(--color-accent)"
        strokeWidth={2}
      />
      {vectors.map((vector, i) => {
        const label = pointAt(i, total, LABEL_RADIUS);
        return (
          <text
            key={vector.trait}
            x={label.x}
            y={label.y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="radar-chart__label"
          >
            {vector.trait}
          </text>
        );
      })}
    </svg>
  );
}
