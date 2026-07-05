/* 科目一模拟考试 - 前端应用 */
(function () {
  "use strict";

  const API = {
    stats: "/api/stats",
    allQuestions: "/api/questions/all",
    category: (kw) => "/api/questions/category/" + encodeURIComponent(kw),
    generateExam: (type) => "/api/exam/generate?type=" + encodeURIComponent(type || "new"),
    submitExam: "/api/exam/submit",
    allQuestions: (type) => "/api/questions/all" + (type && type !== "new" ? "?type=" + encodeURIComponent(type) : ""),
    category: (kw, type) => "/api/questions/category/" + encodeURIComponent(kw) + (type && type !== "new" ? "?type=" + encodeURIComponent(type) : ""),
    stats: (type) => "/api/stats" + (type && type !== "new" ? "?type=" + encodeURIComponent(type) : ""),
  };

  const Store = {
    key_wrong: "s1_wrong_ids",
    key_fav: "s1_fav_ids",
    key_exam_type: "s1_exam_type",
    getExamType() { return localStorage.getItem(this.key_exam_type) || "new"; },
    setExamType(t) { localStorage.setItem(this.key_exam_type, t === "restore" ? "restore" : "new"); },
    getWrong() { return JSON.parse(localStorage.getItem(this.key_wrong) || "[]"); },
    addWrong(id) { const s = new Set(this.getWrong()); s.add(id); localStorage.setItem(this.key_wrong, JSON.stringify([...s])); },
    removeWrong(id) { const s = new Set(this.getWrong()); s.delete(id); localStorage.setItem(this.key_wrong, JSON.stringify([...s])); },
    clearWrong() { localStorage.removeItem(this.key_wrong); },
    getFav() { return JSON.parse(localStorage.getItem(this.key_fav) || "[]"); },
    toggleFav(id) { const s = new Set(this.getFav()); if (s.has(id)) s.delete(id); else s.add(id); localStorage.setItem(this.key_fav, JSON.stringify([...s])); return s.has(id); },
    isFav(id) { return this.getFav().includes(id); },
  };

  function el(tag, props, ...children) {
    const e = document.createElement(tag);
    if (props) {
      for (const k in props) {
        if (k === "class") e.className = props[k];
        else if (k === "html") e.innerHTML = props[k];
        else if (k === "onclick") e.onclick = props[k];
        else if (k.startsWith("on")) e.addEventListener(k.slice(2).toLowerCase(), props[k]);
        else e.setAttribute(k, props[k]);
      }
    }
    for (const c of children) {
      if (c == null) continue;
      if (typeof c === "string") e.appendChild(document.createTextNode(c));
      else e.appendChild(c);
    }
    return e;
  }
  function clearApp() { document.getElementById("app").innerHTML = ""; }
  function render(node) {
    clearApp();
    document.getElementById("app").appendChild(node);
  }
  function go(hash) { location.hash = hash; }
  function fmtTime(sec) { const m = Math.floor(sec / 60), s = sec % 60; return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0"); }
  async function get(url) { const r = await fetch(url); if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }
  async function post(url, body) { const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }

  function renderQuestion(q, opts) {
    opts = opts || {};
    const card = el("div", { class: "question-card" });

    const meta = el("div", { class: "q-meta" });
    meta.appendChild(el("span", { class: "tag" }, q.type === "judge" ? "判断题" : "单选题"));
    if (q.seq != null) meta.appendChild(el("span", { class: "tag" }, "第 " + q.seq + " 题"));
    if (q.star) meta.appendChild(el("span", { class: "tag" }, "难度 " + "★".repeat(q.star)));
    card.appendChild(meta);

    card.appendChild(el("div", { class: "q-text" }, q.question));

    if (q.pic_url) {
      card.appendChild(el("img", { class: "q-pic", src: q.pic_url, alt: "题目图", onerror: function() { this.style.display = 'none'; } }));
    }

    const optWrap = el("div", { class: "options" });
    q.options.forEach((opt) => {
      const o = el("div", { class: "option", "data-key": opt.key });
      o.appendChild(el("div", { class: "key" }, opt.key));
      o.appendChild(el("div", { class: "text" }, opt.text));
      if (opts.mark) {
        const mark = el("div", { class: "mark" });
        o.appendChild(mark);
      }
      if (opts.onSelect) {
        o.onclick = () => { opts.onSelect(opt.key, o); };
      }
      if (opts.selectedKey === opt.key) o.classList.add("selected");
      if (opts.correctKey === opt.key) {
        o.classList.add("correct");
        if (opts.mark) o.querySelector(".mark").textContent = "✓";
      }
      if (opts.wrongKey === opt.key) {
        o.classList.add("wrong");
        if (opts.mark) o.querySelector(".mark").textContent = "✗";
      }
      optWrap.appendChild(o);
    });
    card.appendChild(optWrap);

    if (opts.showAnalysis && q.analysis) {
      const a = el("div", { class: "analysis" });
      a.appendChild(el("div", { class: "title" }, "解析"));
      a.appendChild(el("div", { html: q.analysis }));
      card.appendChild(a);
    }

    if (opts.showFav) {
      const favBtn = el("button", { class: "bookmark-btn" + (Store.isFav(q.id) ? " active" : ""), style: "margin-top:12px;" }, Store.isFav(q.id) ? "★ 已收藏" : "☆ 收藏");
      favBtn.onclick = () => {
        const isFav = Store.toggleFav(q.id);
        favBtn.classList.toggle("active", isFav);
        favBtn.textContent = isFav ? "★ 已收藏" : "☆ 收藏";
      };
      card.appendChild(favBtn);
    }

    return card;
  }

  function renderAnswerSheet(state, onJump) {
    const wrap = el("div", { class: "answer-sheet" });
    wrap.appendChild(el("div", { class: "title" }, "答题卡"));
    const grid = el("div", { class: "grid" });
    state.questions.forEach((q, i) => {
      const cell = el("div", { class: "cell" }, String(i + 1));
      if (state.answers[q.id]) cell.classList.add("answered");
      if (i === state.currentIndex) cell.classList.add("current");
      if (state.results) {
        const r = state.results[q.id];
        if (r) cell.classList.add(r.is_correct ? "correct" : "wrong");
      }
      grid.appendChild(cell);
    });
    grid.onclick = (e) => {
      const cell = e.target.closest('.cell');
      if (cell) {
        const index = parseInt(cell.textContent, 10) - 1;
        if (!isNaN(index) && index >= 0) {
          onJump(index);
        }
      }
    };
    wrap.appendChild(grid);
    return wrap;
  }

  // 创建全局考试类型切换器组件
  function makeExamTypeSwitcher(onChange) {
    const current = Store.getExamType();
    const wrap = el("div", { class: "exam-switcher" });
    const btnNew = el("button", {
      class: "exam-switch-btn" + (current === "new" ? " active" : ""),
      onclick: () => {
        if (current === "new") return;
        Store.setExamType("new");
        if (onChange) onChange("new");
      }
    }, "📝 新考驾照");
    const btnRestore = el("button", {
      class: "exam-switch-btn" + (current === "restore" ? " active" : ""),
      onclick: () => {
        if (current === "restore") return;
        Store.setExamType("restore");
        if (onChange) onChange("restore");
      }
    }, "🔄 恢复驾照");
    wrap.appendChild(btnNew);
    wrap.appendChild(btnRestore);
    return wrap;
  }

  async function viewHome() {
    const currentType = Store.getExamType();
    const stats = await get(API.stats(currentType));
    const wrap = el("div");
    wrap.appendChild(el("div", { class: "navbar" },
      el("div", { class: "logo" }, el("span", { class: "accent" }, "驾照"), "·科目一"),
      el("div", { class: "stats-mini" }, "题库 " + stats.total + " 题")
    ));

    const banner = el("div", { class: "stat-banner" });
    const row = el("div", { class: "row" });
    row.appendChild(el("div", {}, el("div", { class: "num" }, String(stats.total)), el("div", { class: "label" }, "总题量")));
    row.appendChild(el("div", {}, el("div", { class: "num" }, String(stats.judge)), el("div", { class: "label" }, "判断题")));
    row.appendChild(el("div", {}, el("div", { class: "num" }, String(stats.choice)), el("div", { class: "label" }, "单选题")));
    row.appendChild(el("div", {}, el("div", { class: "num" }, String(Store.getWrong().length)), el("div", { class: "label" }, "我的错题")));
    banner.appendChild(row);
    wrap.appendChild(banner);

    // 考试类型选择区（点击直接进入对应模拟考试）
    const examSection = el("div", { class: "exam-type-section" });
    examSection.appendChild(el("div", { class: "section-title" }, "模拟考试"));
    const examGrid = el("div", { class: "exam-type-grid" });

    // 新考驾照
    const newCard = el("div", { class: "exam-type-card primary", onclick: () => go("#/exam/new") });
    newCard.appendChild(el("div", { class: "exam-icon" }, "📝"));
    newCard.appendChild(el("div", { class: "exam-name" }, "新考驾照"));
    newCard.appendChild(el("div", { class: "exam-meta" }, "100 题 · 45 分钟 · 每题 1 分"));
    newCard.appendChild(el("div", { class: "exam-desc" }, "科目一正式考试规则，判断 40 + 单选 60，90 分及格"));
    examGrid.appendChild(newCard);

    // 恢复驾照
    const restoreCard = el("div", { class: "exam-type-card secondary", onclick: () => go("#/exam/restore") });
    restoreCard.appendChild(el("div", { class: "exam-icon" }, "🔄"));
    restoreCard.appendChild(el("div", { class: "exam-name" }, "恢复驾照"));
    restoreCard.appendChild(el("div", { class: "exam-meta" }, "50 题 · 30 分钟 · 每题 2 分"));
    const poolCount = stats.exam_types ? stats.exam_types.restore.question_pool : 941;
    restoreCard.appendChild(el("div", { class: "exam-desc" }, "恢复驾驶资格考试，法规安全常识为主（题库 " + poolCount + " 题），判断 20 + 单选 30"));
    examGrid.appendChild(restoreCard);

    examSection.appendChild(examGrid);
    wrap.appendChild(examSection);

    // 练习模式（受全局考试类型影响）
    const practiceSection = el("div", { style: "margin-top:18px;" });
    const practiceHeader = el("div", { style: "display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;" });
    practiceHeader.appendChild(el("div", { class: "section-title", style: "margin:0;" }, "练习模式"));
    // 全局考试类型切换器
    const switcher = makeExamTypeSwitcher(() => { viewHome(); });
    practiceHeader.appendChild(switcher);
    practiceSection.appendChild(practiceHeader);

    const typeLabel = currentType === "restore" ? "恢复驾照" : "新考驾照";
    const grid = el("div", { class: "home-grid" });
    grid.appendChild(el("div", { class: "mode-card", onclick: () => go("#/practice") },
      el("div", { class: "icon" }, "📖"),
      el("div", { class: "title" }, "顺序练习"),
      el("div", { class: "desc" }, "「" + typeLabel + "」题库 " + stats.total + " 题逐题练习，即时显示答案与解析")
    ));
    grid.appendChild(el("div", { class: "mode-card", onclick: () => go("#/wrong") },
      el("div", { class: "icon" }, "❌"),
      el("div", { class: "title" }, "错题本"),
      el("div", { class: "desc" }, "复习做错的题目，强化记忆薄弱知识点（" + Store.getWrong().length + " 题）")
    ));
    grid.appendChild(el("div", { class: "mode-card", onclick: () => go("#/category") },
      el("div", { class: "icon" }, "🗂️"),
      el("div", { class: "title" }, "分类练习"),
      el("div", { class: "desc" }, "「" + typeLabel + "」题库按知识点关键字专项练习（" + stats.categories.length + " 个分类）")
    ));
    practiceSection.appendChild(grid);
    wrap.appendChild(practiceSection);

    const history = JSON.parse(localStorage.getItem("s1_history") || "[]");
    if (history.length) {
      const h = el("div", { class: "answer-sheet", style: "margin-top:14px;" });
      h.appendChild(el("div", { class: "title" }, "最近模拟成绩"));
      const list = el("div", { style: "display:flex;flex-direction:column;gap:6px;" });
      history.slice(-8).reverse().forEach((r) => {
        const typeTag = r.examType === "restore" ? " [恢复] " : " [新考] ";
        const item = el("div", { style: "display:flex;justify-content:space-between;padding:8px 4px;border-bottom:1px solid var(--border);" },
          el("span", {}, new Date(r.time).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) + typeTag),
          el("span", { style: "font-weight:700;color:" + (r.passed ? "var(--success)" : "var(--danger)") },
            r.score + " 分 " + (r.passed ? "✓" : "✗"))
        );
        list.appendChild(item);
      });
      h.appendChild(list);
      wrap.appendChild(h);
    }

    render(wrap);
  }

  async function viewExam(examType) {
    examType = (examType === "restore") ? "restore" : "new";
    const typeLabel = examType === "restore" ? "恢复驾照" : "新考驾照";
    const wrap = el("div");
    wrap.appendChild(el("div", { class: "navbar" },
      el("button", { class: "btn-back", onclick: () => go("#/") }, "← 返回"),
      el("div", { class: "stats-mini" }, typeLabel + " · 加载中...")
    ));
    wrap.appendChild(el("div", { class: "empty-state" }, el("div", { class: "icon" }, "⏳"), "正在生成试卷..."));
    render(wrap);

    const paper = await get(API.generateExam(examType));
    const state = {
      questions: paper.questions,
      answers: {},
      currentIndex: 0,
      remaining: paper.duration_seconds,
      duration: paper.duration_seconds,
      passScore: paper.pass_score,
      scorePerQ: paper.score_per_question || 1,
      examType: examType,
      examLabel: paper.exam_label || typeLabel,
      timerId: null,
    };

    function renderCurrent() {
      const wrap = el("div");
      wrap.appendChild(el("div", { class: "navbar" },
        el("button", { class: "btn-back", onclick: () => {
          if (confirm("确定要退出考试吗？已答内容不会保存。")) { clearInterval(state.timerId); go("#/"); }
        }}, "← 退出"),
        el("div", { class: "stats-mini" }, state.examLabel + " · " + paper.total + "题")
      ));

      const header = el("div", { class: "exam-header" });
      header.appendChild(el("div", { class: "progress" },
        "第 " + (state.currentIndex + 1) + " / " + state.questions.length + " 题 · 每题 " + state.scorePerQ + " 分"));
      const timerEl = el("div", { class: "timer" + (state.remaining < 300 ? "" : " normal") }, fmtTime(state.remaining));
      header.appendChild(timerEl);
      wrap.appendChild(header);

      const q = state.questions[state.currentIndex];
      const qCard = renderQuestion(q, {
        selectedKey: state.answers[q.id],
        onSelect: (key) => {
          state.answers[q.id] = key;
          renderCurrent();
        },
      });
      wrap.appendChild(qCard);

      wrap.appendChild(renderAnswerSheet(state, (i) => {
        if (i >= 0 && i < state.questions.length) {
          state.currentIndex = i;
          renderCurrent();
          window.scrollTo(0, 0);
        }
      }));

      const footer = el("div", { class: "exam-footer" });
      if (state.currentIndex > 0) {
        footer.appendChild(el("button", { class: "btn btn-secondary", onclick: () => { state.currentIndex--; renderCurrent(); window.scrollTo(0,0); } }, "上一题"));
      }
      if (state.currentIndex < state.questions.length - 1) {
        footer.appendChild(el("button", { class: "btn btn-primary", onclick: () => { state.currentIndex++; renderCurrent(); window.scrollTo(0,0); } }, "下一题"));
        footer.appendChild(el("button", { class: "btn btn-danger", style: "flex:0 0 auto;padding:13px 20px;", onclick: () => submit() }, "交卷"));
      } else {
        footer.appendChild(el("button", { class: "btn btn-danger", onclick: () => submit() }, "交卷"));
      }
      wrap.appendChild(footer);

      render(wrap);
    }

    function submit() {
      const answered = Object.keys(state.answers).length;
      if (answered < state.questions.length) {
        if (!confirm("还有 " + (state.questions.length - answered) + " 题未作答，确定交卷吗？")) return;
      }
      clearInterval(state.timerId);
      doSubmit();
    }

    async function doSubmit() {
      const wrap = el("div");
      wrap.appendChild(el("div", { class: "navbar" },
        el("button", { class: "btn-back", onclick: () => go("#/") }, "← 返回首页"),
        el("div", { class: "stats-mini" }, "评分中...")
      ));
      wrap.appendChild(el("div", { class: "empty-state" }, el("div", { class: "icon" }, "⏳"), "正在评分..."));
      render(wrap);

      const result = await post(API.submitExam, { answers: state.answers, exam_type: state.examType });
      const history = JSON.parse(localStorage.getItem("s1_history") || "[]");
      history.push({ time: Date.now(), score: result.score, passed: result.passed, correct: result.correct, total: result.total, examType: state.examType });
      localStorage.setItem("s1_history", JSON.stringify(history));
      result.details.filter(d => !d.is_correct).forEach(d => Store.addWrong(d.id));
      renderResult(result);
    }

    function renderResult(result) {
      const wrap = el("div");
      wrap.appendChild(el("div", { class: "navbar" },
        el("button", { class: "btn-back", onclick: () => go("#/") }, "← 返回首页"),
        el("div", { class: "stats-mini" }, result.exam_label + " · 考试结果")
      ));

      const hero = el("div", { class: "result-hero" });
      hero.appendChild(el("div", { class: "score " + (result.passed ? "pass" : "fail") }, result.score + ""));
      hero.appendChild(el("div", { class: "verdict", style: "color:" + (result.passed ? "var(--success)" : "var(--danger)") },
        result.passed ? "🎉 恭喜通过！" : "❌ 未通过"));
      hero.appendChild(el("div", { class: "summary" },
        "答对 " + result.correct + " / " + result.total + " 题  ·  错 " + result.wrong + " 题  ·  及格线 " + result.pass_score + " 分（每题 " + result.score_per_question + " 分）"));
      wrap.appendChild(hero);

      const btns = el("div", { class: "exam-footer", style: "position:static;" });
      btns.appendChild(el("button", { class: "btn btn-secondary", onclick: () => go("#/exam/" + state.examType) }, "再考一次"));
      btns.appendChild(el("button", { class: "btn btn-primary", onclick: () => go("#/wrong") }, "查看错题"));
      wrap.appendChild(btns);

      const state2 = { tab: "wrong", result: result };
      function rerender() {
        const tabs = el("div", { class: "result-tabs" });
        const tAll = el("div", { class: "result-tab" + (state2.tab === "all" ? " active" : ""), onclick: () => { state2.tab = "all"; rerender(); } }, "全部 " + result.total);
        const tWrong = el("div", { class: "result-tab" + (state2.tab === "wrong" ? " active" : ""), onclick: () => { state2.tab = "wrong"; rerender(); } }, "错题 " + result.wrong);
        tabs.appendChild(tAll); tabs.appendChild(tWrong);

        const list = el("div", { style: "margin-top:12px;" });
        const items = state2.tab === "all" ? result.details : result.details.filter(d => !d.is_correct);
        items.forEach((d) => {
          const q = {
            id: d.id, question: d.question, options: d.options, type: d.type,
            pic_url: d.pic_url, analysis: d.analysis, answer: d.correct_answer,
          };
          const card = renderQuestion(q, {
            showAnalysis: true,
            mark: true,
            correctKey: d.correct_answer,
            wrongKey: d.is_correct ? null : d.user_answer,
            showFav: true,
          });
          list.appendChild(card);
        });
        const existing = wrap.querySelector(".result-tabs");
        if (existing) { existing.replaceWith(tabs); wrap.querySelector("#resultList").replaceWith(list); }
        else { wrap.appendChild(tabs); list.id = "resultList"; wrap.appendChild(list); }
        render(wrap);
        window.scrollTo(0, 0);
      }
      rerender();
    }

    state.timerId = setInterval(() => {
      state.remaining--;
      if (state.remaining <= 0) {
        clearInterval(state.timerId);
        alert("时间到，自动交卷！");
        doSubmit();
        return;
      }
      const t = document.querySelector(".timer");
      if (t) {
        t.textContent = fmtTime(state.remaining);
        t.classList.toggle("normal", state.remaining >= 300);
      }
    }, 1000);

    renderCurrent();
  }

  async function viewPractice() {
    const examType = Store.getExamType();
    const typeLabel = examType === "restore" ? "恢复驾照" : "新考驾照";
    const wrap = el("div");
    wrap.appendChild(el("div", { class: "navbar" },
      el("button", { class: "btn-back", onclick: () => go("#/") }, "← 返回"),
      el("div", { class: "stats-mini" }, typeLabel + " · 加载题库...")
    ));
    wrap.appendChild(el("div", { class: "empty-state" }, el("div", { class: "icon" }, "⏳"), "加载中..."));
    render(wrap);

    const data = await get(API.allQuestions(examType));
    const questions = data.questions;
    // 不同考试类型的进度独立存储
    const indexKey = "s1_practice_index_" + examType;
    const state = {
      currentIndex: parseInt(localStorage.getItem(indexKey) || "0", 10),
      revealed: {},
    };
    if (state.currentIndex >= questions.length) state.currentIndex = 0;

    function renderCurrent() {
      const wrap = el("div");
      wrap.appendChild(el("div", { class: "navbar" },
        el("button", { class: "btn-back", onclick: () => go("#/") }, "← 返回"),
        el("div", { class: "stats-mini" }, "顺序练习 · " + (state.currentIndex + 1) + "/" + questions.length)
      ));

      const header = el("div", { class: "exam-header" });
      header.appendChild(el("div", { class: "progress" }, "进度 " + Math.round((state.currentIndex + 1) / questions.length * 100) + "%"));
      header.appendChild(el("div", { class: "timer normal" }, "已练 " + (state.currentIndex + 1) + " 题"));
      wrap.appendChild(header);

      const q = questions[state.currentIndex];
      const isRevealed = !!state.revealed[q.id];
      const userAns = state.revealed[q.id];

      const card = renderQuestion(q, {
        selectedKey: userAns,
        showAnalysis: isRevealed,
        correctKey: isRevealed ? q.answer : null,
        wrongKey: isRevealed && userAns !== q.answer ? userAns : null,
        mark: isRevealed,
        showFav: true,
        onSelect: (key) => {
          state.revealed[q.id] = key;
          if (key !== q.answer) Store.addWrong(q.id);
          else Store.removeWrong(q.id);
          renderCurrent();
        },
      });
      wrap.appendChild(card);

      const sheet = renderAnswerSheet({
        questions: questions.slice(Math.max(0, state.currentIndex - 20), state.currentIndex + 20),
        answers: state.revealed,
        currentIndex: Math.min(20, state.currentIndex),
      }, (i) => {
        state.currentIndex = Math.max(0, state.currentIndex - 20) + i;
        localStorage.setItem(indexKey, state.currentIndex);
        renderCurrent(); window.scrollTo(0, 0);
      });
      wrap.appendChild(sheet);

      const footer = el("div", { class: "exam-footer" });
      if (state.currentIndex > 0) {
        footer.appendChild(el("button", { class: "btn btn-secondary", onclick: () => {
          state.currentIndex--; localStorage.setItem(indexKey, state.currentIndex);
          renderCurrent(); window.scrollTo(0,0);
        }}, "上一题"));
      }
      footer.appendChild(el("button", { class: "btn btn-primary", onclick: () => {
        if (state.currentIndex < questions.length - 1) {
          state.currentIndex++; localStorage.setItem(indexKey, state.currentIndex);
          renderCurrent(); window.scrollTo(0,0);
        } else {
          alert("已练习完毕！🎉");
          go("#/");
        }
      }}, state.currentIndex < questions.length - 1 ? "下一题" : "完成"));
      wrap.appendChild(footer);

      render(wrap);
    }
    renderCurrent();
  }

  async function viewWrong() {
    const wrongIds = Store.getWrong();
    const wrap = el("div");
    wrap.appendChild(el("div", { class: "navbar" },
      el("button", { class: "btn-back", onclick: () => go("#/") }, "← 返回"),
      el("div", { class: "stats-mini" }, "错题本 · " + wrongIds.length + " 题")
    ));

    if (wrongIds.length === 0) {
      wrap.appendChild(el("div", { class: "empty-state" },
        el("div", { class: "icon" }, "✨"),
        el("div", {}, "还没有错题，去练习吧！")));
      render(wrap);
      return;
    }

    // 错题本用全题库匹配，确保两种考试类型的错题都能找到
    const data = await get(API.allQuestions("new"));
    const idMap = {}; data.questions.forEach(q => idMap[q.id] = q);
    const wrongQs = wrongIds.map(id => idMap[id]).filter(Boolean);

    if (wrongQs.length === 0) {
      wrap.appendChild(el("div", { class: "empty-state" }, el("div", { class: "icon" }, "✨"), "错题已清空"));
      render(wrap);
      return;
    }

    const toolbar = el("div", { class: "exam-footer", style: "position:static;margin-bottom:12px;" });
    toolbar.appendChild(el("button", { class: "btn btn-danger", onclick: () => {
      if (confirm("确定清空所有错题吗？此操作不可撤销。")) { Store.clearWrong(); viewWrong(); }
    }}, "清空错题"));
    wrap.appendChild(toolbar);

    const state = { revealed: {} };
    function rerender() {
      const list = wrap.querySelector("#wrongList");
      const newList = el("div", { id: "wrongList", style: "margin-top:12px;" });
      wrongQs.forEach((q) => {
        const isRevealed = !!state.revealed[q.id];
        const userAns = state.revealed[q.id];
        const card = renderQuestion(q, {
          selectedKey: userAns,
          showAnalysis: isRevealed,
          correctKey: isRevealed ? q.answer : null,
          wrongKey: isRevealed && userAns !== q.answer ? userAns : null,
          mark: isRevealed,
          showFav: true,
          onSelect: (key) => {
            state.revealed[q.id] = key;
            if (key === q.answer) {
              Store.removeWrong(q.id);
              const idx = wrongQs.indexOf(q);
              if (idx >= 0) wrongQs.splice(idx, 1);
            }
            rerender();
          },
        });
        const rmBtn = el("button", { class: "bookmark-btn", style: "margin-top:8px;color:var(--danger);border-color:var(--danger);" }, "移出错题本");
        rmBtn.onclick = () => { Store.removeWrong(q.id); const i = wrongQs.indexOf(q); if (i>=0) wrongQs.splice(i,1); rerender(); };
        card.appendChild(rmBtn);
        newList.appendChild(card);
      });
      if (list) list.replaceWith(newList); else wrap.appendChild(newList);
      render(wrap);
    }
    rerender();
  }

  async function viewCategory() {
    const examType = Store.getExamType();
    const typeLabel = examType === "restore" ? "恢复驾照" : "新考驾照";
    const stats = await get(API.stats(examType));
    const wrap = el("div");
    wrap.appendChild(el("div", { class: "navbar" },
      el("button", { class: "btn-back", onclick: () => go("#/") }, "← 返回"),
      el("div", { class: "stats-mini" }, typeLabel + " · 分类练习")
    ));
    wrap.appendChild(el("div", { class: "question-card" },
      el("div", { class: "q-text", style: "font-size:16px;" }, "「" + typeLabel + "」题库按知识点关键字专项练习，点击进入：")));

    const list = el("div", { class: "cat-list" });
    stats.categories.forEach((c) => {
      list.appendChild(el("div", { class: "cat-item", onclick: () => go("#/category/" + encodeURIComponent(c.keyword)) },
        el("div", { class: "name" }, c.keyword),
        el("div", { class: "count" }, c.count + " 题")
      ));
    });
    wrap.appendChild(list);
    render(wrap);
  }

  async function viewCategoryDetail(keyword) {
    const examType = Store.getExamType();
    const typeLabel = examType === "restore" ? "恢复驾照" : "新考驾照";
    const wrap = el("div");
    wrap.appendChild(el("div", { class: "navbar" },
      el("button", { class: "btn-back", onclick: () => go("#/category") }, "← 返回分类"),
      el("div", { class: "stats-mini" }, "加载中...")
    ));
    render(wrap);

    const data = await get(API.category(keyword, examType));
    const questions = data.questions;
    const state = { currentIndex: 0, revealed: {} };

    function renderCurrent() {
      const wrap = el("div");
      wrap.appendChild(el("div", { class: "navbar" },
        el("button", { class: "btn-back", onclick: () => go("#/category") }, "← 返回"),
        el("div", { class: "stats-mini" }, "「" + keyword + "」· " + (state.currentIndex + 1) + "/" + questions.length)
      ));

      const header = el("div", { class: "exam-header" });
      header.appendChild(el("div", { class: "progress" }, keyword));
      header.appendChild(el("div", { class: "timer normal" }, (state.currentIndex + 1) + "/" + questions.length));
      wrap.appendChild(header);

      const q = questions[state.currentIndex];
      const isRevealed = !!state.revealed[q.id];
      const userAns = state.revealed[q.id];
      const card = renderQuestion(q, {
        selectedKey: userAns,
        showAnalysis: isRevealed,
        correctKey: isRevealed ? q.answer : null,
        wrongKey: isRevealed && userAns !== q.answer ? userAns : null,
        mark: isRevealed,
        showFav: true,
        onSelect: (key) => {
          state.revealed[q.id] = key;
          if (key !== q.answer) Store.addWrong(q.id); else Store.removeWrong(q.id);
          renderCurrent();
        },
      });
      wrap.appendChild(card);

      const footer = el("div", { class: "exam-footer" });
      if (state.currentIndex > 0) footer.appendChild(el("button", { class: "btn btn-secondary", onclick: () => { state.currentIndex--; renderCurrent(); window.scrollTo(0,0); } }, "上一题"));
      footer.appendChild(el("button", { class: "btn btn-primary", onclick: () => {
        if (state.currentIndex < questions.length - 1) { state.currentIndex++; renderCurrent(); window.scrollTo(0,0); }
        else { alert("本分类练习完毕！🎉"); go("#/category"); }
      }}, state.currentIndex < questions.length - 1 ? "下一题" : "完成"));
      wrap.appendChild(footer);
      render(wrap);
    }
    renderCurrent();
  }

  function router() {
    const hash = location.hash.slice(1) || "/";
    if (hash === "/" || hash === "") return viewHome().catch(errHandler);
    if (hash === "/exam" || hash === "/exam/new") return viewExam("new").catch(errHandler);
    if (hash === "/exam/restore") return viewExam("restore").catch(errHandler);
    if (hash === "/practice") return viewPractice().catch(errHandler);
    if (hash === "/wrong") return viewWrong().catch(errHandler);
    if (hash === "/category") return viewCategory().catch(errHandler);
    const catMatch = hash.match(/^\/category\/(.+)$/);
    if (catMatch) return viewCategoryDetail(decodeURIComponent(catMatch[1])).catch(errHandler);
    return viewHome().catch(errHandler);
  }

  function errHandler(e) {
    console.error(e);
    const wrap = el("div");
    wrap.appendChild(el("div", { class: "navbar" },
      el("button", { class: "btn-back", onclick: () => go("#/") }, "← 返回首页")));
    wrap.appendChild(el("div", { class: "empty-state" },
      el("div", { class: "icon" }, "⚠️"),
      el("div", {}, "加载失败：" + (e.message || "未知错误"))));
    render(wrap);
  }

  window.addEventListener("hashchange", router);
  router();
})();
