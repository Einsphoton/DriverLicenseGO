"""
科目一模拟考试 - Flask 后端
提供题库 API、模拟考试抽题、统计接口
支持两种考试类型：新考驾照（100题/45分钟）、恢复驾照（50题/30分钟）
支持 OpenAI 格式 API 集成，AI 讲解题目
"""
import json
import random
import urllib.request
import urllib.error
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "questions.json"

app = Flask(__name__, static_folder="static", static_url_path="")

# 启动时加载题库到内存
with open(DATA_FILE, encoding="utf-8") as f:
    RAW_QUESTIONS = json.load(f)

# --- C1/C2 小型汽车题库筛选 ---
# 原始题库为综合题库（含 A/B 照大型车辆题目），本应用面向 C1/C2 用户，需排除大型车辆专属题
_LARGE_VEHICLE_KEYWORDS = [
    "大型客车", "重型牵引挂车", "城市公交车", "中型客车", "大型货车",
    "半挂", "全挂", "牵引车", "挂车号牌", "重型载货", "中型载货",
    "危险品运输", "有轨电车", "无轨电车", "校车驾驶",
    "持大型客车", "持重型牵引", "持城市公交", "持中型客车", "持大型货车",
]
# 保留通用法规题（C1 也需要知道，如实习期不得牵引挂车、避让校车等）
_KEEP_PATTERNS = ["实习期", "避让校车", "不按规定避让校车"]


def _is_large_vehicle_exclusive(q):
    """判断是否为大型车辆专属题（C1/C2 不考）"""
    text = q.get("question", "") + " " + q.get("analysis", "")
    for kw in _LARGE_VEHICLE_KEYWORDS:
        if kw in text:
            # 通用法规题保留
            for keep in _KEEP_PATTERNS:
                if keep in text:
                    return False
            return True
    return False


# C1/C2 小型汽车专用题库
ALL_QUESTIONS = [q for q in RAW_QUESTIONS if not _is_large_vehicle_exclusive(q)]

# 按题型分组（新考驾照：C1 全题库）
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

# 全题库按关键字分组（取前 24 个高频关键字作为分类）
KEYWORD_MAP = {}
for q in ALL_QUESTIONS:
    for kw in q.get("keywords", []):
        KEYWORD_MAP.setdefault(kw, []).append(q)
TOP_KEYWORDS = sorted(KEYWORD_MAP.items(), key=lambda x: len(x[1]), reverse=True)[:24]

# 恢复驾照题库按关键字分组
RESTORE_KEYWORD_MAP = {}
for q in RESTORE_QUESTIONS:
    for kw in q.get("keywords", []):
        RESTORE_KEYWORD_MAP.setdefault(kw, []).append(q)
RESTORE_TOP_KEYWORDS = sorted(RESTORE_KEYWORD_MAP.items(), key=lambda x: len(x[1]), reverse=True)[:24]

# 恢复驾照题库的 id 集合（用于错题本等场景快速判断）
RESTORE_ID_SET = {q["id"] for q in RESTORE_QUESTIONS}


def _get_question_pool(exam_type):
    """根据考试类型返回对应题库"""
    return RESTORE_QUESTIONS if exam_type == "restore" else ALL_QUESTIONS


def _get_keyword_map(exam_type):
    """根据考试类型返回对应关键字分组"""
    return RESTORE_KEYWORD_MAP if exam_type == "restore" else KEYWORD_MAP


def _get_top_keywords(exam_type):
    """根据考试类型返回对应高频关键字"""
    return RESTORE_TOP_KEYWORDS if exam_type == "restore" else TOP_KEYWORDS

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
    """题库统计，支持 type 参数返回对应考试类型的统计"""
    exam_type = request.args.get("type", "new")
    if exam_type not in EXAM_CONFIG:
        exam_type = "new"

    if exam_type == "restore":
        pool = RESTORE_QUESTIONS
        judges = RESTORE_JUDGE_QUESTIONS
        choices = RESTORE_CHOICE_QUESTIONS
        cats = RESTORE_TOP_KEYWORDS
    else:
        pool = ALL_QUESTIONS
        judges = JUDGE_QUESTIONS
        choices = CHOICE_QUESTIONS
        cats = TOP_KEYWORDS

    return jsonify({
        "total": len(pool),
        "judge": len(judges),
        "choice": len(choices),
        "vehicle_type": "C1/C2",
        "categories": [{"keyword": k, "count": len(v)} for k, v in cats],
        "exam_type": exam_type,
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
    """全量题库（顺序练习用），支持 type 参数按考试类型筛选"""
    exam_type = request.args.get("type", "new")
    pool = _get_question_pool(exam_type if exam_type in EXAM_CONFIG else "new")
    return jsonify({"questions": pool, "exam_type": exam_type})


@app.route("/api/questions/category/<keyword>")
def by_category(keyword):
    """按关键字分类练习，支持 type 参数按考试类型筛选"""
    exam_type = request.args.get("type", "new")
    kw_map = _get_keyword_map(exam_type if exam_type in EXAM_CONFIG else "new")
    items = kw_map.get(keyword, [])
    return jsonify({"keyword": keyword, "count": len(items), "questions": items, "exam_type": exam_type})


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


# ==================== AI 讲解 ====================

AI_SYSTEM_PROMPT = """你是一位耐心、专业的驾考教练，正在帮助一位中年阿姨备考科目一/恢复驾驶资格考试。

你的讲解风格：
1. 通俗易懂，避免专业术语，用大白话解释
2. 先直接说正确答案是什么，再解释为什么
3. 逐个分析每个选项对错的原因
4. 补充相关的交通法规知识点或记忆口诀
5. 如果题目涉及图片（交通标志/手势信号），描述图片内容并解释含义
6. 鼓励学员，语气亲切温和

回答格式：
- 控制在 300 字以内
- 用简短的段落，每段 1-2 句话
- 可以用 emoji 增加亲切感但不要过度"""

# AI 配置存储在服务器端文件，所有客户端共享
# 优先使用 /app/config/ 目录（可挂载持久化），否则回退到 data/
import os
_CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", str(BASE_DIR / "config")))
_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
AI_CONFIG_FILE = _CONFIG_DIR / "ai_config.json"


def load_ai_config():
    """读取服务器端 AI 配置"""
    try:
        with open(AI_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_ai_config(cfg):
    """保存 AI 配置到服务器"""
    with open(AI_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


@app.route("/api/ai/config", methods=["GET"])
def get_ai_config():
    """返回服务器端 AI 配置状态（不返回完整 api_key）"""
    cfg = load_ai_config()
    api_key = cfg.get("api_key", "")
    masked = ""
    if api_key:
        masked = api_key[:8] + "****" + api_key[-4:] if len(api_key) > 12 else "****"
    return jsonify({
        "configured": bool(cfg.get("base_url") and cfg.get("api_key")),
        "base_url": cfg.get("base_url", ""),
        "model": cfg.get("model", ""),
        "api_key_masked": masked,
    })


@app.route("/api/ai/config", methods=["POST"])
def set_ai_config():
    """保存 AI 配置到服务器"""
    data = request.get_json()
    cfg = {
        "base_url": (data.get("base_url") or "").strip(),
        "api_key": (data.get("api_key") or "").strip(),
        "model": (data.get("model") or "").strip() or "gpt-4o-mini",
    }
    save_ai_config(cfg)
    return jsonify({"ok": True, "configured": bool(cfg["base_url"] and cfg["api_key"])})


@app.route("/api/ai/explain", methods=["POST"])
def ai_explain():
    """
    AI 讲解题目（流式 SSE 响应）
    AI 配置从服务器端文件读取，所有客户端共享。
    请求体只需题目数据，无需传 config。
    """
    data = request.get_json()
    config = load_ai_config()

    base_url = (config.get("base_url") or "").rstrip("/")
    api_key = config.get("api_key", "")
    model = config.get("model") or "gpt-4o-mini"

    if not base_url or not api_key:
        return jsonify({"error": "请先在设置中配置 API 地址和密钥"}), 400

    # 构造题目描述
    q_text = data.get("question", "")
    options = data.get("options", [])
    answer = data.get("answer", "")
    analysis = data.get("analysis", "")
    q_type = data.get("type", "")
    pic_url = data.get("pic_url", "")
    user_answer = data.get("user_answer", "")

    opt_str = "\n".join([f"  {o['key']}. {o['text']}" for o in options])
    type_label = "判断题" if q_type == "judge" else "单选题"

    user_msg = f"""请讲解以下驾考题目：

【{type_label}】{q_text}

选项：
{opt_str}

正确答案：{answer}
"""
    if user_answer and user_answer != answer:
        user_msg += f"学员选了：{user_answer}（选错了）\n"
    elif user_answer:
        user_msg += "学员选对了！\n"

    if pic_url:
        user_msg += f"\n（本题配有图片：{pic_url}）\n"

    if analysis:
        user_msg += f"\n官方解析：{analysis}\n"

    user_msg += "\n请用通俗易懂的语言讲解这道题。"

    # 调用 OpenAI 格式 API（流式）
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 600,
    }).encode("utf-8")

    chat_url = base_url + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/event-stream",
    }

    def generate():
        try:
            req = urllib.request.Request(chat_url, data=payload, headers=headers, method="POST")
            resp = urllib.request.urlopen(req, timeout=60)

            buf = b""
            for chunk in resp:
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(b"data: "):
                        line = line[6:]
                    if line == b"[DONE]":
                        yield "data: [DONE]\n\n"
                        return
                    try:
                        obj = json.loads(line)
                        delta = obj.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield "data: " + json.dumps({"content": content}, ensure_ascii=False) + "\n\n"
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue
            yield "data: [DONE]\n\n"
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            yield "data: " + json.dumps({"error": "API 错误 " + str(e.code) + ": " + err_body[:200]}, ensure_ascii=False) + "\n\n"
        except urllib.error.URLError as e:
            yield "data: " + json.dumps({"error": "连接失败: " + str(e.reason)}, ensure_ascii=False) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"error": "内部错误: " + str(e)}, ensure_ascii=False) + "\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
