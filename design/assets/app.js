/* ============================================================
   语音书 · 原型交互脚本 (design/assets/app.js)
   仅用于静态原型演示：步骤切换 / Tab / Toast / 播放器态
   ============================================================ */
(function () {
  "use strict";

  /* —— Toast —— */
  function toast(msg, type) {
    type = type || "ok";
    var wrap = document.querySelector(".toast-wrap") || (function () {
      var w = document.createElement("div"); w.className = "toast-wrap"; document.body.appendChild(w); return w;
    })();
    var t = document.createElement("div");
    t.className = "toast " + type;
    var icon = type === "err"
      ? '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>'
      : '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>';
    t.innerHTML = icon + "<span>" + msg + "</span>";
    wrap.appendChild(t);
    setTimeout(function () { t.style.opacity = "0"; t.style.transform = "translateY(8px)"; t.style.transition = ".3s"; }, 2200);
    setTimeout(function () { t.remove(); }, 2600);
  }

  /* —— 步骤条导航（工作室） —— */
  function activateStep(n) {
    document.querySelectorAll(".step").forEach(function (s) {
      var i = +s.dataset.step;
      s.classList.toggle("active", i === n);
      s.classList.toggle("done", i < n);
    });
    document.querySelectorAll(".step-panel").forEach(function (p) {
      p.classList.toggle("hide", +p.dataset.step !== n);
    });
    var bar = document.querySelector(".step-progress");
    if (bar) bar.style.width = Math.round((n - 1) / 3 * 100) + "%";
  }

  /* —— Tab / 分段控件 —— */
  function bindSegmented() {
    document.querySelectorAll("[data-seg]").forEach(function (group) {
      group.addEventListener("click", function (e) {
        var btn = e.target.closest("button");
        if (!btn) return;
        group.querySelectorAll("button").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        // 【修复】按钮的取值应读取 data-val（此前误读 data-seg，
        // 导致 key 恒为 undefined、所有面板都会被隐藏）
        var key = btn.dataset.val;
        var seg = group.dataset.seg;
        document.querySelectorAll('[data-seg-panel="' + seg + '"]').forEach(function (p) {
          // 【修复】分段控件自身的按钮也带 data-seg-panel，若不排除会把未选中的按钮
          // 当成面板隐藏掉（studio.html 的「样章 / 全本」即是此问题）。
          if (p.closest("[data-seg]")) return;
          p.classList.toggle("hide", p.dataset.val !== key);
        });
      });
    });
  }

  /* —— 播放器（波形随播放前进，纯演示） —— */
  function bindPlayers() {
    document.querySelectorAll(".player").forEach(function (pl) {
      var btn = pl.querySelector(".play");
      var bars = pl.querySelectorAll(".wave i");
      var playing = false, idx = 0, timer = null;
      btn.addEventListener("click", function () {
        playing = !playing;
        btn.innerHTML = playing
          ? '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>'
          : '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
        if (playing) {
          timer = setInterval(function () {
            if (idx >= bars.length) { idx = 0; bars.forEach(function (b) { b.classList.remove("on"); }); }
            bars[idx].classList.add("on"); idx++;
          }, 60);
        } else { clearInterval(timer); }
      });
    });
  }

  /* —— 导航高亮（原型内跳转） —— */
  function bindNav() {
    document.querySelectorAll(".nav-item[data-nav]").forEach(function (it) {
      it.addEventListener("click", function () {
        document.querySelectorAll(".nav-item").forEach(function (n) { n.classList.remove("active"); });
        it.classList.add("active");
      });
    });
  }

  /* ============================================================
     以下为 v0.2 新增：弹窗 / 下拉菜单 / 开关 / 标签筛选 / 表格过滤
     均为纯静态演示逻辑，不依赖后端；接入 Vue 时改写为组件状态即可
     ============================================================ */

  /* —— 弹窗控制 ——
     打开：任意元素带 [data-open-modal="#id"]
     关闭：[data-close-modal] / 点击遮罩空白 / Esc 键 */
  function openModal(sel) {
    var m = document.querySelector(sel);
    if (m) m.classList.remove("hide");
  }
  function closeModal(m) {
    m.classList.add("hide");
  }
  function bindModals() {
    document.querySelectorAll("[data-open-modal]").forEach(function (b) {
      b.addEventListener("click", function () { openModal(b.dataset.openModal); });
    });
    document.querySelectorAll("[data-close-modal]").forEach(function (b) {
      b.addEventListener("click", function () { closeModal(b.closest(".modal-mask")); });
    });
    // 点击遮罩自身（非弹窗内容）时关闭
    document.querySelectorAll(".modal-mask").forEach(function (mask) {
      mask.addEventListener("click", function (e) { if (e.target === mask) closeModal(mask); });
    });
    // Esc 关闭最上层弹窗
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        var open = document.querySelectorAll(".modal-mask:not(.hide)");
        if (open.length) closeModal(open[open.length - 1]);
      }
    });
  }

  /* —— 下拉菜单（更多操作 ⋯） ——
     [data-menu-btn] 点击切换同层 .menu 的 .open；点击菜单项后自动收起；
     点击页面其他区域也会收起（全局监听一次） */
  function bindMenus() {
    document.querySelectorAll("[data-menu-btn]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var menu = btn.parentElement.querySelector(".menu");
        if (!menu) return;
        var wasOpen = menu.classList.contains("open");
        closeAllMenus();
        if (!wasOpen) menu.classList.add("open");
      });
    });
    document.addEventListener("click", function () { closeAllMenus(); });
  }
  function closeAllMenus() {
    document.querySelectorAll(".menu.open").forEach(function (m) { m.classList.remove("open"); });
  }

  /* —— 开关（Switch） —— 点击切换 .on（纯演示） */
  function bindSwitches() {
    document.querySelectorAll("[data-switch]").forEach(function (s) {
      s.addEventListener("click", function () { s.classList.toggle("on"); });
    });
  }

  /* —— 勾选圆点（批量选择） ——
     点击切换 .on，并统计选中数量更新批量操作栏文案与显隐 */
  function bindChecks() {
    var dots = document.querySelectorAll("[data-check]");
    var bar = document.querySelector("[data-batch-bar]");
    function refresh() {
      var n = document.querySelectorAll("[data-check].on").length;
      if (bar) {
        bar.classList.toggle("hide", n === 0);
        var label = bar.querySelector("[data-batch-count]");
        if (label) label.textContent = "已选 " + n + " 项";
      }
    }
    dots.forEach(function (d) {
      d.addEventListener("click", function (e) {
        e.stopPropagation(); // 避免触发卡片自身的点击跳转
        d.classList.toggle("on");
        var card = d.closest(".selectable");
        if (card) card.classList.toggle("sel", d.classList.contains("on"));
        refresh();
      });
    });
    var clear = document.querySelector("[data-batch-clear]");
    if (clear) clear.addEventListener("click", function () {
      dots.forEach(function (d) { d.classList.remove("on"); });
      document.querySelectorAll(".selectable.sel").forEach(function (c) { c.classList.remove("sel"); });
      refresh();
    });
    refresh();
  }

  /* —— 标签筛选 chips ——
     [data-tag-filter] 点击切换 .active（多选演示，仅样式态） */
  function bindTagFilters() {
    document.querySelectorAll("[data-tag-filter]").forEach(function (c) {
      c.addEventListener("click", function () { c.classList.toggle("active"); });
    });
  }

  /* —— 表格类型筛选（工作室·片段明细演示） ——
     [data-type-filter] 按钮组：读取行内 .cell-type 文本进行匹配过滤 */
  function bindTypeFilter() {
    var btns = document.querySelectorAll("[data-type-filter]");
    if (!btns.length) return;
    btns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        btns.forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        var key = btn.dataset.typeFilter; // "all" | "对话" | "叙述" | "心理"
        document.querySelectorAll("[data-type-table] tbody tr").forEach(function (tr) {
          var cell = tr.querySelector(".cell-type");
          tr.style.display = (key === "all" || !cell || cell.textContent.trim() === key) ? "" : "none";
        });
      });
    });
  }

  /* —— 滑杆数值联动 ——
     input.slider 旁边的 .pval 实时显示当前值（保留 1 位小数） */
  function bindSliders() {
    document.querySelectorAll("input[type=range].slider").forEach(function (s) {
      var out = s.parentElement.querySelector(".pval");
      var fmt = function () {
        if (!out) return;
        var v = parseFloat(s.value);
        out.textContent = (s.dataset.unit === "st" ? (v > 0 ? "+" : "") + v + "st" : (v > 0 ? "+" : "") + v.toFixed(1) + "x");
      };
      s.addEventListener("input", fmt);
      fmt();
    });
  }

  /* ============================================================
     以下为 v0.3 新增（语音书工作空间 workspace.html）
     覆盖：锚点子导航 + 滚动高亮 / 制作流水线跳转 / 角色卡选中 /
          关系图节点选中与边联动 / 片段多维筛选 / 配音资产 / 修改日志 /
          常驻迷你播放器 / 可编辑字段的「保存中」反馈
     均为纯静态演示逻辑，接入 Vue 时改写为组件状态即可
     ============================================================ */

  /* —— 锚点子导航 ——
     .subnav .sub-link 点击 → 平滑滚动到 #id；
     滚动过程中（IntersectionObserver）自动高亮当前所在区块 */
  function bindSubnav() {
    var links = Array.prototype.slice.call(document.querySelectorAll(".subnav .sub-link"));
    if (!links.length) return;
    links.forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var target = document.querySelector(a.getAttribute("href"));
        if (!target) return;
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    // 滚动高亮：以视口上方 160px 处作为「当前区块」判定线
    var spy = function () {
      var line = 160, cur = null;
      document.querySelectorAll(".anchor").forEach(function (sec) {
        if (sec.getBoundingClientRect().top <= line) cur = sec;
      });
      links.forEach(function (a) {
        var on = cur && a.getAttribute("href") === "#" + cur.id;
        a.classList.toggle("active", !!on);
      });
    };
    window.addEventListener("scroll", spy, { passive: true });
    spy();
  }

  /* —— 制作流水线 ——
     .pipe-stage[data-goto] 点击 → 滚到对应锚点（等于子导航）；
     .pipe-stage 上的 [data-pipe-act] 按钮代表「人工介入」，单独 toast */
  function bindPipeline() {
    document.querySelectorAll(".pipe-stage[data-goto]").forEach(function (s) {
      s.addEventListener("click", function (e) {
        if (e.target.closest("[data-pipe-act]")) return; // 按钮优先
        var t = document.querySelector(s.dataset.goto);
        if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  /* —— 角色卡 ——
     单选：点选后高亮 .sel，并把卡片上的角色名同步到关系图详情面板 .gp-name */
  function bindRoleCards() {
    var cards = document.querySelectorAll("[data-role-card]");
    if (!cards.length) return;
    cards.forEach(function (c) {
      c.addEventListener("click", function (e) {
        if (e.target.closest("button, a")) return; // 卡片内的按钮不触发选中
        var was = c.classList.contains("sel");
        cards.forEach(function (x) { x.classList.remove("sel"); });
        if (!was) c.classList.add("sel");
        var n = c.querySelector(".rc-name");
        var s = c.querySelector(".rc-sub");
        var g = document.querySelector(".graph-panel .gp-name");
        var gs = document.querySelector(".graph-panel .gp-sub");
        if (g) g.textContent = n ? n.textContent : "角色";
        if (gs && s) gs.textContent = s.textContent;
        var avatar = c.querySelector(".avatar");
        if (avatar && document.querySelector(".graph-panel .gp-avatar")) {
          document.querySelector(".graph-panel .gp-avatar").style.background = getComputedStyle(avatar).backgroundColor;
        }
      });
    });
  }

  /* —— 关系图联动 ——
     .g-node 点击选中（其余节点与边做 dim 弱化）；
     .g-edge 悬停/点击高亮对应关系详情；详情编辑走 toast 演示 */
  function bindGraph() {
    var nodes = document.querySelectorAll(".g-node");
    var edges = document.querySelectorAll(".g-edge");
    if (!nodes.length) return;
    function focusNode(id) {
      var any = false;
      edges.forEach(function (e) {
        var hit = e.dataset.gedge && (e.dataset.gedge.indexOf(id) >= 0);
        e.classList.toggle("dim", !!id && !hit);
        if (hit) any = true;
      });
      nodes.forEach(function (n) {
        n.classList.toggle("dim", !!id && n.dataset.gnode !== id);
        n.classList.toggle("sel", !!id && n.dataset.gnode === id);
      });
      document.querySelectorAll(".graph-panel").forEach(function (p) { p.classList.toggle("hide", false); });
    }
    nodes.forEach(function (n) {
      n.addEventListener("click", function () { focusNode(n.dataset.gnode); });
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".g-node") && !e.target.closest(".g-edge")) focusNode("");
    });
    edges.forEach(function (e) {
      e.addEventListener("mouseenter", function () {
        edges.forEach(function (x) { x.classList.toggle("hl", x === e); });
        var lab = e.querySelector("text");
        var panel = document.querySelector("[data-rel-panel]");
        if (lab && panel) {
          var t = lab.textContent; // 形如「张三 ↔ 李四 · 兄妹 · 强」
          panel.innerHTML = "<b>" + (t.split("·")[0] || "") + "</b>";
        }
      });
      e.addEventListener("mouseleave", function () {
        edges.forEach(function (x) { x.classList.remove("hl"); });
      });
    });
    // 人工调整关系（新增 / 改类型 / 改强度 / 删除 / 恢复自动）
    document.querySelectorAll("[data-rel-act]").forEach(function (b) {
      b.addEventListener("click", function () {
        toast(b.dataset.relAct, (b.dataset.relActType === "err") ? "err" : "ok");
      });
    });
    // 点击节点后右侧详情里的「在章节内容中定位」等跳转
    document.querySelectorAll("[data-rel-goto]").forEach(function (b) {
      b.addEventListener("click", function () {
        var t = document.querySelector(b.dataset.relGoto);
        if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  /* —— 片段多维筛选（已解析章节内容） ——
     筛选维度：类型（/data-seg="ftype"）/ 说话人 select / 情绪 select /
     开关（仅低置信 data-only="low"/仅人工修改 data-only="edited"） */
  function bindSegmentFilters() {
    var wrap = document.querySelector("[data-seg-list]");
    if (!wrap) return;
    var rows = Array.prototype.slice.call(wrap.querySelectorAll(".seg"));

    /* 当前类型筛选用闭包变量保存。
       【修复】不能从 .active 读取：按钮自身的监听器在事件冒泡到 [data-seg] 分组之前
       就会触发，那时 .active 还是旧值，筛选永远不生效。这里直接用被点按钮的 data-val。 */
    var segType = "all";

    // 读取其他筛选条件
    function conditions() {
      var low = document.querySelector("[data-only='low']");
      var ed = document.querySelector("[data-only='edited']");
      return {
        type: segType,
        spk: (document.querySelector("[data-spk-filter]") || {}).value || "",
        emo: (document.querySelector("[data-emo-filter]") || {}).value || "",
        onlyLow: !!low && low.classList.contains("on"),
        onlyEd: !!ed && ed.classList.contains("on")
      };
    }

    function apply() {
      var c = conditions(), n = 0;
      rows.forEach(function (r) {
        var ok = true;
        if (c.type !== "all") ok = ok && r.dataset.type === c.type;
        if (c.spk) ok = ok && r.dataset.spk === c.spk;
        if (c.emo) ok = ok && (r.dataset.emo || "").indexOf(c.emo) >= 0;
        if (c.onlyLow) ok = ok && r.classList.contains("lowconf");
        if (c.onlyEd) ok = ok && r.classList.contains("edited");
        r.classList.toggle("hide", !ok);
        if (ok) n++;
      });
      var cnt = document.querySelector("[data-seg-count]");
      if (cnt) cnt.textContent = n + " / " + rows.length;
      // 全被筛掉时展示空态，避免只看到一片空白
      var empty = document.querySelector("[data-seg-empty]");
      if (empty) empty.classList.toggle("hide", n !== 0);
    }

    // 类型分段按钮与其他筛选器变化时重算
    document.querySelectorAll("[data-seg='ftype']").forEach(function (grp) {
      grp.addEventListener("click", function (e) {
        var b = e.target.closest("button");
        if (!b) return;
        segType = b.dataset.val || "all";
        apply();
      });
    });
    document.querySelectorAll("[data-spk-filter], [data-emo-filter]").forEach(function (s) { s.addEventListener("change", apply); });
    document.querySelectorAll("[data-only]").forEach(function (s) { s.addEventListener("click", function () { s.classList.toggle("on"); apply(); }); });

    // 片段行内的具体操作按钮优先；点片段空白处 = 试听该段（驱动迷你播放器）
    rows.forEach(function (r) {
      r.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-seg-act]");
        if (btn) { toast(btn.dataset.segAct, btn.dataset.segActType || "ok"); return; }
        var dur = r.querySelector(".sg-dur");
        var label = (r.querySelector(".sg-text") || {}).textContent || "";
        var who = (r.querySelector("[data-seg-spk]") || {}).textContent || "";
        label = label.trim().replace(/\s+/g, " ").slice(0, 26);
        r.classList.add("playing");
        window.SB.miniPlay(label, who + " · " + ((dur || {}).textContent || "").trim());
        setTimeout(function () { r.classList.remove("playing"); }, 2200);
      });
    });
    apply();
  }

  /* —— 通用行内操作 ——
     button / a 上的 [data-act] → toast（select 上的 data-act 是「改了就记日志」，
     不做 toast，避免每次点击下拉都弹提示）
     范围限定 button/a，是因为 .editable、卡片、章节节点等非按钮元素靠 onclick 或
     专用绑定处理，混在一起会重复触发 */
  function bindActions() {
    document.querySelectorAll("button[data-act], a[data-act]").forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        toast(b.dataset.act, b.dataset.actType || "ok");
      });
    });
  }

  /* —— 可人工修改的字段 ——
     .editable 点击后给出「保存中 → 已保存」反馈，并把提示写入修改日志 */
  function bindEditable() {
    var flag = document.querySelector("[data-saving-flag]");
    document.querySelectorAll(".editable").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.stopPropagation();
        el.classList.add("saving");
        toast("已改为「" + el.textContent.trim() + "」并记入修改日志");
        if (flag) { flag.classList.add("on"); flag.textContent = "保存中…"; }
        setTimeout(function () {
          if (flag) { flag.textContent = "已保存 · 已记入修改日志"; setTimeout(function () { flag.classList.remove("on"); }, 1600); }
        }, 520);
      });
    });
  }

  /* —— 常驻迷你播放器 ——
     工作空间内点任意 [data-play]（片段 / 音频行 / 章节）即可抢占播放；
     顶栏播放器与迷你播放器状态同步，波形随播放前进 */
  var miniState = { timer: null, idx: 0 };
  function bindMiniPlayer() {
    var mp = document.querySelector(".mini-player");
    if (!mp) return;
    var play = mp.querySelector(".mp-play");
    var bars = mp.querySelectorAll(".mp-wave i");
    function paint(playing) {
      play.innerHTML = playing
        ? '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
    }
    function tick() {
      if (!bars.length) return;
      if (miniState.idx >= bars.length) { miniState.idx = 0; bars.forEach(function (b) { b.classList.remove("on"); }); }
      bars[miniState.idx].classList.add("on"); miniState.idx++;
    }
    play.addEventListener("click", function () {
      var on = !miniState.timer;
      clearInterval(miniState.timer);
      if (on) miniState.timer = setInterval(tick, 70);
      paint(on);
    });
    mp.querySelector(".mp-close").addEventListener("click", function () {
      clearInterval(miniState.timer); paint(false); mp.classList.add("hide");
    });
    // 全局试听入口：统一驱动迷你播放器
    document.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-play]");
      if (!btn || btn.closest(".mini-player")) return;
      var title = btn.getAttribute("data-play") || "音频";
      var sub = btn.getAttribute("data-play-sub") || "";
      var t = mp.querySelector(".mp-title"), s = mp.querySelector(".mp-sub");
      if (t) t.textContent = title;
      if (s) s.textContent = sub;
      mp.classList.remove("hide");
      miniState.idx = 0; bars.forEach(function (b) { b.classList.remove("on"); });
      clearInterval(miniState.timer);
      miniState.timer = setInterval(tick, 70);
      paint(true);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindSegmented();
    bindPlayers();
    bindNav();
    bindModals();      // v0.2：弹窗开合
    bindMenus();       // v0.2：下拉菜单
    bindSwitches();    // v0.2：开关
    bindChecks();      // v0.2：批量勾选
    bindTagFilters();  // v0.2：标签筛选
    bindTypeFilter();  // v0.2：表格类型筛选
    bindSliders();     // v0.2：滑杆数值联动
    /* v0.3：语音书工作空间 */
    bindSubnav();      // 锚点子导航 + 滚动高亮
    bindPipeline();    // 制作流水线阶段跳转
    bindRoleCards();   // 角色卡选中 → 联动关系图详情
    bindGraph();       // 关系图节点/边联动
    bindSegmentFilters(); // 已解析章节内容多维筛选
    bindActions();     // 行内操作 toast
    bindEditable();    // 可人工修改字段的保存反馈
    bindMiniPlayer();  // 常驻迷你播放器（全局试听）
    document.querySelectorAll(".step").forEach(function (s) {
      s.addEventListener("click", function () { activateStep(+s.dataset.step); });
    });
    document.querySelectorAll("[data-toast]").forEach(function (b) {
      b.addEventListener("click", function () { toast(b.dataset.toast, b.dataset.toastType || "ok"); });
    });
    document.querySelectorAll("[data-step-go]").forEach(function (b) {
      b.addEventListener("click", function () { activateStep(+b.dataset.stepGo); window.scrollTo({ top: 0, behavior: "smooth" }); });
    });
    // 默认进入工作室第 1 步
    var first = document.querySelector(".step");
    if (first) activateStep(+first.dataset.step || 1);
  });

  /* —— 全局试听（供页面各处 [data-play] 复用）——
     与迷你播放器共用同一套状态；重复调用会重置进度条而非叠加 */
  function miniPlay(title, sub) {
    var mp = document.querySelector(".mini-player");
    if (!mp) return;
    var t = mp.querySelector(".mp-title"), s = mp.querySelector(".mp-sub");
    if (t) t.textContent = title;
    if (s) s.textContent = sub || "";
    mp.classList.remove("hide");
    var bars = mp.querySelectorAll(".mp-wave i");
    miniState.idx = 0;
    bars.forEach(function (b) { b.classList.remove("on"); });
    clearInterval(miniState.timer);
    if (!bars.length) return;
    miniState.timer = setInterval(function () {
      if (miniState.idx >= bars.length) { miniState.idx = 0; bars.forEach(function (b) { b.classList.remove("on"); }); }
      bars[miniState.idx].classList.add("on"); miniState.idx++;
    }, 70);
  }

  window.SB = {
    toast: toast,
    activateStep: activateStep,
    openModal: openModal,
    closeModal: closeModal,
    miniPlay: miniPlay // v0.3：工作空间全局试听入口
  };
})();
