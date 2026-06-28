# Quiz Builder

## Description

An AI-powered quiz generator. Give it a topic, it generates 5 multiple-choice questions, scores your answers and explains why each correct answer is right.

<sub>Built for Entrata's take-home assignment: 5 multiple-choice questions per quiz, 4 options each, score and correct answers shown after submission. Two of the three bonus features are implemented: Wikipedia-based retrieval for factual grounding and per-question explanations after scoring. Result persistence (reviewing past quizzes) is not implemented.</sub>

## Quick start

```bash
# Backend
cd backend
pip install -r requirements.txt
# add GROQ_API_KEY to a .env file in backend/
uvicorn main:app --reload

# Frontend
open frontend/index.html
```



Wikipedia REST API
| Endpoint | Purpose |
|---|---|
| `POST /generate-quiz` | Fetch Wikipedia context, generate 5 questions, cache the answer key |
| `POST /score` | Score submitted answers, generate explanations in one call |
| `GET /topics` | Suggested topics for the frontend's autocomplete |

`main.py` only handles routing and HTTP errors. All the actual logic is in `quiz_generator.py`.

The frontend is one HTML file and one JS file. Three states: enter a topic, answer the quiz, see results.

---

## Why Groq + Llama 3.3

This workload is bursty and doesn't need frontier-model reasoning, generating MCQs is a moderate difficulty task. Groq's free tier covers it , which matters for an MVP with no production traffic yet.

The provider call is isolated to two functions in `quiz_generator.py`, so switching to Claude or GPT later is a small change.

Groq doesn't offer a strict JSON guarantee, so reliability comes from prompting instead: explicit format instructions, a worked example and a retry if the response fails to parse.

---

## Wikipedia grounding

Before generating questions, `fetch_wikipedia_summary(topic)` hits:
GET https://en.wikipedia.org/api/rest_v1/page/summary/{topic}

If found, the summary gets sent to the prompt as factual grounding. If not, generation proceeds without it.

This helps for stable, well-documented topics and does nothing for niche topics at that point the model is relying on its own training knowledge.

---

## Handling unreliable JSON output

LLMs occasionally ignore formatting instructions : wrapping output in markdown fences, adding stray text or truncating. The generation and explanation calls both go through `_parse_json_with_retry`:

1. Strip markdown code fences if present
2. Try `json.loads()`
3. If that fails, replay the conversation with the model's bad response included, plus a correction message and try once more
4. If the retry also fails, raise a clear error instead of crashing silently

One retry, enough to recover from the common case without burning API calls.

---

## In-memory answer cache

After generation, the correct answer index for each question is stored in a dict:

```python
_answer_cache: dict[str, dict[str, int]] = {}
# { topic_lower: { question_text: correct_option_index } }
```

`/score` reads from this instead of asking the model again, the answer key from generation time is authoritative, so there's no risk of the model giving a different answer on a second call.

The tradeoff: it's keyed by topic string, lives only in process memory, and is lost on restart. Two users generating a quiz on the same topic at the same time will overwrite each other's cache entry. 

---

## Persistence — SQLite

Quiz and attempt data is stored in a local SQLite database (`backend/quiz_history.db`), created automatically on first run via `backend/db.py`.

**Schema:**
- `quizzes` — `id`, `topic`, `questions_json`, `answer_key_json`, `created_at`
- `attempts` — `id`, `quiz_id`, `answers_json`, `score`, `total`, `submitted_at`

**Flow:** `/generate-quiz` saves the new quiz and returns a `quiz_id` to the client instead of relying on the topic string as a lookup key. `/score` looks up the answer key by `quiz_id`, scores the submission, and saves the attempt. A `GET /history` endpoint lists past quizzes with their most recent score.

This replaces the earlier in-memory `_answer_cache` approach and fixes the concurrency issue it had — two users generating a quiz on the same topic at the same time now get distinct `quiz_id`s instead of overwriting the same cache key. Data also survives a server restart, since SQLite writes to disk.

SQLite (not Postgres) was chosen because it needs zero setup — no separate database server to run for a take-home reviewer to evaluate this. The schema and queries are simple enough that swapping to Postgres later would mean changing the connection string and one or two SQL dialect quirks, not a redesign.

--

## Two-stage generation

Explanations are only generated after a quiz is submitted, not upfront, there is no point spending tokens explaining questions a user might never finish. When they are needed, all 5 are requested in a single batched call rather than 5 separate ones, which keeps both latency and cost down.


<img width="2557" height="1357" alt="image" src="https://github.com/user-attachments/assets/41bb5a20-a5ee-4c6f-b89c-681bb73fc38b" />
