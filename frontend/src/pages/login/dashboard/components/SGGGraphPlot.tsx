import type { ComponentType } from 'react'
import PlotModule from 'react-plotly.js'

import type { SGGVisualData } from '../../../../data/requests'

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

type SGGGraphPlotProps = {
  data: SGGVisualData
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

function dangerToRgb(dangerQuality: number) {
  if (dangerQuality <= 0.5) {
    const t = dangerQuality / 0.5
    const r = Math.round(46 + (255 - 46) * t)
    const g = Math.round(204 + (255 - 204) * t)
    const b = Math.round(113 + (255 - 113) * t)
    return `rgb(${r},${g},${b})`
  }

  const t = (dangerQuality - 0.5) / 0.5
  const r = Math.round(255 - (255 - 231) * t)
  const g = Math.round(255 - (255 - 76) * t)
  const b = Math.round(255 - (255 - 60) * t)
  return `rgb(${r},${g},${b})`
}

function buildRipplePoints(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
) {
  const pointCount = 30
  const deltaX = targetX - sourceX
  const deltaY = targetY - sourceY
  const length = Math.hypot(deltaX, deltaY) || 1
  const perpX = -deltaY / length
  const perpY = deltaX / length
  const amplitude = 0.12
  const xs: number[] = []
  const ys: number[] = []

  for (let index = 0; index <= pointCount; index += 1) {
    const t = index / pointCount
    const baseX = sourceX + deltaX * t
    const baseY = sourceY + deltaY * t
    const ripple = amplitude * Math.sin(t * 6 * Math.PI)
    xs.push(baseX + perpX * ripple)
    ys.push(baseY + perpY * ripple)
  }

  return {
    xs,
    ys,
    labelX: (sourceX + targetX) / 2 + perpX * 0.3,
    labelY: (sourceY + targetY) / 2 + perpY * 0.3,
  }
}

function buildFigure(data: SGGVisualData): { traces: PlotTrace[]; layout: PlotLayout } {
  const traces: PlotTrace[] = []
  const annotations: Array<Record<string, unknown>> = []
  const xValues = data.nodes.map((node) => node.x)
  const yValues = data.nodes.map((node) => node.y)
  const xRange = buildAxisRange(xValues, 1.8, [-6, 6])
  const yRange = buildAxisRange(yValues, 1.4, [-1, 10])

  for (const edge of data.edges) {
    const ripple = buildRipplePoints(edge.source_x, edge.source_y, edge.target_x, edge.target_y)

    traces.push({
      type: 'scatter',
      mode: 'lines',
      x: ripple.xs,
      y: ripple.ys,
      line: {
        color: edge.color,
        width: 2.5,
      },
      hoverinfo: 'text',
      hovertext: edge.label,
      showlegend: false,
    })

    traces.push({
      type: 'scatter',
      mode: 'text',
      x: [ripple.labelX],
      y: [ripple.labelY],
      text: [edge.label],
      textfont: {
        size: 9,
        color: edge.color,
      },
      hoverinfo: 'skip',
      showlegend: false,
    })
  }

  for (const node of data.nodes) {
    const speed = Math.hypot(node.vx, node.vy)
    if (speed < 0.01) {
      continue
    }

    annotations.push({
      x: node.x + node.vx * 1.5,
      y: node.y + node.vy * 1.5,
      ax: node.x,
      ay: node.y,
      xref: 'x',
      yref: 'y',
      axref: 'x',
      ayref: 'y',
      showarrow: true,
      arrowhead: 3,
      arrowsize: 1.5,
      arrowwidth: 2,
      arrowcolor: node.is_ego ? '#2980b9' : '#2c3e50',
    })
  }

  const pointNodes = data.nodes.filter((node) => !node.is_ego)
  const egoNode = data.nodes.find((node) => node.is_ego)

  if (pointNodes.length > 0) {
    traces.push({
      type: 'scatter',
      mode: 'markers+text',
      x: pointNodes.map((node) => node.x),
      y: pointNodes.map((node) => node.y),
      marker: {
        size: pointNodes.map((node) => 18 + 14 * node.smoothed_certainty),
        color: pointNodes.map((node) => dangerToRgb(node.danger_quality)),
        line: {
          width: 2,
          color: '#2c3e50',
        },
      },
      text: pointNodes.map((node) => `${node.cls}\n(id=${node.id})`),
      textposition: 'top center',
      textfont: {
        size: 10,
        color: '#2c3e50',
      },
      hoverinfo: 'text',
      hovertext: pointNodes.map((node) =>
        `<b>${node.cls}</b> (id=${node.id})<br>` +
        `q=${node.danger_quality.toFixed(3)} c=${node.smoothed_certainty.toFixed(3)}<br>` +
        `TTC=${node.ttc_label || 'n/a'}<br>` +
        `v=(${node.vx.toFixed(1)}, ${node.vy.toFixed(1)}) m/s<br>` +
        `pos=[${node.x.toFixed(1)}, ${node.y.toFixed(1)}, 1]`,
      ),
      name: 'Entities',
    })
  }

  if (egoNode) {
    traces.push({
      type: 'scatter',
      mode: 'markers+text',
      x: [egoNode.x],
      y: [egoNode.y],
      marker: {
        size: 30,
        color: '#3498db',
        symbol: 'triangle-up',
        line: {
          width: 3,
          color: '#2c3e50',
        },
      },
      text: ['EGO'],
      textposition: 'bottom center',
      textfont: {
        size: 11,
        color: '#2980b9',
        family: 'Arial Black',
      },
      hoverinfo: 'text',
      hovertext: [`<b>Ego Vehicle</b><br>v=(${egoNode.vx.toFixed(1)}, ${egoNode.vy.toFixed(1)}) m/s`],
      name: 'Ego Vehicle',
    })
  }

  traces.push({
    type: 'scatter',
    mode: 'markers',
    x: [null],
    y: [null],
    marker: {
      size: 0,
      colorscale: [
        [0, '#2ecc71'],
        [0.5, '#ffffff'],
        [1, '#e74c3c'],
      ],
      cmin: 0,
      cmax: 1,
      colorbar: {
        title: 'danger_quality',
        thickness: 11,
        len: 0.42,
        bgcolor: 'rgba(245,241,232,0.96)',
        bordercolor: 'rgba(116,100,71,0.15)',
        borderwidth: 1,
      },
      showscale: true,
      color: [0.5],
    },
    showlegend: false,
    hoverinfo: 'skip',
  })

  const layout: PlotLayout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: '#f6f2e7',
    margin: { l: 42, r: 38, t: 18, b: 42 },
    font: {
      color: '#3a362d',
    },
    xaxis: {
      title: 'x [m] (lateral — left<0, right>0)',
      scaleanchor: 'y',
      scaleratio: 1,
      range: xRange,
      zeroline: true,
      zerolinecolor: '#c7bea6',
      gridcolor: '#e6decb',
      linecolor: '#c7bea6',
      tickcolor: '#8e8268',
    },
    yaxis: {
      title: 'y [m] (forward)',
      range: yRange,
      zeroline: true,
      zerolinecolor: '#c7bea6',
      gridcolor: '#e6decb',
      linecolor: '#c7bea6',
      tickcolor: '#8e8268',
    },
    annotations,
    legend: {
      x: 0.01,
      y: 0.99,
      font: {
        size: 10,
      },
    },
  }

  return { traces, layout }
}

export function SGGGraphPlot({ data }: SGGGraphPlotProps) {
  const figure = buildFigure(data)

  return (
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
  )
}
