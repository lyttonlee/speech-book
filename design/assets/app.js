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
        document.querySelectorAll('[data-seg-panel="' + group.dataset.seg + '"]').forEach(function (p) {
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

  window.SB = { toast: toast, activateStep: activateStep, openModal: openModal, closeModal: closeModal };
})();
