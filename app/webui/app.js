const $ = (sel) => document.querySelector(sel);
const logEl = $("#log");
const chip = $("#status-chip");
const statusText = $("#status-text");
const busy = $("#busy");
const busyText = $("#busy-text");

let api = null;
let busyLock = false;

function appendLog(line) {
  const div = document.createElement("div");
  const s = String(line ?? "");
  let cls = "dim";
  if (/完成|成功|已写入|已注入|已恢复|OK/i.test(s)) cls = "ok";
  if (/错误|失败|异常|Error|Traceback/i.test(s)) cls = "err";
  div.className = cls;
  div.textContent = s;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

function setBusy(on, text) {
  busyLock = !!on;
  busy.classList.toggle("hidden", !on);
  if (text) busyText.textContent = text;
  ["btn-install", "btn-restore", "btn-fix"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.disabled = !!on;
  });
}

function setStatus(text, tone) {
  statusText.textContent = text;
  chip.className = `chip ${tone || "muted"}`;
}

async function refreshStatus() {
  if (!api) return;
  const path = $("#install-path").value.trim();
  const st = await api.status(path);
  if (!st.valid) {
    setStatus("无效安装目录", "danger");
    return;
  }
  if (st.legacy_injected) setStatus("检测到旧版汉化", "warn");
  else if (st.smooth_injected) setStatus("已汉化", "ok");
  else setStatus(st.has_backup ? "未汉化（有备份）" : "未汉化", "muted");
}

function switchView(name) {
  document.querySelectorAll(".nav-item").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === name);
  });
  document.querySelectorAll(".page").forEach((v) => v.classList.remove("active"));
  $(`#view-${name}`).classList.add("active");
  const map = { home: "汉化设置", log: "运行记录", about: "关于软件" };
  $("#page-title").textContent = map[name];
}

async function runJob(title, fn) {
  if (busyLock || !api) return;
  setBusy(true, title);
  appendLog(`—— ${title} ——`);
  switchView("log");
  try {
    const ok = await fn();
    appendLog(ok ? `[完成] ${title}成功` : `[失败] ${title}未完全成功`);
    await refreshStatus();
    await api.alert(
      title,
      ok
        ? `${title}成功。\n请完全退出并重启 Cursor 生效。`
        : `${title}未完全成功，请查看日志。\n如权限不足，请以管理员身份运行。`
    );
  } catch (e) {
    appendLog(`[异常] ${e}`);
    await api.alert(title, String(e));
  } finally {
    setBusy(false);
  }
}

function bind() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });

  $("#btn-install").addEventListener("click", () =>
    runJob("一键汉化", () =>
      api.install($("#install-path").value.trim(), $("#userdata-path").value.trim(), $("#langpack").checked)
    )
  );
  $("#btn-restore").addEventListener("click", async () => {
    const yes = await api.confirm("确认还原", "将移除汉化注入并恢复备份文件，是否继续？");
    if (!yes) return;
    runJob("一键还原", () => api.restore($("#install-path").value.trim()));
  });
  $("#btn-fix").addEventListener("click", () =>
    runJob("修复校验", () => api.fix($("#install-path").value.trim()))
  );
  $("#btn-refresh").addEventListener("click", refreshStatus);
  $("#btn-clear-log").addEventListener("click", () => { logEl.innerHTML = ""; });
  $("#btn-open-cursor").addEventListener("click", () => api.open_cursor($("#install-path").value.trim()));
  $("#btn-browse-install").addEventListener("click", async () => {
    const p = await api.browse_folder("选择 Cursor 安装目录");
    if (p) {
      $("#install-path").value = p;
      refreshStatus();
    }
  });
  $("#btn-browse-userdata").addEventListener("click", async () => {
    const p = await api.browse_folder("选择用户数据目录");
    if (p) $("#userdata-path").value = p;
  });
  $("#install-path").addEventListener("change", refreshStatus);
}

async function boot() {
  if (!(window.pywebview && window.pywebview.api)) {
    await new Promise((r) => {
      window.addEventListener("pywebviewready", r, { once: true });
      setTimeout(r, 600);
    });
  }
  api = window.pywebview && window.pywebview.api;
  bind();
  if (!api) {
    setStatus("桌面桥接未就绪", "danger");
    appendLog("[提示] 请使用 启动精美版GUI.bat 打开");
    return;
  }
  const init = await api.get_init();
  $("#install-path").value = init.install || "";
  $("#userdata-path").value = init.userdata || "";
  appendLog("就绪");
  await refreshStatus();
}

boot();
