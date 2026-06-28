import json
import re
import urllib.parse
import urllib.request
from groq import Groq

_answer_cache: dict[str, dict[str, int]] = {}

_WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
_WIKIPEDIA_TIMEOUT = 5


def fetch_wikipedia_summary(topic: str) -> str | None:
    slug = urllib.parse.quote(topic.replace(" ", "_"), safe="")
    url = _WIKIPEDIA_API.format(slug)
    req = urllib.request.Request(url, headers={"User-Agent": "quiz-builder/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_WIKIPEDIA_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            payload = json.loads(resp.read())
            if payload.get("type") == "disambiguation":
                return None
            return payload.get("extract") or None
    except Exception:
        return None


def _parse_json_with_retry(client: Groq, messages: list[dict], max_tokens: int) -> object:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=max_tokens,
        messages=messages,
    )
    raw = response.choices[0].message.content
    raw_stripped = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        return json.loads(raw_stripped)
    except json.JSONDecodeError:
        pass
    retry_messages = messages + [
        {"role": "assistant", "content": raw},
        {
            "role": "user",
            "content": (
                "Your response was not valid JSON. "
                "Return ONLY a valid JSON array with no other text, no markdown, and no code fences."
            ),
        },
    ]
    retry_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=max_tokens,
        messages=retry_messages,
    )
    retry_raw = retry_response.choices[0].message.content
    retry_raw = re.sub(r"```(?:json)?\s*|\s*```", "", retry_raw).strip()
    try:
        return json.loads(retry_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON after retry: {exc}") from exc

def get_topics() -> list[str]:
    return ["python", "javascript", "general", "sql", "algorithms", "networking"]

def generate_quiz(topic: str, num_questions: int = 5) -> list[dict]:
    client = Groq()

    summary = fetch_wikipedia_summary(topic)
    context_block = (
        f"Use the following Wikipedia summary as factual grounding for the questions:\n\n"
        f"{summary}\n\n"
        if summary
        else ""
    )

    prompt = f"""{context_block}Generate exactly {num_questions} multiple-choice questions about "{topic}".

Return ONLY a JSON array with no other text, no markdown, no code fences.
Each element must have:
- "question": string
- "options": array of exactly 4 strings
- "answer": integer 0-3 (index of the correct option)

Example:
[
  {{
    "question": "What does HTTP stand for?",
    "options": ["HyperText Transfer Protocol", "High Transfer Text Protocol", "HyperText Transmission Process", "Hybrid Text Transfer Protocol"],
    "answer": 0
  }}
]"""
    questions_data = _parse_json_with_retry(
        client, [{"role": "user", "content": prompt}], max_tokens=2048
    )

    answer_key = {q["question"]: q["answer"] for q in questions_data}
    _answer_cache[topic.lower()] = answer_key

    return [
        {"id": i, "question": q["question"], "options": q["options"]}
        for i, q in enumerate(questions_data[:num_questions])
    ]

def check_answers(topic: str, answers: dict[int, int]) -> dict:
    key = topic.lower()
    if key not in _answer_cache:
        raise ValueError(f"No quiz found for topic {topic!r}. Generate a quiz first.")
    return _answer_cache[key]

def get_explanations(questions: list[dict], answer_key: dict[str, int]) -> dict[str, str]:
    items = [
        {"question": q["question"], "options": q["options"], "correct": answer_key[q["question"]]}
        for q in questions
        if q["question"] in answer_key
    ]
    if not items:
        return {}

    client = Groq()
    prompt = f"""For each quiz question below, write a brief explanation (1-2 sentences) of why the marked correct answer is right.

Return ONLY a JSON array with no other text, no markdown, no code fences.
Each element must have:
- "question": the exact question string copied verbatim
- "explanation": why the correct answer is correct

Questions:
{json.dumps(items, indent=2)}"""

    data = _parse_json_with_retry(
        client, [{"role": "user", "content": prompt}], max_tokens=1024
    )
    return {item["question"]: item["explanation"] for item in data}
