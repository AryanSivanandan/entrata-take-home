from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from quiz_generator import generate_quiz, get_explanations, get_topics
import db

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
    quiz_id: int
    answers: dict[int, int]

@app.get("/topics")
def list_topics():
    return {"topics": get_topics()}

@app.post("/generate-quiz")
def generate_quiz_endpoint(req: GenerateQuizRequest):
    try:
        quiz_id, questions = generate_quiz(req.topic)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"topic": req.topic, "quiz_id": quiz_id, "questions": questions}

@app.post("/score")
def score_quiz(req: ScoreRequest):
    result = db.get_quiz(req.quiz_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    questions, answer_key = result
    explanations = get_explanations(questions, answer_key)
    results = []
    score = 0
    for q in questions:
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
    db.save_attempt(req.quiz_id, req.answers, score, len(questions))
    return {"score": score, "total": len(questions), "results": results}

@app.get("/history")
def get_history():
    return {"history": db.list_history()}
