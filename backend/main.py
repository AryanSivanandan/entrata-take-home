from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from quiz_generator import check_answers, generate_quiz, get_explanations, get_topics

app = FastAPI(title="Quiz Builder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "null"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateQuizRequest(BaseModel):
    topic: str


class ScoreRequest(BaseModel):
    topic: str
    questions: list[dict]
    answers: dict[int, int]


@app.get("/topics")
def list_topics():
    return {"topics": get_topics()}


@app.post("/generate-quiz")
def generate_quiz_endpoint(req: GenerateQuizRequest):
    try:
        questions = generate_quiz(req.topic)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"topic": req.topic, "questions": questions}


@app.post("/score")
def score_quiz(req: ScoreRequest):
    try:
        answer_key = check_answers(req.topic, req.answers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    explanations = get_explanations(req.questions, answer_key)

    results = []
    score = 0
    for q in req.questions:
        qid = q["id"]
        correct_idx = answer_key.get(q["question"])
        chosen = req.answers.get(qid)
        is_correct = chosen == correct_idx
        if is_correct:
            score += 1
        results.append(
            {
                "id": qid,
                "question": q["question"],
                "chosen": chosen,
                "correct": correct_idx,
                "is_correct": is_correct,
                "explanation": explanations.get(q["question"], ""),
            }
        )

    return {"score": score, "total": len(req.questions), "results": results}
