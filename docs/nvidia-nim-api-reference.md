# NVIDIA NIM API — Free Endpoint Reference
> Last updated: 2026-06-30 | Sources: build.nvidia.com, docs.nvidia.com, integrate.api.nvidia.com/v1/models

---

## 1. API Base URL & Authentication

| Field | Value |
|-------|-------|
| **Base URL** | `https://integrate.api.nvidia.com/v1` |
| **Auth Header** | `Authorization: Bearer nvapi-...` |
| **API Key Source** | https://build.nvidia.com/settings/api-keys |
| **Compatibility** | OpenAI-compatible (`/v1/chat/completions`, `/v1/models`, etc.) |
| **Signup** | Free, no credit card required |

---

## 2. Full API Specification: `/v1/chat/completions`

### Request

```
POST https://integrate.api.nvidia.com/v1/chat/completions
Content-Type: application/json
Authorization: Bearer nvapi-YOUR_KEY
```

```json
{
  "model": "meta/llama-3.1-70b-instruct",
  "messages": [
    {"role": "user", "content": "What is GPU computing?"}
  ],
  "max_tokens": 256,
  "temperature": 0.7,
  "top_p": 0.95,
  "stream": false
}
```

### Streaming

Set `"stream": true`. Responses arrive as SSE (Server-Sent Events):
```
data: {"id":"...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"},"index":0}]}

data: {"id":"...","object":"chat.completion.chunk","choices":[{"delta":{"content":" world"},"index":0}]}

data: [DONE]
```

### Response (non-streaming)

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1718145600,
  "model": "meta/llama-3.1-70b-instruct",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "GPU computing is..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  }
}
```

### Error Codes

| HTTP Status | Meaning | Response |
|-------------|---------|----------|
| `200` | Success | Normal response |
| `400` | Bad Request | Invalid parameters, model not found, bad JSON |
| `401` | Unauthorized | Missing or invalid API key |
| `403` | Forbidden | API key lacks permission for requested model |
| `429` | Rate Limit Exceeded | See rate limit section below |
| `500` | Internal Error | Server-side issue, retry with backoff |
| `503` | Service Unavailable | Overloaded, retry later |

### Rate Limit Headers

NVIDIA NIM returns standard rate-limit headers per response:

| Header | Description |
|--------|-------------|
| `x-ratelimit-remaining-requests` | Requests remaining in current window |
| `x-ratelimit-remaining-tokens` | Tokens remaining in current window |
| `x-ratelimit-reset-requests` | Seconds until request quota resets |
| `x-ratelimit-reset-tokens` | Seconds until token quota resets |
| `Retry-After` | Seconds to wait before retrying (on 429) |

### 429 Rate Limit Error Response

```json
{
  "error": {
    "message": "Rate limit exceeded. Please try again later.",
    "type": "rate_limit_exceeded",
    "code": 429
  }
}
```

---

## 3. Rate Limit Rules (Free Tier)

| Metric | Limit |
|--------|-------|
| **Requests per minute (RPM)** | ~40 RPM per model (varies slightly by model/load) |
| **Tokens per minute (TPM)** | Not strictly enforced; governed by RPM × output tokens |
| **Credit system** | **Phased out early 2025** — now pure rate-limiting |
| **Per-model or global?** | Rate limits are **per-model**, not aggregated across all models |
| **429 behavior** | Returns `429` with `Retry-After` header; your RPM resets every 60 seconds |
| **Peak hours** | Popular models (DeepSeek R1, Qwen 3.5, GLM-5) may return 429 during high load |

### Practical Implications

- 40 RPM ≈ 1 request every 1.5 seconds — fine for interactive use, tight for batch
- Switching to a less popular model avoids congestion
- Each model has its own quota bucket — you can parallelize across models
- No hard TPM cap documented; tokens are bounded by RPM × response length

---

## 4. Complete Model Catalog (121 models from API)

### ⚡ Frontier / Large (70B+ parameters) — Primary Tier

| Model ID | Provider | Parameters | Context | Capabilities |
|----------|----------|-----------|---------|-------------|
| `deepseek-ai/deepseek-v4-pro` | DeepSeek | ~685B (MoE) | 1M | Code, reasoning, 1M context |
| `deepseek-ai/deepseek-v4-flash` | DeepSeek | ~285B (MoE) | 128K | Fast coding, reasoning |
| `z-ai/glm-5.1` | Z.ai | ~744B (MoE) | 128K | Agentic, coding, long-horizon reasoning |
| `qwen/qwen3.5-397b-a17b` | Qwen | 397B (MoE, 17B active) | 128K | General, coding, reasoning |
| `qwen/qwen3.5-122b-a10b` | Qwen | 122B (MoE, 10B active) | 128K | Strong coder, efficient MoE |
| `qwen/qwen3-next-80b-a3b-instruct` | Qwen | 80B (MoE, 3B active) | 128K | Efficient inference |
| `moonshotai/kimi-k2.6` | Moonshot AI | ~1T (MoE) | 128K | Frontier reasoning |
| `minimaxai/minimax-m2.7` | MiniMax | 230B (MoE) | 128K | General, multilingual |
| `minimaxai/minimax-m3` | MiniMax | ~466B (MoE) | 128K | Improved reasoning |
| `nvidia/nemotron-3-ultra-550b-a55b` | NVIDIA | 550B (55B active, Mamba+MoE) | 1M | Frontier reasoning, agents, tool use |
| `nvidia/nemotron-3-super-120b-a12b` | NVIDIA | 120B (12B active, MoE) | 1M | Coding, reasoning, tool calling |
| `nvidia/nemotron-4-340b-instruct` | NVIDIA | 340B | 4K | Legacy Nemotron-4 |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | NVIDIA | 253B | 128K | Instruction following, reasoning |
| `nvidia/llama-3.1-nemotron-70b-instruct` | NVIDIA | 70B | 128K | General, coding, RLHF-tuned |
| `nvidia/llama-3.3-nemotron-super-49b-v1.5` | NVIDIA | 49B | 128K | Latest nemotron-super |
| `nvidia/llama-3.3-nemotron-super-49b-v1` | NVIDIA | 49B | 128K | Nemotron-super v1 |
| `nvidia/llama3-chatqa-1.5-70b` | NVIDIA | 70B | 4K | Chat/RAG optimized |
| `meta/llama-3.1-70b-instruct` | Meta | 70B | 128K | General purpose, multilingual |
| `meta/llama-3.3-70b-instruct` | Meta | 70B | 128K | Latest Llama 3.3 |
| `meta/llama-3.2-90b-vision-instruct` | Meta | 90B | 128K | Vision + text |
| `meta/codellama-70b` | Meta | 70B | 4K | Code generation |
| `meta/llama2-70b` | Meta | 70B | 4K | Legacy Llama 2 |
| `mistralai/mistral-large-3-675b-instruct-2512` | Mistral | 675B (MoE) | 128K | Frontier Mistral |
| `mistralai/mistral-large-2-instruct` | Mistral | 123B | 128K | General, multilingual |
| `mistralai/mistral-large` | Mistral | 123B | 32K | General, multilingual |
| `mistralai/mixtral-8x22b-v0.1` | Mistral | 141B (MoE) | 64K | MoE with 8 experts |
| `mistralai/mistral-small-4-119b-2603` | Mistral | 119B | 128K | Small/Large hybrid |
| `mistralai/mistral-medium-3.5-128b` | Mistral | 128B | 128K | Balanced performance |
| `openai/gpt-oss-120b` | OpenAI | 120B (MoE) | 128K | Reasoning, math |
| `stepfun-ai/step-3.7-flash` | StepFun | MoE (sparse) | 128K | Multimodal reasoning, enterprise |
| `stepfun-ai/step-3.5-flash` | StepFun | MoE (sparse) | 128K | Fast MoE inference |
| `ai21labs/jamba-1.5-large-instruct` | AI21 Labs | 398B (MoE) | 256K | Long context |
| `stockmark/stockmark-2-100b-instruct` | Stockmark | 100B | 128K | Japanese + English |
| `writer/palmyra-creative-122b` | Writer | 122B | 8K | Creative writing |
| `writer/palmyra-fin-70b-32k` | Writer | 70B | 32K | Finance domain |
| `writer/palmyra-med-70b-32k` | Writer | 70B | 32K | Medical domain |
| `writer/palmyra-med-70b` | Writer | 70B | 8K | Medical domain |
| `abacusai/dracarys-llama-3.1-70b-instruct` | AbacusAI | 70B | 128K | Finetuned Llama 3.1 |
| `01-ai/yi-large` | 01.AI | 34B | 4K | Bilingual (EN/ZH) |
| `databricks/dbrx-instruct` | Databricks | 132B (MoE) | 32K | Enterprise MoE |
| `mistralai/mistral-nemotron` | Mistral/NVIDIA | 123B | 128K | Nemotron-tuned Mistral |

### 🔶 Mid-Tier (8B–40B) — Secondary Fallback

| Model ID | Provider | Parameters | Context | Capabilities |
|----------|----------|-----------|---------|-------------|
| `google/gemma-4-31b-it` | Google | 31B | 128K | Frontier reasoning, coding, agentic |
| `nvidia/nemotron-3-nano-30b-a3b` | NVIDIA | 30B (3B active, MoE) | 1M | Coding, reasoning, tool calling |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | NVIDIA | 30B (3B active) | 1M | Omni-modal (vision+speech+text) |
| `nvidia/nemotron-nano-3-30b-a3b` | NVIDIA | 30B (3B active, MoE) | 128K | Efficient MoE |
| `nvidia/llama-3.1-nemotron-51b-instruct` | NVIDIA | 51B | 128K | Mid-size nemotron |
| `nvidia/llama-3.1-nemotron-nano-vl-8b-v1` | NVIDIA | 8B | 128K | Vision-language |
| `nvidia/llama-3.1-nemotron-nano-8b-v1` | NVIDIA | 8B | 128K | Compact nemotron |
| `nvidia/nemotron-nano-12b-v2-vl` | NVIDIA | 12B | 128K | Vision-language v2 |
| `nvidia/nvidia-nemotron-nano-9b-v2` | NVIDIA | 9B | 128K | Compact general |
| `nvidia/neva-22b` | NVIDIA | 22B | 4K | Vision-language |
| `nvidia/mistral-nemo-minitron-8b-8k-instruct` | NVIDIA | 8B | 8K | Distilled Mistral |
| `nvidia/ising-calibration-1-35b-a3b` | NVIDIA | 35B | 32K | Physics/calibration |
| `nvidia/cosmos-reason2-8b` | NVIDIA | 8B | 128K | Physical world reasoning |
| `meta/llama-4-maverick-17b-128e-instruct` | Meta | 17B (128E MoE) | 1M | Long context MoE |
| `meta/llama-3.2-11b-vision-instruct` | Meta | 11B | 128K | Vision + text |
| `meta/llama-3.1-8b-instruct` | Meta | 8B | 128K | Compact general |
| `meta/llama-3.2-3b-instruct` | Meta | 3B | 128K | Lightweight general |
| `meta/llama-3.2-1b-instruct` | Meta | 1B | 128K | Ultra-lightweight |
| `meta/llama-guard-4-12b` | Meta | 12B | 128K | Safety/content moderation |
| `google/gemma-3-12b-it` | Google | 12B | 128K | Compact Gemma 3 |
| `google/gemma-3-4b-it` | Google | 4B | 128K | Lightweight |
| `google/gemma-3n-e4b-it` | Google | 4B | 128K | Nano variant |
| `google/gemma-2-2b-it` | Google | 2B | 8K | Tiny Gemma 2 |
| `google/gemma-3n-e2b-it` | Google | 2B | 128K | Nano tiny |
| `google/diffusiongemma-26b-a4b-it` | Google | 26B (4B active) | 128K | Diffusion-based LLM |
| `google/recurrentgemma-2b` | Google | 2B | 8K | Recurrent architecture |
| `google/codegemma-1.1-7b` | Google | 7B | 8K | Code specialized |
| `google/codegemma-7b` | Google | 7B | 8K | Code specialized |
| `microsoft/phi-4-mini-instruct` | Microsoft | 3.8B | 128K | Compact reasoning |
| `microsoft/phi-4-multimodal-instruct` | Microsoft | 5.6B | 128K | Vision + text |
| `microsoft/phi-3.5-moe-instruct` | Microsoft | 42B (MoE) | 128K | MoE reasoning |
| `microsoft/phi-3-vision-128k-instruct` | Microsoft | 4.2B | 128K | Vision |
| `mistralai/ministral-14b-instruct-2512` | Mistral | 14B | 128K | Compact instruction |
| `mistralai/codestral-22b-instruct-v0.1` | Mistral | 22B | 32K | Code specialized |
| `mistralai/mixtral-8x7b-instruct-v0.1` | Mistral | 47B (MoE) | 32K | Classic MoE |
| `mistralai/mistral-7b-instruct-v0.3` | Mistral | 7B | 32K | Compact general |
| `ibm/granite-3.0-8b-instruct` | IBM | 8B | 128K | Enterprise |
| `ibm/granite-34b-code-instruct` | IBM | 34B | 128K | Code specialized |
| `ibm/granite-8b-code-instruct` | IBM | 8B | 128K | Code compact |
| `ibm/granite-3.0-3b-a800m-instruct` | IBM | 3B | 128K | Ultra compact |
| `openai/gpt-oss-20b` | OpenAI | 20B (MoE) | 128K | Reasoning, math |
| `bigcode/starcoder2-15b` | BigCode | 15B | 16K | Code generation |
| `deepseek-ai/deepseek-coder-6.7b-instruct` | DeepSeek | 6.7B | 16K | Code specialized |
| `bytedance/seed-oss-36b-instruct` | ByteDance | 36B | 128K | General |
| `upstage/solar-10.7b-instruct` | Upstage | 10.7B | 4K | Compact |
| `nv-mistralai/mistral-nemo-12b-instruct` | NVIDIA/Mistral | 12B | 128K | Nemo architecture |
| `zyphra/zamba2-7b-instruct` | Zyphra | 7B | 128K | Mamba hybrid |
| `snowflake/arctic` | Snowflake | 480B (MoE, 17B active) | 4K | Enterprise MoE |
| `aisingapore/sea-lion-7b-instruct` | AI Singapore | 7B | 8K | SEA languages |
| `sarvamai/sarvam-m` | Sarvam AI | - | 128K | Indic languages |

### 🟢 Small / Utility (<8B) — Budget Tier

| Model ID | Provider | Parameters | Context | Capabilities |
|----------|----------|-----------|---------|-------------|
| `nvidia/nemotron-mini-4b-instruct` | NVIDIA | 4B | 32K | Ultra compact |
| `nvidia/nemotron-content-safety-reasoning-4b` | NVIDIA | 4B | 8K | Content safety |
| `nvidia/nemotron-3-content-safety` | NVIDIA | 8B | 8K | Content safety |
| `nvidia/nemotron-3.5-content-safety` | NVIDIA | 8B | 8K | Content safety v3.5 |
| `nvidia/llama-3.1-nemoguard-8b-content-safety` | NVIDIA | 8B | 8K | Guardrails |
| `nvidia/llama-3.1-nemoguard-8b-topic-control` | NVIDIA | 8B | 8K | Topic control |
| `nvidia/llama-3.1-nemotron-safety-guard-8b-v3` | NVIDIA | 8B | 8K | Safety guard |
| `nvidia/riva-translate-4b-instruct` | NVIDIA | 4B | 2K | Translation |
| `nvidia/riva-translate-4b-instruct-v1.1` | NVIDIA | 4B | 2K | Translation v1.1 |
| `nvidia/nemoretriever-parse` | NVIDIA | - | 512 | Document parsing |
| `nvidia/nemotron-parse` | NVIDIA | - | 512 | Document parsing |
| `nvidia/gliner-pii` | NVIDIA | - | 512 | PII detection |

### 📊 Embedding / Retrieval Models

| Model ID | Provider | Type |
|----------|----------|------|
| `nvidia/nv-embed-v1` | NVIDIA | General embedding |
| `nvidia/nv-embedqa-e5-v5` | NVIDIA | QA embedding |
| `nvidia/nv-embedqa-mistral-7b-v2` | NVIDIA | QA embedding (7B) |
| `nvidia/nv-embedcode-7b-v1` | NVIDIA | Code embedding |
| `nvidia/embed-qa-4` | NVIDIA | QA embedding v4 |
| `nvidia/llama-3.2-nv-embedqa-1b-v1` | NVIDIA | QA embedding (1B) |
| `nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1` | NVIDIA | VLM embedding |
| `nvidia/llama-nemotron-embed-1b-v2` | NVIDIA | Embedding v2 |
| `nvidia/llama-nemotron-embed-vl-1b-v2` | NVIDIA | VL embedding v2 |
| `baai/bge-m3` | BAAI | Multilingual embedding |
| `snowflake/arctic-embed-l` | Snowflake | Embedding |

### 🎨 Vision / Multimodal Models

| Model ID | Provider | Type |
|----------|----------|------|
| `adept/fuyu-8b` | Adept | Vision-language |
| `google/deplot` | Google | Chart/plot understanding |
| `microsoft/kosmos-2` | Microsoft | Vision-language |
| `microsoft/phi-4-multimodal-instruct` | Microsoft | Vision + text |
| `microsoft/phi-3-vision-128k-instruct` | Microsoft | Vision |
| `nvidia/cosmos-reason2-8b` | NVIDIA | Physical world VLM |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | NVIDIA | Omni-modal (vision+speech+text) |
| `nvidia/nemotron-nano-12b-v2-vl` | NVIDIA | Vision-language v2 |
| `nvidia/llama-3.1-nemotron-nano-vl-8b-v1` | NVIDIA | Vision-language |
| `nvidia/neva-22b` | NVIDIA | Vision-language |
| `nvidia/ai-synthetic-video-detector` | NVIDIA | Synthetic video detection |
| `nvidia/nvclip` | NVIDIA | CLIP-style model |
| `nvidia/vila` | NVIDIA | Visual language |

### 🏆 Reward / Scoring Models

| Model ID | Provider | Type |
|----------|----------|------|
| `nvidia/nemotron-4-340b-reward` | NVIDIA | Reward model (340B) |

---

## 5. Categorized Fallback Groups (for bot configuration)

### Group A: Frontier / Max Quality (primary)
```
"deepseek-ai/deepseek-v4-pro"
"qwen/qwen3.5-122b-a10b"
"nvidia/nemotron-3-ultra-550b-a55b"
"z-ai/glm-5.1"
"minimaxai/minimax-m3"
```
### Group B: Strong General (fallback 1)
```
"nvidia/llama-3.1-nemotron-70b-instruct"
"nvidia/llama-3.3-nemotron-super-49b-v1.5"
"meta/llama-3.3-70b-instruct"
"mistralai/mistral-large-3-675b-instruct-2512"
"google/gemma-4-31b-it"
```
### Group C: Mid / Fast (fallback 2)
```
"nvidia/nemotron-3-nano-30b-a3b"
"nvidia/llama-3.1-nemotron-51b-instruct"
"mistralai/mixtral-8x22b-v0.1"
"openai/gpt-oss-20b"
"mistralai/mistral-small-4-119b-2603"
```
### Group D: Lightweight / Latency-Optimized (fallback 3)
```
"meta/llama-3.1-8b-instruct"
"nvidia/llama-3.1-nemotron-nano-8b-v1"
"mistralai/mistral-7b-instruct-v0.3"
"nvidia/nemotron-nano-9b-v2"
```

### Code-Specific Models
```
"deepseek-ai/deepseek-coder-6.7b-instruct"
"mistralai/codestral-22b-instruct-v0.1"
"ibm/granite-34b-code-instruct"
"ibm/granite-8b-code-instruct"
"bigcode/starcoder2-15b"
```

---

## 6. Key API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/chat/completions` | POST | Chat completions (primary inference) |
| `/v1/models` | GET | List available models |
| `/v1/health/live` | GET | Liveness check (200 if container running) |
| `/v1/health/ready` | GET | Readiness check (200 if model loaded) |
| `/v1/version` | GET | NIM release version |
| `/v1/metadata` | GET | Model profile ID and name |
| `/v1/metrics` | GET | Prometheus-compatible metrics |
| `/tokenize` | POST | Tokenize input → token IDs |
| `/detokenize` | POST | Token IDs → text |

---

## 7. Sources & Verification

| Source | URL | Data Obtained |
|--------|-----|--------------|
| **Official API** | `GET https://integrate.api.nvidia.com/v1/models` | Complete model list (121 models) |
| **NVIDIA Build Catalog** | `https://build.nvidia.com/models` | 77 "Free Endpoint" models, filtering by use case |
| **NIM API Docs** | `https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html` | Full API spec, health endpoints, streaming |
| **aihola.com** | `https://aihola.com/article/nvidia-nim-free-api-models` | Rate limits (~40 RPM), catalog overview |
| **Medium (Vignaraj Ravi)** | Medium article on NIM + OpenCode | Rate limit confirmation, API base URL `integrate.api.nvidia.com/v1` |
| **uright.ca** | `https://uright.ca/posts/running-claude-code-for-free-with-nvidia-nim/` | Model IDs with parameter counts, LiteLLM proxy setup |
| **tienle.com** | OpenClaw + NIM article | Context windows (200K for GLM-5, Kimi K2.5) |
| **LiteLLM Docs** | `https://docs.litellm.ai/docs/providers/nvidia_nim` | Historical model list, API compatibility |
