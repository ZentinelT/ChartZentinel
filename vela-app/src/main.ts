import { Vela } from '@luxalgo/vela'
import type { DataProvider, BarRange, OHLCV, ProviderInfo, SymbolDescriptor } from '@luxalgo/vela'
import { createTheme } from '@luxalgo/vela/ui'

const BRIDGE_URL = 'http://localhost:8787'

// Vela timeframe (minutes as string, or 'D'/'W'/'M') → MT5 bridge interval
const TF_MAP: Record<string, string> = {
  '1': '1min', '3': '3min', '5': '5min', '15': '15min', '30': '30min',
  '60': '1h', '120': '2h', '240': '4h', '360': '6h', '480': '8h', '720': '12h',
  'D': '1day', '1D': '1day', 'W': '1week', '1W': '1week', 'M': '1month', '1M': '1month',
}

class Mt5Provider implements DataProvider {
  info(): ProviderInfo {
    return { name: 'mt5', label: 'MT5 Bridge' }
  }

  async getBars(ticker: string, timeframe: string, range: BarRange): Promise<OHLCV[]> {
    const interval = TF_MAP[timeframe] ?? '1h'
    const limit = range.limit ?? 500
    // Bridge expects seconds; range.to is ms
    const before = range.to ? Math.floor(range.to / 1000) : undefined
    let url = `${BRIDGE_URL}/ohlcv?symbol=${encodeURIComponent(ticker)}&interval=${interval}&bars=${limit}`
    if (before) url += `&before=${before}`
    const res = await fetch(url)
    if (!res.ok) throw new Error(`Bridge error ${res.status}`)
    const json = await res.json()
    // Bridge returns time in seconds (epoch); Vela expects milliseconds
    return (json.bars ?? []).map((b: { time: number; open: number; high: number; low: number; close: number; volume?: number }) => ({
      time: b.time * 1000,
      open: b.open, high: b.high, low: b.low, close: b.close,
      volume: b.volume,
    }))
  }

  subscribe(ticker: string, timeframe: string, onBar: (bar: OHLCV) => void): () => void {
    const interval = TF_MAP[timeframe] ?? '1h'
    let stopped = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      if (stopped) return
      try {
        const url = `${BRIDGE_URL}/ohlcv?symbol=${encodeURIComponent(ticker)}&interval=${interval}&bars=2`
        const res = await fetch(url)
        const json = await res.json()
        const bars: Array<{ time: number; open: number; high: number; low: number; close: number; volume?: number }> = json.bars ?? []
        if (bars.length > 0) {
          const b = bars[bars.length - 1]
          onBar({ time: b.time * 1000, open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume })
        }
      } catch { /* bridge offline — retry next tick */ }
      if (!stopped) timer = setTimeout(poll, 2000)
    }
    poll()
    return () => { stopped = true; clearTimeout(timer) }
  }

  async listSymbols(): Promise<SymbolDescriptor[]> {
    try {
      const res = await fetch(`${BRIDGE_URL}/symbols`)
      const names = await res.json() as string[]
      return names.map(s => ({ ticker: s, name: s, description: s }))
    } catch {
      return []
    }
  }
}

const theme = createTheme({ base: 'dark', radius: 'lg' })

const chart = new Vela('#chart', {
  symbol: 'mt5:NAS100.fs',
  timeframe: '60',
  live: true,
  theme,
  volume: true,
  animations: { pan: true, zoom: true, liveBar: false },
})

chart.data.registerProvider('mt5', new Mt5Provider())

chart.ready().then(() => {
  console.log('Vela headless + MT5 provider listo')
})
