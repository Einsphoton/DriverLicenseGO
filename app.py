"""
科目一模拟考试 - Flask 后端
提供题库 API、模拟考试抽题、统计接口
"""
import json
import random
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "questions.json"

app = Flask(__name__, static_folder="static", static_url_path="")

# 启动时加载题库到内存
with open(DATA_FILE, encoding="utf-8") as f:
    ALL_QUESTIONS = json.load(f)

# 按题型分组
JUDGE_QUESTIONS = [q for q in ALL_QUESTIONS if q["type"] == "judge"]
CHOICE_QUESTIONS = [q for q in ALL_QUESTIONS if q["type"] == "single_choice"]

# 按关键字分组（取前 20 个高频关键字作为分类）
KEYWORD_MAP = {}
for q in ALL_QUESTIONS:
    for kw in q.get("keywords", []):
        KEYWORD_MAP.setdefault(kw, []).append(q)
TOP_KEYWORDS = sorted(KEYWORD_MAP.items(), key=lambda x: len(x[1]), reverse=True)[:24]


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/stats")
def stats():
    """题库统计"""
    return jsonify({
        "total": len(ALL_QUESTIONS),
        "judge": len(JUDGE_QUESTIONS),
        "choice": len(CHOICE_QUESTIONS),
        "categories": [{"keyword": k, "count": len(v)} for k, v in TOP_KEYWORDS],
    })


@app.route("/api/questions/all")
def all_questions():
    """全量题库（顺序练习用）"""
    return jsonify({"questions": ALL_QUESTIONS})


@app.route("/api/questions/category/<keyword>")
def by_category(keyword):
    """按关键字分类练习"""
    items = KEYWORD_MAP.get(keyword, [])
    return jsonify({"keyword": keyword, "count": len(items), "questions": items})


@app.route("/api/exam/generate")
def generate_exam():
    """
    生成模拟考试卷：100 题 / 45 分钟
    官方规则：判断题 40 + 单选题 60（共 100 题，90 分及格）
    """
    seed = request.args.get("seed")
    if seed:
        rng = random.Random(int(seed))
    else:
        rng = random.Random()

    judges = rng.sample(JUDGE_QUESTIONS, min(40, len(JUDGE_QUESTIONS)))
    choices = rng.sample(CHOICE_QUESTIONS, min(60, len(CHOICE_QUESTIONS)))
    paper = judges + choices
    rng.shuffle(paper)

    # 返回试卷（不包含答案，前端交卷后再请求评分）
    paper_for_client = []
    for i, q in enumerate(paper, 1):
        paper_for_client.append({
            "seq": i,
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "options": q["options"],
            "pic_url": q.get("pic_url", ""),
        })
    return jsonify({
        "total": len(paper_for_client),
        "duration_seconds": 45 * 60,
        "pass_score": 90,
        "questions": paper_for_client,
    })


@app.route("/api/exam/submit", methods=["POST"])
def submit_exam():
    """
    交卷评分
    请求体：{"answers": {"<question_id>": "<selected_key>", ...}}
    返回：分数、对错明细、每题解析
    """
    data = request.get_json()
    answers = data.get("answers", {})

    id_map = {q["id"]: q for q in ALL_QUESTIONS}
    correct_count = 0
    total = len(answers)
    details = []

    for qid, user_ans in answers.items():
        q = id_map.get(qid)
        if not q:
            continue
        is_correct = (user_ans == q["answer"])
        if is_correct:
            correct_count += 1
        details.append({
            "id": q["id"],
            "question": q["question"],
            "options": q["options"],
            "user_answer": user_ans,
            "correct_answer": q["answer"],
            "is_correct": is_correct,
            "analysis": q["analysis"],
            "pic_url": q.get("pic_url", ""),
            "type": q["type"],
        })

    score = round(correct_count / max(total, 1) * 100, 1) if total else 0
    passed = score >= 90
    return jsonify({
        "total": total,
        "correct": correct_count,
        "wrong": total - correct_count,
        "score": score,
        "passed": passed,
        "details": details,
    })


@app.route("/api/question/<qid>")
def get_question(qid):
    """单题查询"""
    id_map = {q["id"]: q for q in ALL_QUESTIONS}
    q = id_map.get(qid)
    if not q:
        return jsonify({"error": "not found"}), 404
    return jsonify(q)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
