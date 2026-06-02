document.addEventListener("DOMContentLoaded", () => {
    // ────────────────── Card Accordion Logic ──────────────────
    window.toggleCard = function(cardId) {
        const card = document.getElementById(cardId);
        if (!card) return;
        
        const isCollapsed = card.classList.contains("card-collapsed");
        
        // Always collapse both
        document.getElementById("card-task")?.classList.add("card-collapsed");
        document.getElementById("card-loop")?.classList.add("card-collapsed");
        
        // If it was collapsed before click, expand it now
        if (isCollapsed) {
            card.classList.remove("card-collapsed");
        }
    };

    // ─── Elements ───
    const startBtn = document.getElementById("start-task-btn");
    const taskNameInput = document.getElementById("task_name");
    const qtyInput = document.getElementById("task_qty");
    const taskStatus = document.getElementById("task-status");
    const taskListEl = document.getElementById("task-list");
    const terminalBody = document.getElementById("terminal-body");

    // Stats
    const statPending = document.getElementById("stat-pending");
    const statRunning = document.getElementById("stat-running");
    const statCompleted = document.getElementById("stat-completed");
    const statFailed = document.getElementById("stat-failed");

    // Logs state
    let taskLogs = { "sys": [{text: "系统就绪，等待任务创建...", type: "sys"}] };
    let currentLogTaskId = "sys";
    let logLocked = false;

    function switchLogView(taskId) {
        currentLogTaskId = taskId;
        terminalBody.innerHTML = "";
        let logs = taskLogs[taskId] || [];
        logs.forEach(renderSingleLog);
        
        const titleLabel = document.getElementById("current-task-label");
        if (titleLabel) {
            titleLabel.textContent = taskId === "sys" ? " - 系统日志" : ` - 任务 #${taskId}`;
        }
        
        document.querySelectorAll(".task-item").forEach(el => {
            if (parseInt(el.getAttribute("data-id")) === taskId) {
                el.classList.add("active-task");
            } else {
                el.classList.remove("active-task");
            }
        });
    }

    function renderSingleLog(entry) {
        const line = document.createElement("div");
        line.className = `log-line ${entry.type}`;
        line.textContent = entry.text;
        terminalBody.appendChild(line);
        if (!logLocked) {
            terminalBody.scrollTo({ top: terminalBody.scrollHeight, behavior: "smooth" });
        }
        if (terminalBody.childElementCount > 1000) {
            terminalBody.removeChild(terminalBody.firstChild);
        }
    }

    // ────────────────── Create Task ──────────────────
    const accountSelect = document.getElementById("account_select");
    const concurrencyInput = document.getElementById("task_concurrency");
    const showBrowserCb = document.getElementById("show_browser");
    const browserModeSelect = document.getElementById("browser_mode");
    const emailModeSelect = document.getElementById("email_mode");
    const customEmailGroup = document.getElementById("custom-email-group");
    const customEmailCount = document.getElementById("custom-email-count");
    let customEmailAvailable = 0;

    function loadCustomEmailCounts() {
        return fetch("/api/custom-emails")
            .then(r => r.json())
            .then(data => {
                customEmailAvailable = data.counts?.available || 0;
                updateEmailModeUi();
            })
            .catch(() => {
                customEmailAvailable = 0;
                updateEmailModeUi();
            });
    }

    function updateEmailModeUi() {
        const isCustom = ["custom", "microsoft"].includes(emailModeSelect?.value);
        if (customEmailGroup) customEmailGroup.style.display = isCustom ? "flex" : "none";
        if (customEmailCount) {
            customEmailCount.textContent = `当前可用 ${customEmailAvailable} 个未使用邮箱。任务创建后会先锁定，验证码提交成功后标记为已使用。`;
        }
    }

    emailModeSelect?.addEventListener("change", updateEmailModeUi);
    loadCustomEmailCounts();
    setInterval(loadCustomEmailCounts, 10000);
    updateEmailModeUi();

    // Load accounts for dropdown
    function loadAccountsForDropdown() {
        if (!accountSelect) return;
        fetch("/api/accounts")
            .then(r => r.json())
            .then(accounts => {
                const activeAccounts = accounts.filter(a => a.is_active && a.invite_url);
                const optionsHtml = '<option value="">✏️ 手动输入邀请链接...</option>' + 
                    activeAccounts.map(a => `<option value="${a.invite_url}" data-name="${a.name}">👥 账号：${a.name} (${a.invite_url.substring(0,25)}...)</option>`).join("");
                
                // Only update if changed (to prevent losing selection)
                const currentVal = accountSelect.value;
                accountSelect.innerHTML = optionsHtml;
                if (Array.from(accountSelect.options).some(o => o.value === currentVal)) {
                    accountSelect.value = currentVal;
                }
            });
    }

    if (accountSelect) {
        accountSelect.addEventListener("change", (e) => {
            const urlInput = document.getElementById("invite_url");
            if (e.target.value) {
                urlInput.value = e.target.value;
                const opt = e.target.options[e.target.selectedIndex];
                if (opt && opt.getAttribute("data-name")) {
                    taskNameInput.value = `邀请 - ${opt.getAttribute("data-name")}`;
                }
            } else {
                urlInput.value = "";
            }
        });
        loadAccountsForDropdown();
        setInterval(loadAccountsForDropdown, 10000);
    }

    startBtn.addEventListener("click", () => {
        const qty = parseInt(qtyInput.value) || 1;
        const conc = parseInt(concurrencyInput.value) || 1;
        const browserMode = browserModeSelect?.value || (showBrowserCb?.checked ? "local" : "bitbrowser");
        const showBrowser = browserMode === "local";
        const taskName = (taskNameInput.value || "").trim();
        const inviteUrl = (document.getElementById("invite_url").value || "").trim();
        const emailMode = emailModeSelect?.value || "temp";

        if (!inviteUrl) {
            taskStatus.style.color = "var(--danger)";
            taskStatus.textContent = "⚠️ 请填写邀请链接";
            document.getElementById("invite_url").focus();
            return;
        }

        if (["custom", "microsoft"].includes(emailMode)) {
            if (customEmailAvailable <= 0) {
                taskStatus.style.color = "var(--danger)";
                taskStatus.textContent = "⚠️ 自备邮箱池没有可用邮箱";
                return;
            }
            if (qty > customEmailAvailable) {
                taskStatus.style.color = "var(--danger)";
                taskStatus.textContent = `⚠️ 注册数量不能超过可用自备邮箱数量 (${customEmailAvailable})`;
                qtyInput.focus();
                return;
            }
        }

        startBtn.disabled = true;
        startBtn.textContent = "加入中...";

        fetch("/api/tasks", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                name: taskName,
                quantity: qty,
                concurrency: conc,
                show_browser: showBrowser,
                browser_mode: browserMode,
                invite_url: inviteUrl,
                email_mode: emailMode
            })
        }).then(async r => {
            const data = await r.json();
            if (!r.ok) throw new Error(data.detail || "创建任务失败");
            return data;
        }).then(data => {
            startBtn.disabled = false;
            startBtn.textContent = "加入队列";
            taskStatus.style.color = "var(--success)";
            taskStatus.textContent = `✅ ${data.name} 已创建 (${data.quantity}个, 并发${data.concurrency})`;
            setTimeout(() => taskStatus.textContent = "", 3000);
            appendLog(`系统: ${data.name} 已加入队列 (#${data.id}, ${data.quantity}个注册, 并发${data.concurrency})`, "sys");
            loadCustomEmailCounts();
            refreshTaskList();
        }).catch((err) => {
            startBtn.disabled = false;
            startBtn.textContent = "加入队列";
            taskStatus.style.color = "var(--danger)";
            taskStatus.textContent = `❌ ${err.message || "创建任务失败，请检查自备邮箱格式"}`;
        });
    });

    // ────────────────── Auto Loop Mode ──────────────────
    const startLoopBtn = document.getElementById("start-loop-btn");
    const stopLoopBtn = document.getElementById("stop-loop-btn");
    const loopQtyInput = document.getElementById("loop_qty");
    const loopConcurrencyInput = document.getElementById("loop_concurrency");
    const loopShowBrowserCb = document.getElementById("loop_show_browser");
    const loopBrowserModeSelect = document.getElementById("loop_browser_mode");
    const loopEmailModeSelect = document.getElementById("loop_email_mode");
    const loopRunModeSelect = document.getElementById("loop_run_mode");
    const loopScheduleStartInput = document.getElementById("loop_schedule_start");
    const loopScheduleStopInput = document.getElementById("loop_schedule_stop");
    const loopScheduleCollapse = document.getElementById("loop-schedule-collapse");
    const loopScheduleToggle = document.getElementById("loop-schedule-toggle");
    const loopScheduleSummary = document.getElementById("loop-schedule-summary");
    const loopSuccessRateInput = document.getElementById("loop_success_rate_stop_threshold");
    const loopAccountOrderBtn = document.getElementById("loop-account-order-btn");
    const loopAccountOrderSummary = document.getElementById("loop-account-order-summary");
    const loopAccountModal = document.getElementById("loop-account-modal");
    const loopAccountModalClose = document.getElementById("loop-account-modal-close");
    const loopAccountModalDone = document.getElementById("loop-account-modal-done");
    const loopAccountOrderEl = document.getElementById("loop-account-order");
    let loopAccounts = [];
    let loopAccountOrder = [];

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function updateLoopScheduleSummary() {
        if (!loopScheduleSummary) return;
        const start = loopScheduleStartInput?.value || "";
        const stop = loopScheduleStopInput?.value || "";
        loopScheduleSummary.textContent = start || stop ? `启动 ${start || "--:--"} / 停止 ${stop || "--:--"}` : "未设置";
    }

    function normalizeLoopOrder(accounts) {
        const activeIds = accounts.map(a => String(a.id));
        const kept = loopAccountOrder.filter(id => activeIds.includes(id));
        const added = activeIds.filter(id => !kept.includes(id));
        loopAccountOrder = [...kept, ...added];
    }

    function updateLoopAccountSummary() {
        if (!loopAccountOrderSummary) return;
        const selected = loopAccountOrder.length;
        const names = loopAccountOrder
            .map(id => loopAccounts.find(a => String(a.id) === id)?.name)
            .filter(Boolean)
            .slice(0, 3);
        loopAccountOrderSummary.textContent = selected
            ? `已选择 ${selected} 个账号：${names.join("、")}${selected > 3 ? "..." : ""}`
            : "未选择账号";
    }

    function renderLoopAccountOrder() {
        if (!loopAccountOrderEl) return;
        const byId = new Map(loopAccounts.map(a => [String(a.id), a]));
        const ordered = [
            ...loopAccountOrder.map(id => byId.get(id)).filter(Boolean),
            ...loopAccounts.filter(a => !loopAccountOrder.includes(String(a.id)))
        ];
        if (!ordered.length) {
            loopAccountOrderEl.innerHTML = '<div class="empty-hint">没有启用且带邀请链接的账号</div>';
            updateLoopAccountSummary();
            return;
        }
        loopAccountOrderEl.innerHTML = ordered.map((account, index) => {
            const id = String(account.id);
            const isSelected = loopAccountOrder.includes(id);
            const checked = isSelected ? "checked" : "";
            return `
                <div class="loop-account-row" data-id="${escapeHtml(id)}">
                    <input type="checkbox" class="loop-account-check" ${checked}>
                    <div>
                        <div class="loop-account-name">${escapeHtml(account.name || `账号 ${id}`)}</div>
                        <div class="loop-account-url">${escapeHtml(account.invite_url || "")}</div>
                    </div>
                    <div class="loop-account-actions">
                        <button class="btn-sm primary loop-account-up" type="button" ${!isSelected || index === 0 ? "disabled" : ""}>↑</button>
                        <button class="btn-sm primary loop-account-down" type="button" ${!isSelected || index === loopAccountOrder.length - 1 ? "disabled" : ""}>↓</button>
                    </div>
                </div>
            `;
        }).join("");
        updateLoopAccountSummary();
    }

    function loadLoopAccounts() {
        return fetch("/api/accounts")
            .then(r => r.json())
            .then(accounts => {
                loopAccounts = accounts.filter(a => a.is_active && a.invite_url);
                normalizeLoopOrder(loopAccounts);
                renderLoopAccountOrder();
            })
            .catch(() => {
                loopAccounts = [];
                renderLoopAccountOrder();
            });
    }

    loopScheduleToggle?.addEventListener("click", () => {
        loopScheduleCollapse?.classList.toggle("is-collapsed");
    });
    loopScheduleStartInput?.addEventListener("input", updateLoopScheduleSummary);
    loopScheduleStopInput?.addEventListener("input", updateLoopScheduleSummary);
    updateLoopScheduleSummary();

    loopAccountOrderBtn?.addEventListener("click", () => {
        loadLoopAccounts().then(() => {
            if (loopAccountModal) loopAccountModal.style.display = "flex";
        });
    });
    loopAccountModalClose?.addEventListener("click", () => {
        if (loopAccountModal) loopAccountModal.style.display = "none";
    });
    loopAccountModalDone?.addEventListener("click", () => {
        if (loopAccountModal) loopAccountModal.style.display = "none";
        updateLoopAccountSummary();
    });
    loopAccountModal?.addEventListener("click", (e) => {
        if (e.target === loopAccountModal) loopAccountModal.style.display = "none";
    });
    loopAccountOrderEl?.addEventListener("click", (e) => {
        const row = e.target.closest(".loop-account-row");
        if (!row) return;
        const id = row.getAttribute("data-id");
        const index = loopAccountOrder.indexOf(id);
        if (e.target.classList.contains("loop-account-up") && index > 0) {
            [loopAccountOrder[index - 1], loopAccountOrder[index]] = [loopAccountOrder[index], loopAccountOrder[index - 1]];
            renderLoopAccountOrder();
        }
        if (e.target.classList.contains("loop-account-down") && index >= 0 && index < loopAccountOrder.length - 1) {
            [loopAccountOrder[index], loopAccountOrder[index + 1]] = [loopAccountOrder[index + 1], loopAccountOrder[index]];
            renderLoopAccountOrder();
        }
    });
    loopAccountOrderEl?.addEventListener("change", (e) => {
        if (!e.target.classList.contains("loop-account-check")) return;
        const row = e.target.closest(".loop-account-row");
        const id = row?.getAttribute("data-id");
        if (!id) return;
        if (e.target.checked) {
            if (!loopAccountOrder.includes(id)) loopAccountOrder.push(id);
        } else {
            loopAccountOrder = loopAccountOrder.filter(item => item !== id);
        }
        renderLoopAccountOrder();
    });
    loadLoopAccounts();

    function updateAutoLoopStatus() {
        if(!startLoopBtn) return;
        fetch("/api/autoloop/status")
            .then(r => r.json())
            .then(data => {
                if (data.is_running) {
                    startLoopBtn.style.display = "none";
                    stopLoopBtn.style.display = "block";
                    loopQtyInput.value = data.quantity;
                    loopConcurrencyInput.value = data.concurrency;
                    if (loopShowBrowserCb) loopShowBrowserCb.checked = data.show_browser;
                    if (loopBrowserModeSelect) loopBrowserModeSelect.value = data.browser_mode || (data.show_browser ? "local" : "bitbrowser");
                    if(data.email_mode) loopEmailModeSelect.value = data.email_mode;
                    if(loopRunModeSelect) loopRunModeSelect.value = data.loop_run_mode || "infinite";
                    if(loopSuccessRateInput) loopSuccessRateInput.value = data.success_rate_stop_threshold || 0;
                    if(Array.isArray(data.account_order) && data.account_order.length) {
                        loopAccountOrder = data.account_order.map(String);
                        updateLoopAccountSummary();
                    }
                    if(data.schedule_start) loopScheduleStartInput.value = data.schedule_start;
                    if(data.schedule_stop) loopScheduleStopInput.value = data.schedule_stop;
                    updateLoopScheduleSummary();
                    
                    loopQtyInput.disabled = true;
                    loopConcurrencyInput.disabled = true;
                    if (loopShowBrowserCb) loopShowBrowserCb.disabled = true;
                    if (loopBrowserModeSelect) loopBrowserModeSelect.disabled = true;
                    loopEmailModeSelect.disabled = true;
                    if (loopRunModeSelect) loopRunModeSelect.disabled = true;
                    if (loopSuccessRateInput) loopSuccessRateInput.disabled = true;
                    if (loopAccountOrderBtn) loopAccountOrderBtn.disabled = true;
                    loopScheduleStartInput.disabled = true;
                    loopScheduleStopInput.disabled = true;
                } else {
                    startLoopBtn.style.display = "block";
                    stopLoopBtn.style.display = "none";
                    startLoopBtn.disabled = false;
                    startLoopBtn.textContent = "启动自动模式";
                    stopLoopBtn.textContent = "🛑 停止运行";
                    loopQtyInput.disabled = false;
                    loopConcurrencyInput.disabled = false;
                    if (loopShowBrowserCb) loopShowBrowserCb.disabled = false;
                    if (loopBrowserModeSelect) loopBrowserModeSelect.disabled = false;
                    loopEmailModeSelect.disabled = false;
                    if (loopRunModeSelect) loopRunModeSelect.disabled = false;
                    if (loopSuccessRateInput) loopSuccessRateInput.disabled = false;
                    if (loopAccountOrderBtn) loopAccountOrderBtn.disabled = false;
                    loopScheduleStartInput.disabled = false;
                    loopScheduleStopInput.disabled = false;
                }
            });
    }

    if (startLoopBtn) {
        startLoopBtn.addEventListener("click", async () => {
            const loopRunMode = loopRunModeSelect?.value || "infinite";
            const runModeText = loopRunMode === "once" ? "一轮：账号按顺序轮完后自动停止" : "无限：账号轮完后继续下一轮";
            if (!confirm(`即将启动全自动模式（${runModeText}）。确认启动？`)) return;
            const loopEmailMode = loopEmailModeSelect?.value || "temp";
            const loopQty = parseInt(loopQtyInput.value) || 10;
            const loopBrowserMode = loopBrowserModeSelect?.value || (loopShowBrowserCb?.checked ? "local" : "bitbrowser");
            await loadLoopAccounts();
            const selectedAccountOrder = loopAccountOrder.filter(id => loopAccounts.some(a => String(a.id) === id));
            const successRateStopThreshold = Math.max(0, Math.min(parseFloat(loopSuccessRateInput?.value || "0") || 0, 100));
            if (selectedAccountOrder.length === 0) {
                appendLog("系统: 请至少选择一个启用且带邀请链接的账号", "sys");
                return;
            }
            if (["custom", "microsoft"].includes(loopEmailMode)) {
                if (customEmailAvailable <= 0) {
                    appendLog("系统: 全自动模式需要可用自备邮箱，请先导入邮箱池", "sys");
                    return;
                }
                if (loopQty > customEmailAvailable) {
                    appendLog(`系统: 全自动子任务注册量不能超过可用自备邮箱数量 (${customEmailAvailable})`, "sys");
                    return;
                }
            }
            startLoopBtn.disabled = true;
            startLoopBtn.textContent = "启动中...";
            fetch("/api/autoloop/start", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ 
                    quantity: loopQty, 
                    concurrency: parseInt(loopConcurrencyInput.value) || 1, 
                    show_browser: loopBrowserMode === "local",
                    browser_mode: loopBrowserMode,
                    email_mode: loopEmailMode,
                    invite_url: "auto",
                    name: "autoloop",
                    account_order: selectedAccountOrder,
                    loop_run_mode: loopRunMode,
                    success_rate_stop_threshold: successRateStopThreshold,
                    schedule_start: loopScheduleStartInput.value || "",
                    schedule_stop: loopScheduleStopInput.value || ""
                })
            }).then(() => updateAutoLoopStatus());
        });

        stopLoopBtn.addEventListener("click", () => {
            if (!confirm("确认停止全自动模式？（当前正在运行的子任务也会被停止）")) return;
            stopLoopBtn.disabled = true;
            stopLoopBtn.textContent = "停止中...";
            fetch("/api/autoloop/stop", { method: "POST" })
              .then(() => updateAutoLoopStatus());
        });
        
        setInterval(updateAutoLoopStatus, 3000);
        updateAutoLoopStatus();
    }

    // ────────────────── Task List ──────────────────
    function refreshTaskList() {
        fetch("/api/tasks")
            .then(r => r.json())
            .then(tasks => {
                // Update stats
                let pending = 0, running = 0, completed = 0, failed = 0;
                tasks.forEach(t => {
                    if (t.status === "pending") pending += t.quantity;
                    else if (t.status === "running") {
                        running += (t.quantity - t.completed - t.failed);
                        completed += t.completed;
                        failed += t.failed;
                    } else {
                        completed += t.completed;
                        failed += t.failed;
                    }
                });
                statPending.textContent = pending;
                statRunning.textContent = running;
                statCompleted.textContent = completed;
                statFailed.textContent = failed;

                if (tasks.length === 0) {
                    taskListEl.innerHTML = '<div class="empty-hint">暂无任务</div>';
                    return;
                }
                
                // Auto switch focus to running task if current one is not active
                let currentItem = tasks.find(t => t.id === currentLogTaskId);
                if (!currentItem || !["running", "pending", "stopping"].includes(currentItem.status)) {
                    let activeTask = tasks.find(t => t.status === "running") || tasks.find(t => t.status === "stopping") || tasks.find(t => t.status === "pending");
                    if (activeTask && currentLogTaskId !== activeTask.id) {
                        switchLogView(activeTask.id);
                    }
                }

                // Show latest 10
                taskListEl.innerHTML = tasks.slice(0, 10).map(t => {
                    let badgeClass = t.status;
                    let badgeText = { pending: "排队中", running: "运行中", completed: "已完成", stopped: "已停止", stopping: "停止中..." }[t.status] || t.status;
                    let activeClass = t.id === currentLogTaskId ? " active-task" : "";
                    return `
                        <div class="task-item${activeClass}" data-id="${t.id}" style="cursor: pointer;">
                            <div class="task-left">
                                <span class="task-id">${t.name || `任务 #${t.id}`}</span>
                                <span class="task-meta">#${t.id} · ${t.created_at} · ${t.quantity}个 · 并发${t.concurrency}</span>
                            </div>
                            <div class="task-right">
                                <div class="task-counts" style="display:flex; flex-direction:column; align-items:flex-end;">
                                    <div><span class="ok" title="成功">${t.completed}</span> / <span class="fail" title="失败">${t.failed}</span></div>
                                    <div style="font-size:0.7rem; color:var(--text-dim); margin-top:2px;">入池: <span style="color:var(--success)">${t.imported || 0}</span></div>
                                </div>
                                <span class="badge ${badgeClass}">${badgeText}</span>
                                ${["pending", "running"].includes(t.status) ? `<button class="btn-sm danger stop-task-btn" data-id="${t.id}" style="margin-left: 8px;">停止</button>` : ''}
                            </div>
                        </div>
                    `;
                }).join("");
            });
    }

    taskListEl.addEventListener("click", (e) => {
        if (e.target.classList.contains("stop-task-btn")) {
            const taskId = parseInt(e.target.getAttribute("data-id"));
            if (confirm(`确认要停止任务 #${taskId} 吗？`)) {
                e.target.disabled = true;
                e.target.textContent = "停止中...";
                fetch("/api/tasks/stop", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ ids: [taskId] })
                }).then(() => refreshTaskList());
            }
            return;
        }

        const item = e.target.closest(".task-item");
        if (item) {
            const taskId = parseInt(item.getAttribute("data-id"));
            if (taskId) switchLogView(taskId);
        }
    });

    setInterval(refreshTaskList, 2000);
    refreshTaskList();

    // ────────────────── WebSocket Logs ──────────────────
    let protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    let wsUrl = `${protocol}//${window.location.host}/ws/logs`;

    function connectWS() {
        const ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
            const msg = event.data;
            if (msg === "__STATE_UPDATE__") {
                refreshTaskList();
                return;
            }
            let type = "info";
            if (msg.includes("✅") || msg.includes("🎉")) type = "success";
            if (msg.includes("❌") || msg.includes("⚠️")) type = "error";
            if (msg.includes("系统") || msg.includes("📋") || msg.includes("🏁")) type = "sys";
            appendLog(msg, type);
        };

        ws.onclose = () => {
            setTimeout(connectWS, 3000);
        };
    }

    function appendLog(text, type = "info") {
        let tid = null;
        let match = text.match(/\[任务#(\d+)-\d+\]/);
        if (!match) match = text.match(/任务 #(\d+) /);
        if (match) tid = parseInt(match[1]);

        let entry = { text, type };
        if (tid) {
            if (!taskLogs[tid]) taskLogs[tid] = [];
            taskLogs[tid].push(entry);
        } else {
            taskLogs["sys"].push(entry);
        }

        if (tid === currentLogTaskId || (!tid && currentLogTaskId === "sys")) {
            renderSingleLog(entry);
        }
    }

    const expandBtn = document.getElementById("expand-terminal-btn");
    if (expandBtn) {
        expandBtn.addEventListener("click", () => {
            const card = document.querySelector(".terminal-card");
            card.classList.toggle("fullscreen");
            expandBtn.textContent = card.classList.contains("fullscreen") ? "收起 ✖" : "展开 ⛶";
            if (!card.classList.contains("fullscreen") && !logLocked) {
                terminalBody.scrollTo({ top: terminalBody.scrollHeight, behavior: "smooth" });
            }
        });
    }

    const lockBtn = document.getElementById("lock-terminal-btn");
    if (lockBtn) {
        lockBtn.addEventListener("click", () => {
            logLocked = !logLocked;
            lockBtn.textContent = logLocked ? "🔒" : "🔓";
            lockBtn.title = logLocked ? "点击解锁日志滚动" : "点击锁定日志滚动";
            if (!logLocked) {
                terminalBody.scrollTo({ top: terminalBody.scrollHeight, behavior: "smooth" });
            }
        });
    }

    switchLogView("sys");
    connectWS();
});
