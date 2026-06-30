#!/usr/bin/env python3
"""
将 BrainDrivePass 的 SQL 题库转换为结构化 JSON。
字段：id, order_id, code, type(1判断/2选择), question, select_item,
      item_a/b/c/d, answer, analysis, pic_url, key_words, star, err_rate
"""
import re
import json
import sys
from pathlib import Path

SQL_FILE = Path(__file__).parent.parent / "sql-source" / "braindrivepass_practice.sql"
OUT_FILE = Path(__file__).parent.parent / "data" / "questions.json"


def parse_sql_values(values_str: str):
    """解析 SQL VALUES (...) 中的字段列表，正确处理引号、转义、NULL。"""
    fields = []
    i = 0
    n = len(values_str)
    while i < n:
        # 跳过前导空白和逗号
        while i < n and values_str[i] in " \t,":
            i += 1
        if i >= n:
            break
        ch = values_str[i]
        if ch == "'":
            # 字符串字面量
            i += 1
            buf = []
            while i < n:
                c = values_str[i]
                if c == "'" and i + 1 < n and values_str[i + 1] == "'":
                    # 转义的单引号
                    buf.append("'")
                    i += 2
                elif c == "\\" and i + 1 < n:
                    # 反斜杠转义
                    nxt = values_str[i + 1]
                    mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "0": "\0"}
                    buf.append(mapping.get(nxt, nxt))
                    i += 2
                elif c == "'":
                    # 字符串结束
                    i += 1
                    break
                else:
                    buf.append(c)
                    i += 1
            fields.append("".join(buf))
        elif ch == "N" and values_str[i:i + 4].upper() == "NULL":
            fields.append(None)
            i += 4
        else:
            # 数字或其它字面量
            buf = []
            while i < n and values_str[i] not in ",":
                buf.append(values_str[i])
                i += 1
            raw = "".join(buf).strip()
            fields.append(raw)
    return fields


def clean_html(text: str) -> str:
    """保留 <b> 加粗（前端可用），但去掉 <br> 换行符转为换行。"""
    if not text:
        return text
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    return text.strip()


def main():
    if not SQL_FILE.exists():
        # 容器内备用路径
        alt = Path("/tmp/subject1_research/BrainDrivePass/sql-source/braindrivepass_practice.sql")
        if alt.exists():
            sql_text = alt.read_text(encoding="utf-8")
        else:
            print(f"SQL file not found: {SQL_FILE}", file=sys.stderr)
            sys.exit(1)
    else:
        sql_text = SQL_FILE.read_text(encoding="utf-8")

    # 匹配 question 表的 INSERT 语句
    pattern = re.compile(r"INSERT INTO `question` VALUES \((.+?)\);", re.DOTALL)
    matches = pattern.findall(sql_text)
    print(f"找到 {len(matches)} 条 question 记录", file=sys.stderr)

    questions = []
    for m in matches:
        fields = parse_sql_values(m)
        if len(fields) < 16:
            print(f"字段数不足: {len(fields)} - {fields[:3]}", file=sys.stderr)
            continue

        # 字段顺序：id, order_id, code, type, question, select_item,
        #          item_a, item_b, item_c, item_d, answer, analysis,
        #          pic_url, key_words, star, err_rate
        qid = fields[0]
        order_id = int(fields[1]) if fields[1] else 0
        code = fields[2]
        type_raw = fields[3].lstrip("0") or "0"
        qtype = int(type_raw)
        question = fields[4]
        select_item = fields[5]
        item_a = fields[6]
        item_b = fields[7]
        item_c = fields[8]
        item_d = fields[9]
        answer = fields[10]
        analysis = clean_html(fields[11] or "")
        pic_url = fields[12] or ""
        key_words = fields[13] or ""
        star_raw = fields[14].lstrip("0") or "0"
        star = int(star_raw)
        err_rate = float(fields[15]) if fields[15] else 0.0

        # 规范化题型
        if qtype == 1:
            qtype_name = "judge"
        elif qtype == 2:
            qtype_name = "single_choice"
        else:
            qtype_name = "unknown"

        # 构造选项列表（剔除"空"占位符）
        options = []
        if qtype == 1:
            # 判断题：A=对, B=错
            options = [
                {"key": "A", "text": "对"},
                {"key": "B", "text": "错"},
            ]
            # 答案归一化
            if answer == "对":
                answer_norm = "A"
            elif answer == "错":
                answer_norm = "B"
            else:
                answer_norm = answer
        else:
            # 选择题
            opt_map = [("A", item_a), ("B", item_b), ("C", item_c), ("D", item_d)]
            for k, v in opt_map:
                if v and v.strip() and v.strip() != "空":
                    options.append({"key": k, "text": v.strip()})
            answer_norm = answer.strip()

        # 关键字拆分
        keywords = [k.strip() for k in key_words.split("|") if k.strip()] if key_words else []

        questions.append({
            "id": qid,
            "order_id": order_id,
            "code": code,
            "type": qtype_name,
            "type_id": qtype,
            "question": question.strip(),
            "options": options,
            "answer": answer_norm,
            "analysis": analysis,
            "pic_url": pic_url,
            "keywords": keywords,
            "star": star,
            "err_rate": err_rate,
        })

    # 按 order_id 排序
    questions.sort(key=lambda x: x["order_id"])

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 统计
    judge_count = sum(1 for q in questions if q["type"] == "judge")
    choice_count = sum(1 for q in questions if q["type"] == "single_choice")
    print(f"转换完成: 共 {len(questions)} 题", file=sys.stderr)
    print(f"  判断题: {judge_count}", file=sys.stderr)
    print(f"  单选题: {choice_count}", file=sys.stderr)
    print(f"  输出文件: {OUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
