# Quiz Builder

An AI-powered quiz generator that creates multiple-choice questions on any topic, scores answers, and explains why each correct answer is right.

## Quick start

```bash
# Backend
cd backend
pip install -r ../requirements.txt
ANTHROPIC_API_KEY=sk-... uvicorn main:app --reload

# Frontend — open directly in a browser, no build step needed
open frontend/index.html
# or serve it: python -m http.server 3000 --directory frontend
```

---

## Architecture

```
Browser (vanilla JS)
      │
      │  POST /generate-quiz   POST /score
      ▼
FastAPI backend  ──────────────────────►  Anthropic API (claude-sonnet-4-6)
      │                                        ▲
      │  GET /page/summary/{topic}             │ prompt enriched with context
      ▼                                        │
Wikipedia REST API  ────────────────────────────
```

### Backend — `backend/`

FastAPI serves three application endpoints and one utility endpoint:

| Endpoint | Purpose |
|---|---|
| `POST /generate-quiz` | Fetch Wikipedia context, build prompt, call Claude, cache answer key |
| `POST /score` | Read answer key from cache, call Claude for per-question explanations |
| `POST /quiz` | Legacy endpoint; same as `/generate-quiz` but accepts `num_questions` |
| `GET /topics` | Returns suggested topic strings for the frontend datalist |

All LLM logic lives in `quiz_generator.py`. `main.py` only handles request/response shapes and HTTP error mapping.

### Frontend — `frontend/`

Single HTML file and one JS file, no build toolchain. The page has three states:

1. **Input** — free-text field for topic, "Generate Quiz" button
2. **Quiz** — five questions rendered with A–D radio buttons
3. **Results** — options color-coded correct/wrong/missed, score banner, inline explanations

State transitions are driven by two `fetch` calls against the backend. No framework, no bundler, no dependencies.

---

## Why Claude

The quiz generation task has two hard requirements that ruled out simpler approaches.

**Reliable structured output.** Each API response must be a valid JSON array with exactly the right shape — four options per question, an integer answer index, no extraneous text. Smaller or less instruction-following models tend to leak markdown, truncate arrays, or mis-count options at non-trivial rates. Claude follows the output contract consistently enough that a single `json.loads()` with a markdown-fence strip is sufficient; no retry loop or schema-repair logic is needed.

**Factual accuracy on arbitrary topics.** The topic field is a free-text input — users can ask about anything. A retrieval-free model call means training data is the only source of truth, which degrades on niche or recently-changed subjects. Claude's instruction-following makes it straightforward to inject a Wikipedia passage and have the model treat it as authoritative context rather than override it with its priors.

GPT-4o would be a reasonable alternative with similar capabilities. The practical reason to stay on Anthropic is that the project already uses the Anthropic SDK and the model string is a one-line change if that preference shifts.

---

## Wikipedia grounding

Before calling Claude, `fetch_wikipedia_summary(topic)` hits the Wikipedia REST v1 summary endpoint:

```
GET https://en.wikipedia.org/api/rest_v1/page/summary/{topic}
```

This returns a plain-text `extract` field — no HTML parsing required. When found, it is prepended to the prompt:

```
Use the following Wikipedia summary as factual grounding for the questions:

<extract>

Generate exactly 5 multiple-choice questions about "{topic}"...
```

The function returns `None` and generation continues without context in three cases:
- **No matching page** — Wikipedia returns 404
- **Disambiguation page** — the extract just says "X may refer to…", which would produce meta-questions about the disambiguation itself rather than the topic
- **Network/timeout failure** — a 5-second timeout guards against slow responses blocking the request

**Why this helps:** Topics like "merge sort" or "TCP/IP" have stable, well-sourced Wikipedia articles. Injecting the summary shifts the model away from plausible-sounding confabulations and toward verifiable facts stated in the article.

**What it doesn't solve:** Wikipedia summaries are a few paragraphs. Deep or niche questions still rely on Claude's parametric knowledge. The grounding is a signal, not a constraint — the model can still go beyond it.

---

## In-memory answer cache

After Claude returns a quiz, the correct answer index for each question is stored in a module-level dict:

```python
_answer_cache: dict[str, dict[str, int]] = {}
# { topic_lower: { question_text: correct_option_index } }
```

`/score` reads from this cache rather than re-calling Claude. This means:

- **No second LLM call** to re-derive answers the model already produced
- **Answers are authoritative** — the index stored at generation time is exactly what scoring checks, so there's no risk of Claude producing a different answer on a re-call
- **Keyed by topic string**, so generating a new quiz on the same topic overwrites the previous entry

The tradeoff is that the cache lives in the FastAPI process. It is lost on server restart and is not shared across worker processes if the server is scaled horizontally. Two users generating a quiz on the same topic simultaneously will also collide on the same cache key.

---

## What's missing for production

**Persistence.** The answer cache is in-memory and lost on restart. Production would store quiz sessions in a database (Postgres, Redis) keyed by a session UUID returned to the client, so scoring survives restarts and horizontal scaling.

**Session isolation.** The cache key is the topic string. Two users on the same topic overwrite each other's answer key. The fix is a per-quiz UUID generated at quiz creation, returned to the client, and required on the `/score` call.

**Authentication.** There is no auth. Any request to `/generate-quiz` triggers an Anthropic API call billed to the operator's key. Production needs at minimum an API key or session token on inbound requests.

**Rate limiting.** Each `/generate-quiz` call makes one Wikipedia request and one Claude call; each `/score` call makes one more Claude call. Nothing prevents a client from hammering these endpoints. A token-bucket per IP (e.g. `slowapi`) in front of the LLM-calling routes is the simplest mitigation.

**LLM output validation.** If Claude returns malformed JSON, `json.loads()` raises and the request 500s. A retry with an explicit correction prompt ("your last response was not valid JSON — return only a JSON array") would recover most cases.

**CORS and TLS.** The backend allows the `null` origin (file:// loads) for local development. Production needs an explicit allowlist and TLS termination in front of uvicorn.
