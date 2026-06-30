import { tool } from "@opencode-ai/plugin"

const DMAPI_BASE = "https://api.dmarket.com"

export const balance = tool({
  description: "Get DMarket account balance (USD). Returns available and reserved amounts.",
  args: {},
  async execute(args, context) {
    const apiKey = process.env.DMARKET_API_KEY
    const apiSecret = process.env.DMARKET_API_SECRET
    if (!apiKey || !apiSecret) {
      return "ERROR: DMARKET_API_KEY and DMARKET_API_SECRET must be set in environment"
    }
    try {
      const timestamp = Math.floor(Date.now() / 1000).toString()
      const method = "GET"
      const path = "/account/balance"
      const signStr = timestamp + method + path
      const crypto = await import("crypto")
      const signature = crypto.createHmac("sha256", apiSecret).update(signStr).digest("hex")

      const res = await fetch(`${DMAPI_BASE}${path}`, {
        headers: {
          "X-Api-Key": apiKey,
          "X-Api-Sign": signature,
          "X-Api-Timestamp": timestamp,
          "Content-Type": "application/json"
        }
      })
      if (!res.ok) return `HTTP ${res.status}: ${await res.text()}`
      const data = await res.json()
      return JSON.stringify(data, null, 2)
    } catch (e: any) {
      return `ERROR: ${e.message}`
    }
  }
})

export const items = tool({
  description: "Search DMarket marketplace items. Returns listings with prices.",
  args: {
    query: tool.schema.string().describe("Search query (e.g. 'AK-47 | Redline')"),
    limit: tool.schema.number().optional().describe("Max results (default 10, max 50)"),
    game: tool.schema.string().optional().describe("Game filter: cs2, dota2, tf2")
  },
  async execute(args, context) {
    const limit = Math.min(args.limit || 10, 50)
    const game = args.game || "cs2"
    try {
      const params = new URLSearchParams({
        title: args.query,
        limit: limit.toString(),
        game: game
      })
      const res = await fetch(`${DMAPI_BASE}/exchange/v2/market/items?${params}`)
      if (!res.ok) return `HTTP ${res.status}: ${await res.text()}`
      const data = await res.json()
      if (!data.items || data.items.length === 0) return "No items found"
      const summary = data.items.map((item: any) =>
        `- ${item.title}: $${(item.price / 100).toFixed(2)} (${item.game || game})`
      ).join("\n")
      return `Found ${data.items.length} items:\n${summary}`
    } catch (e: any) {
      return `ERROR: ${e.message}`
    }
  }
})

export const orders = tool({
  description: "Get your active DMarket orders (buy/sell).",
  args: {
    type: tool.schema.enum(["buy", "sell"]).optional().describe("Filter by order type")
  },
  async execute(args, context) {
    const apiKey = process.env.DMARKET_API_KEY
    const apiSecret = process.env.DMARKET_API_SECRET
    if (!apiKey || !apiSecret) {
      return "ERROR: DMARKET_API_KEY and DMARKET_API_SECRET must be set"
    }
    try {
      const timestamp = Math.floor(Date.now() / 1000).toString()
      const method = "GET"
      const path = "/exchange/v2/user/orders"
      const signStr = timestamp + method + path
      const crypto = await import("crypto")
      const signature = crypto.createHmac("sha256", apiSecret).update(signStr).digest("hex")

      const res = await fetch(`${DMAPI_BASE}${path}`, {
        headers: {
          "X-Api-Key": apiKey,
          "X-Api-Sign": signature,
          "X-Api-Timestamp": timestamp
        }
      })
      if (!res.ok) return `HTTP ${res.status}: ${await res.text()}`
      const data = await res.json()
      const orders = data.orders || data || []
      if (orders.length === 0) return "No active orders"
      const filtered = args.type ? orders.filter((o: any) => o.type === args.type) : orders
      const summary = filtered.map((o: any) =>
        `- ${o.title || o.item_id}: $${(o.price / 100).toFixed(2)} (${o.type})`
      ).join("\n")
      return `Active orders (${filtered.length}):\n${summary}`
    } catch (e: any) {
      return `ERROR: ${e.message}`
    }
  }
})

export const price_history = tool({
  description: "Get price history for a specific item. Returns price points over time.",
  args: {
    item_id: tool.schema.string().describe("DMarket item ID"),
    days: tool.schema.number().optional().describe("History days (default 7, max 30)")
  },
  async execute(args, context) {
    const days = Math.min(args.days || 7, 30)
    try {
      const res = await fetch(
        `${DMAPI_BASE}/exchange/v2/items/${args.item_id}/history?days=${days}`
      )
      if (!res.ok) return `HTTP ${res.status}: ${await res.text()}`
      const data = await res.json()
      if (!data.history || data.history.length === 0) return "No history data"
      const prices = data.history.map((h: any) =>
        `${new Date(h.date || h.timestamp).toLocaleDateString()}: $${(h.price / 100).toFixed(2)}`
      ).join("\n")
      return `Price history (${days} days):\n${prices}`
    } catch (e: any) {
      return `ERROR: ${e.message}`
    }
  }
})

export const status = tool({
  description: "Check DMarket API connectivity and auth status.",
  args: {},
  async execute(args, context) {
    const apiKey = process.env.DMARKET_API_KEY
    const hasKey = !!apiKey
    const hasSecret = !!process.env.DMARKET_API_SECRET
    try {
      const res = await fetch(`${DMAPI_BASE}/exchange/v2/market/games`, {
        signal: AbortSignal.timeout(5000)
      })
      const apiOk = res.ok
      return JSON.stringify({
        api_reachable: apiOk,
        api_key_set: hasKey,
        api_secret_set: hasSecret,
        http_status: res.status
      }, null, 2)
    } catch (e: any) {
      return JSON.stringify({
        api_reachable: false,
        api_key_set: hasKey,
        api_secret_set: hasSecret,
        error: e.message
      }, null, 2)
    }
  }
})
