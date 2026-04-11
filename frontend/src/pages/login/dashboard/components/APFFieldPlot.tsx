import type { ComponentType } from 'react'
import PlotModule from 'react-plotly.js'

import type { APFVisualData } from '../../../../data/requests'

type PlotTrace = {
  [key: string]: unknown
}

type PlotLayout = {
  [key: string]: unknown
}

const Plot = (('default' in (PlotModule as object) ? PlotModule.default : PlotModule) as ComponentType<{
  data: PlotTrace[]
  layout: PlotLayout
  config: Record<string, unknown>
  style: Record<string, string>
  className: string
  useResizeHandler: boolean
}>)

type APFFieldPlotProps = {
  data: APFVisualData
}

function isNumber(value: number | string): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function hasNumericSurface(data: APFVisualData) {
  return data.z_surface.some((row) => row.every(isNumber))
}

function normalizeSurface(data: APFVisualData) {
  const x = data.x_grid.filter(isNumber)
  const y = data.y_grid.filter(isNumber)
  const z = data.z_surface
    .filter((row) => row.every(isNumber))
    .map((row) => row.filter(isNumber))

  if (x.length === 0 || y.length === 0 || z.length === 0) {
    return null
  }

  return { x, y, z }
}

function buildAxisRange(values: number[], padding: number, fallback: [number, number]) {
  if (values.length === 0) {
    return fallback
  }

  const min = Math.min(...values)
  const max = Math.max(...values)

  if (Math.abs(max - min) < 0.001) {
    return [min - padding, max + padding]
  }

  return [min - padding, max + padding]
}

function normalizeTrajectory(data: APFVisualData) {
  return data.trajectory.filter((point): point is [number, number, number] => Array.isArray(point))
}

function buildFigure(data: APFVisualData): { traces: PlotTrace[]; layout: PlotLayout } {
  const traces: PlotTrace[] = []
  const surface = normalizeSurface(data)
  const vectorBaseZ = 0.08
  const vectorTipZ = 0.18
  const vectorEndX = data.ego_x + data.control_steer_x
  const vectorEndY = data.ego_y + data.control_steer_y
  const trajectory = normalizeTrajectory(data)
  const pathOffsetZ =
    trajectory.length > 0 && trajectory.every((point) => Math.abs(point[2]) < 0.0001) ? 0.04 : 0
  const focusX = [
    data.ego_x,
    vectorEndX,
    ...data.entities.map((entity) => entity.x),
    ...trajectory.map((point) => point[0]),
  ]
  const focusY = [
    data.ego_y,
    vectorEndY,
    ...data.entities.map((entity) => entity.y),
    ...trajectory.map((point) => point[1]),
  ]
  const xRange = buildAxisRange(focusX, 2.6, [-6, 6])
  const yRange = buildAxisRange(focusY, 2.2, [-1, 10])

  if (surface) {
    traces.push({
      type: 'surface',
      x: surface.x,
      y: surface.y,
      z: surface.z,
      colorscale: [
        [0, '#53253b'],
        [0.35, '#8d3352'],
        [0.7, '#d66b3d'],
        [1, '#f5d98b'],
      ],
      opacity: 0.68,
      showscale: true,
      colorbar: {
        title: 'log₁₊(U)',
        thickness: 11,
        len: 0.42,
        x: 0.96,
        bgcolor: 'rgba(15,23,42,0.82)',
        bordercolor: 'rgba(148,163,184,0.2)',
        borderwidth: 1,
      },
      name: 'Potential Field',
      hovertemplate: 'x=%{x:.1f}m y=%{y:.1f}m<br>U=%{z:.3f}<extra></extra>',
      contours: {
        z: {
          show: true,
          usecolormap: false,
          color: 'rgba(255,255,255,0.56)',
          width: 1.8,
        },
      },
    })
  }

  for (const entity of data.entities) {
    traces.push({
      type: 'scatter3d',
      mode: 'markers+text',
      x: [entity.x],
      y: [entity.y],
      z: [entity.z + 0.1],
      marker: {
        size: 8,
        color: entity.color,
        line: {
          width: 1,
          color: 'black',
        },
      },
      text: [`${entity.cls} (q=${entity.danger_quality.toFixed(2)})`],
      textposition: 'top center',
      textfont: {
        size: 9,
      },
      hoverinfo: 'text',
      hovertext: [
        `<b>${entity.cls}</b> (id=${entity.id})<br>` +
        `q=${entity.danger_quality.toFixed(3)} c=${entity.smoothed_certainty.toFixed(3)}<br>` +
        `TTC=${entity.ttc_label || 'n/a'}<br>` +
        `class=${entity.danger_class}`,
      ],
      showlegend: false,
    })
  }

  traces.push({
    type: 'scatter3d',
    mode: 'markers+text',
    x: [data.ego_x],
    y: [data.ego_y],
    z: [vectorBaseZ],
    marker: {
      size: 12,
      color: '#3498db',
      symbol: 'diamond',
      line: {
        width: 2,
        color: 'black',
      },
    },
    text: ['EGO'],
    textposition: 'bottom center',
    textfont: {
      size: 11,
      color: '#2980b9',
    },
    hoverinfo: 'text',
    hovertext: [`<b>Ego Vehicle</b><br>V=${data.ego_v.toFixed(1)} m/s`],
    name: 'Vehicle',
  })

  traces.push({
    type: 'scatter3d',
    mode: 'lines',
    x: [data.ego_x, vectorEndX],
    y: [data.ego_y, vectorEndY],
    z: [vectorBaseZ, vectorTipZ],
    line: {
      color: '#7dd3fc',
      width: 10,
    },
    name: 'Steering Direction',
    hovertemplate:
      `Steering Direction<br>Δθ=${data.delta_theta.toFixed(3)} rad<br>` +
      `V=${data.v_target.toFixed(2)} m/s<extra></extra>`,
  })
  if (trajectory.length > 1) {
    traces.push({
      type: 'scatter3d',
      mode: 'lines',
      x: trajectory.map((point) => point[0]),
      y: trajectory.map((point) => point[1]),
      z: trajectory.map((point) => point[2] + pathOffsetZ),
      line: {
        color: '#facc15',
        width: 7,
      },
      name: 'Suggested Path',
      hovertemplate: 'Suggested Path<br>x=%{x:.2f}m y=%{y:.2f}m z=%{z:.2f}<extra></extra>',
    })

    const endpoint = trajectory[trajectory.length - 1]
    traces.push({
      type: 'scatter3d',
      mode: 'markers+text',
      x: [endpoint[0]],
      y: [endpoint[1]],
      z: [endpoint[2] + pathOffsetZ],
      marker: {
        size: 8,
        color: '#fde68a',
        line: {
          width: 2,
          color: '#713f12',
        },
      },
      text: ['Target'],
      textposition: 'top center',
      textfont: {
        size: 10,
        color: '#fef3c7',
      },
      hovertemplate: 'Target<br>x=%{x:.2f}m y=%{y:.2f}m z=%{z:.2f}<extra></extra>',
      showlegend: false,
    })
  }

  traces.push({
    type: 'scatter3d',
    mode: 'markers+text',
    x: [vectorEndX],
    y: [vectorEndY],
    z: [vectorTipZ],
    marker: {
      size: 7,
      color: '#f8fafc',
      line: {
        width: 2,
        color: '#0f172a',
      },
    },
    text: ['Direction'],
    textposition: 'top center',
    textfont: {
      size: 10,
      color: '#e2e8f0',
    },
    hoverinfo: 'skip',
    showlegend: false,
  })

  traces.push({
    type: 'scatter3d',
    mode: 'lines',
    x: data.corridor_xy.map((point) => point[0] + data.ego_x),
    y: data.corridor_xy.map((point) => point[1] + data.ego_y),
    z: data.corridor_xy.map(() => 0),
    line: {
      color: 'rgba(148,163,184,0.7)',
      width: 2,
      dash: 'dash',
    },
    name: 'Safety Corridor',
  })

  const layout: PlotLayout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 6, r: 6, t: 6, b: 6 },
    legend: {
      bgcolor: 'rgba(13,18,21,0.76)',
      bordercolor: 'rgba(122,168,186,0.2)',
      borderwidth: 1,
      x: 0.72,
      y: 0.98,
      font: {
        color: '#e2e8f0',
        size: 10,
      },
    },
    scene: {
      bgcolor: 'rgba(0,0,0,0)',
      xaxis: {
        title: 'x [m] (lateral)',
        range: xRange,
        gridcolor: 'rgba(255,255,255,0.14)',
        zerolinecolor: 'rgba(255,255,255,0.22)',
        color: '#cbd5e1',
      },
      yaxis: {
        title: 'y [m] (forward)',
        range: yRange,
        gridcolor: 'rgba(255,255,255,0.14)',
        zerolinecolor: 'rgba(255,255,255,0.22)',
        color: '#cbd5e1',
      },
      zaxis: {
        title: 'log₁₊(U)',
        gridcolor: 'rgba(255,255,255,0.12)',
        zerolinecolor: 'rgba(255,255,255,0.22)',
        color: '#cbd5e1',
      },
      aspectmode: 'manual',
      aspectratio: {
        x: 1.25,
        y: 1.45,
        z: 0.78,
      },
      camera: {
        eye: { x: -1.05, y: -1.4, z: 0.86 },
        center: { x: -0.05, y: -0.08, z: -0.08 },
      },
    },
  }

  return { traces, layout }
}

export function APFFieldPlot({ data }: APFFieldPlotProps) {
  if (!hasNumericSurface(data)) {
    return (
      <div className="flex h-full min-h-[220px] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-black/10 px-6 text-center text-sm text-zinc-400">
        APF surface data is not available yet. The backend payload still contains placeholder values for
        `z_surface`.
      </div>
    )
  }

  const figure = buildFigure(data)

  return (
    <div className="h-full min-h-0">
      <Plot
        data={figure.traces}
        layout={figure.layout}
        config={{
          responsive: true,
          displaylogo: false,
        }}
        style={{ width: '100%', height: '100%' }}
        className="h-full w-full"
        useResizeHandler
      />
    </div>
  )
}
