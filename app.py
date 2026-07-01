"""
科目一模拟考试 - Flask 后端
提供题库 API、模拟考试抽题、统计接口
支持两种考试类型：新考驾照（100题/45分钟）、恢复驾照（50题/30分钟）
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

# 按题型分组（新考驾照：全题库）
JUDGE_QUESTIONS = [q for q in ALL_QUESTIONS if q["type"] == "judge"]
CHOICE_QUESTIONS = [q for q in ALL_QUESTIONS if q["type"] == "single_choice"]

# --- 恢复驾照题库子集 ---
# 恢复驾照考试以交通法规和安全常识文字题为主，排除纯标志识别题、手势信号题和图片题
_SIGN_PATTERNS = ["这个标志是何含义", "这个标志是", "标志是何含义", "标志预告", "这种标志", "图中所示标志"]
_GESTURE_PATTERNS = ["交通警察手势", "手势是什么信号", "手势信号", "交警手势"]


def _is_visual_recognition(q):
    """判断是否为视觉识别题（标志/手势/带图），恢复驾照题库排除此类"""
    text = q.get("question", "")
    if any(p in text for p in _SIGN_PATTERNS + _GESTURE_PATTERNS):
        return True
    if q.get("pic_url"):
        return True
    return False


RESTORE_QUESTIONS = [q for q in ALL_QUESTIONS if not _is_visual_recognition(q)]
RESTORE_JUDGE_QUESTIONS = [q for q in RESTORE_QUESTIONS if q["type"] == "judge"]
RESTORE_CHOICE_QUESTIONS = [q for q in RESTORE_QUESTIONS if q["type"] == "single_choice"]

# 按关键字分组（取前 24 个高频关键字作为分类）
KEYWORD_MAP = {}
for q in ALL_QUESTIONS:
    for kw in q.get("keywords", []):
        KEYWORD_MAP.setdefault(kw, []).append(q)
TOP_KEYWORDS = sorted(KEYWORD_MAP.items(), key=lambda x: len(x[1]), reverse=True)[:24]

# 考试类型配置
EXAM_CONFIG = {
    "new": {
        "label": "新考驾照",
        "total": 100,
        "judge_count": 40,
        "choice_count": 60,
        "duration_seconds": 45 * 60,
        "pass_score": 90,
        "score_per_question": 1,
        "desc": "科目一正式考试 · 100 题 / 45 分钟",
    },
    "restore": {
        "label": "恢复驾照",
        "total": 50,
        "judge_count": 20,
        "choice_count": 30,
        "duration_seconds": 30 * 60,
        "pass_score": 90,
        "score_per_question": 2,
        "desc": "恢复驾驶资格考试 · 50 题 / 30 分钟（每题 2 分）",
    },
}


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
        "exam_types": {
            "new": {
                "label": EXAM_CONFIG["new"]["label"],
                "total": EXAM_CONFIG["new"]["total"],
                "duration_seconds": EXAM_CONFIG["new"]["duration_seconds"],
                "pass_score": EXAM_CONFIG["new"]["pass_score"],
                "question_pool": len(ALL_QUESTIONS),
                "desc": EXAM_CONFIG["new"]["desc"],
            },
            "restore": {
                "label": EXAM_CONFIG["restore"]["label"],
                "total": EXAM_CONFIG["restore"]["total"],
                "duration_seconds": EXAM_CONFIG["restore"]["duration_seconds"],
                "pass_score": EXAM_CONFIG["restore"]["pass_score"],
                "question_pool": len(RESTORE_QUESTIONS),
                "desc": EXAM_CONFIG["restore"]["desc"],
            },
        },
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
    生成模拟考试卷
    参数 type: new（新考驾照，100题/45分钟）| restore（恢复驾照，50题/30分钟）
    """
    exam_type = request.args.get("type", "new")
    if exam_type not in EXAM_CONFIG:
        exam_type = "new"
    cfg = EXAM_CONFIG[exam_type]

    seed = request.args.get("seed")
    rng = random.Random(int(seed)) if seed else random.Random()

    if exam_type == "restore":
        judge_pool = RESTORE_JUDGE_QUESTIONS
        choice_pool = RESTORE_CHOICE_QUESTIONS
    else:
        judge_pool = JUDGE_QUESTIONS
        choice_pool = CHOICE_QUESTIONS

    judges = rng.sample(judge_pool, min(cfg["judge_count"], len(judge_pool)))
    choices = rng.sample(choice_pool, min(cfg["choice_count"], len(choice_pool)))
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
        "exam_type": exam_type,
        "exam_label": cfg["label"],
        "total": len(paper_for_client),
        "duration_seconds": cfg["duration_seconds"],
        "pass_score": cfg["pass_score"],
        "score_per_question": cfg["score_per_question"],
        "questions": paper_for_client,
    })


@app.route("/api/exam/submit", methods=["POST"])
def submit_exam():
    """
    交卷评分
    请求体：{"answers": {"<question_id>": "<selected_key>", ...}, "exam_type": "new|restore"}
    返回：分数、对错明细、每题解析
    """
    data = request.get_json()
    answers = data.get("answers", {})
    exam_type = data.get("exam_type", "new")
    if exam_type not in EXAM_CONFIG:
        exam_type = "new"
    cfg = EXAM_CONFIG[exam_type]

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

    # 按考试类型计算分数：每题分值不同
    score_per_q = cfg["score_per_question"]
    score = round(correct_count * score_per_q, 1) if total else 0
    full_score = total * score_per_q
    passed = score >= cfg["pass_score"]
    return jsonify({
        "exam_type": exam_type,
        "exam_label": cfg["label"],
        "total": total,
        "correct": correct_count,
        "wrong": total - correct_count,
        "score": score,
        "full_score": full_score,
        "score_per_question": score_per_q,
        "pass_score": cfg["pass_score"],
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
