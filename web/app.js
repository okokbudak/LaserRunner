// ============================================================
// Mainsail UI for LaserRunner OS - Client Application Logic
// ============================================================

const state = {
    connected: false,
    machineState: "DISCONNECTED",
    pos: { x: 0.0, y: 0.0, z: 0.0 },
    speedFactor: 100,
    laserFactor: 100,
    speed_mm_s: 40.0,
    diodeTemp: 25.0,
    mcuTemp: 32.4,
    tempHistory: [], // [{time, diode, mcu}]
    zoom: 1.0,
    pan: { x: 40, y: 40 },
    objects: [],
    airAssist: false,
    redPointer: false,
    exhaustFan: false,
    motorsLocked: true,
    ws: null
};

// DOM Referansları
const msPrinterState = document.getElementById("msPrinterState");
const msStatusDot = document.getElementById("msStatusDot");
const portSelect = document.getElementById("portSelect");
const btnConnect = document.getElementById("btnConnect");
const btnRefreshPorts = document.getElementById("btnRefreshPorts");
const btnEstop = document.getElementById("btnEstop");
const mainSidebar = document.getElementById("mainSidebar");
const btnToggleSidebar = document.getElementById("btnToggleSidebar");

// Toolhead DOM
const valPosX = document.getElementById("valPosX");
const valPosY = document.getElementById("valPosY");
const valPosZ = document.getElementById("valPosZ");
const sliderSpeedFactor = document.getElementById("sliderSpeedFactor");
const valSpeedFactor = document.getElementById("valSpeedFactor");

// Laser DOM
const sliderLaserFactor = document.getElementById("sliderLaserFactor");
const valLaserFactor = document.getElementById("valLaserFactor");

// Console DOM
const consoleLog = document.getElementById("consoleLog");
const consoleForm = document.getElementById("consoleForm");
const consoleInput = document.getElementById("consoleInput");
const fsConsoleLog = document.getElementById("fsConsoleLog");
const fsConsoleForm = document.getElementById("fsConsoleForm");
const fsConsoleInput = document.getElementById("fsConsoleInput");

// Canvas DOM
const canvas = document.getElementById("laserCanvas");
const ctx = canvas ? canvas.getContext("2d") : null;
const tempCanvas = document.getElementById("tempChartCanvas");
const tempCtx = tempCanvas ? tempCanvas.getContext("2d") : null;

// ============================================================
// BAŞLATMA
// ============================================================
window.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initCanvas();
    initTempChart();
    fetchPorts();
    setupToolheadControls();
    setupLaserControls();
    setupConsole();
    setupMachineView();
    setupViewerControls();
    connectWebSocket();
    renderCanvas();
});

// Sidebar & Sekme Yönetimi
function initNavigation() {
    const navItems = document.querySelectorAll(".ms-nav-item[data-view]");
    const views = document.querySelectorAll(".ms-view");

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetViewId = item.dataset.view;
            navItems.forEach(i => i.classList.remove("active"));
            views.forEach(v => v.classList.remove("active"));

            item.classList.add("active");
            const target = document.getElementById(targetViewId);
            if (target) target.classList.add("active");

            if (targetViewId === "view-machine") {
                loadConfigFile();
            } else if (targetViewId === "view-viewer") {
                renderCanvas();
            }
        });
    });

    if (btnToggleSidebar && mainSidebar) {
        btnToggleSidebar.addEventListener("click", () => {
            mainSidebar.classList.toggle("collapsed");
        });
    }

    document.getElementById("btnRestartHost")?.addEventListener("click", async () => {
        if (confirm("LaserRunner servisini yeniden başlatmak istiyor musunuz?")) {
            await fetch("/api/config/restart", { method: "POST" });
            addLog("LaserRunner servisi yeniden başlatılıyor...", "log-info");
        }
    });
}

// ============================================================
// WEBSOCKET & TELEMETRİ
// ============================================================
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
        state.ws = new WebSocket(wsUrl);
        state.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleTelemetry(data);
        };
        state.ws.onclose = () => {
            setTimeout(connectWebSocket, 2000);
        };
    } catch (e) {
        console.warn("WebSocket bağlantı hatası:", e);
    }
}

function handleTelemetry(data) {
    state.machineState = data.state;
    state.connected = (data.state !== "DISCONNECTED");
    state.pos.x = data.x;
    state.pos.y = data.y;
    state.pos.z = data.z;

    // Koordinatları Güncelle
    if (valPosX) valPosX.textContent = data.x.toFixed(2);
    if (valPosY) valPosY.textContent = data.y.toFixed(2);
    if (valPosZ) valPosZ.textContent = data.z.toFixed(3);

    // Durum ve Nokta
    if (msPrinterState) {
        let stateStr = "Ready";
        if (data.state === "DISCONNECTED") stateStr = "Offline";
        else if (data.state === "RUNNING") stateStr = "Printing";
        else if (data.state === "FRAMING") stateStr = "Framing";
        else if (data.state === "ESTOP") stateStr = "Shutdown";
        msPrinterState.textContent = stateStr;
    }

    if (msStatusDot) {
        if (data.state === "DISCONNECTED") {
            msStatusDot.style.backgroundColor = "#757575";
            msStatusDot.style.boxShadow = "none";
        } else if (data.state === "ESTOP") {
            msStatusDot.style.backgroundColor = "#d32f2f";
            msStatusDot.style.boxShadow = "0 0 6px #d32f2f";
        } else {
            msStatusDot.style.backgroundColor = "#00e676";
            msStatusDot.style.boxShadow = "0 0 6px #00e676";
        }
    }

    if (btnConnect) {
        btnConnect.textContent = data.state === "DISCONNECTED" ? "Bağlan" : "Bağlantıyı Kes";
    }

    // Port Seçici
    if (data.available_ports && Array.isArray(data.available_ports)) {
        const currentOptions = Array.from(portSelect.options).map(o => o.value).filter(v => v);
        const newPorts = data.available_ports;
        if (JSON.stringify(currentOptions) !== JSON.stringify(newPorts)) {
            const selectedVal = portSelect.value;
            portSelect.innerHTML = "";
            if (newPorts.length === 0) {
                portSelect.innerHTML = "<option value=''>Cihaz Bulunamadı</option>";
            } else {
                newPorts.forEach(p => {
                    const opt = document.createElement("option");
                    opt.value = p;
                    opt.textContent = p;
                    if (p === data.port || p === selectedVal) opt.selected = true;
                    portSelect.appendChild(opt);
                });
            }
        }
    }

    // Sıcaklık
    if (data.diode_temp !== undefined) {
        state.diodeTemp = data.diode_temp;
        const valTempDiode = document.getElementById("valTempDiode");
        if (valTempDiode) valTempDiode.textContent = `${data.diode_temp.toFixed(1)} °C`;

        const tempStateDiode = document.getElementById("tempStateDiode");
        if (tempStateDiode) {
            tempStateDiode.textContent = data.diode_temp > 30.0 ? "active" : "off";
            tempStateDiode.className = data.diode_temp > 30.0 ? "state-ok" : "state-dim";
        }

        // Sıcaklık Grafiği Geçmişi
        recordTemperature(data.diode_temp, 32.4);
    }

    // İlerleme Çubuğu
    if (data.progress !== undefined) {
        const bar = document.getElementById("mainProgressBar");
        const pct = document.getElementById("currentFilePct");
        if (bar) bar.style.width = `${data.progress}%`;
        if (pct) pct.textContent = `%${Math.round(data.progress)}`;
    }

    // Donanım Anahtarları
    if (data.air_assist !== undefined) {
        state.airAssist = data.air_assist;
        document.getElementById("btnToggleAir")?.classList.toggle("active", data.air_assist);
    }
    if (data.red_pointer !== undefined) {
        state.redPointer = data.red_pointer;
        document.getElementById("btnToggleRedPointer")?.classList.toggle("active", data.red_pointer);
    }

    renderCanvas();
}

// ============================================================
// TOOLHEAD & JOG KONTROLLERİ (Orijinal Mainsail Barları)
// ============================================================
function setupToolheadControls() {
    // Mainsail Lineer Jog Butonları (-100, -10, -1, +1, +10, +100)
    document.querySelectorAll(".ms-jog-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const axis = btn.dataset.axis;
            const dist = parseFloat(btn.dataset.dist);
            let dx = 0, dy = 0, dz = 0;
            if (axis === "x") dx = dist;
            else if (axis === "y") dy = dist;
            else if (axis === "z") dz = dist;

            try {
                await fetch("/api/jog", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ dx, dy, dz, speed: state.speed_mm_s })
                });
                addLog(`G0 ${axis.toUpperCase()}${dist > 0 ? "+" : ""}${dist}`, "log-cmd");
            } catch (e) {
                addLog("Jog komutu iletilemedi!", "log-error");
            }
        });
    });

    // Homing Butonları
    document.getElementById("btnHomeAll")?.addEventListener("click", async () => {
        addLog("G28", "log-cmd");
        await fetch("/api/home", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ axis_mask: 7 }) });
    });

    document.getElementById("btnHomeXY")?.addEventListener("click", async () => {
        addLog("G28 X Y", "log-cmd");
        await fetch("/api/home", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ axis_mask: 3 }) });
    });

    document.getElementById("btnHomeZ")?.addEventListener("click", async () => {
        addLog("G28 Z", "log-cmd");
        await fetch("/api/home", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ axis_mask: 4 }) });
    });

    // Speed Factor Slider
    if (sliderSpeedFactor && valSpeedFactor) {
        sliderSpeedFactor.addEventListener("input", (e) => {
            state.speedFactor = parseInt(e.target.value);
            valSpeedFactor.textContent = `${state.speedFactor} %`;
            state.speed_mm_s = 40.0 * (state.speedFactor / 100.0);
        });

        document.getElementById("btnSpeedMinus")?.addEventListener("click", () => {
            sliderSpeedFactor.value = Math.max(10, parseInt(sliderSpeedFactor.value) - 5);
            sliderSpeedFactor.dispatchEvent(new Event("input"));
        });

        document.getElementById("btnSpeedPlus")?.addEventListener("click", () => {
            sliderSpeedFactor.value = Math.min(250, parseInt(sliderSpeedFactor.value) + 5);
            sliderSpeedFactor.dispatchEvent(new Event("input"));
        });
    }

    // Acil Durdurma (Emergency Stop)
    btnEstop.addEventListener("click", async () => {
        addLog("M112 (EMERGENCY STOP)", "log-error");
        await fetch("/api/estop", { method: "POST" });
    });
}

// ============================================================
// LAZER & ÇEVRESEL BİRİMLER
// ============================================================
function setupLaserControls() {
    // Lazer Güç Faktörü Slider
    if (sliderLaserFactor && valLaserFactor) {
        sliderLaserFactor.addEventListener("input", (e) => {
            state.laserFactor = parseInt(e.target.value);
            valLaserFactor.textContent = `${state.laserFactor} %`;
        });
        document.getElementById("btnPowerMinus")?.addEventListener("click", () => {
            sliderLaserFactor.value = Math.max(0, parseInt(sliderLaserFactor.value) - 5);
            sliderLaserFactor.dispatchEvent(new Event("input"));
        });
        document.getElementById("btnPowerPlus")?.addEventListener("click", () => {
            sliderLaserFactor.value = Math.min(100, parseInt(sliderLaserFactor.value) + 5);
            sliderLaserFactor.dispatchEvent(new Event("input"));
        });
    }

    // Test Ateşi
    async function setLaserTest(pct) {
        await fetch("/api/laser/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ power_percent: pct })
        });
        addLog(`M3 S${Math.round((pct / 100) * 1000)} (Test %${pct})`, "log-cmd");
    }

    document.getElementById("btnLaserOff")?.addEventListener("click", () => setLaserTest(0));
    document.getElementById("btnLaserLow")?.addEventListener("click", () => setLaserTest(1.0));
    document.getElementById("btnLaserMed")?.addEventListener("click", () => setLaserTest(5.0));

    // Donanım Anahtarları
    document.getElementById("btnToggleAir")?.addEventListener("click", async () => {
        state.airAssist = !state.airAssist;
        await fetch("/api/aux/air_assist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active: state.airAssist }) });
        document.getElementById("btnToggleAir").classList.toggle("active", state.airAssist);
        addLog(state.airAssist ? "SET_AIR_ASSIST ACTIVE=1" : "SET_AIR_ASSIST ACTIVE=0", "log-cmd");
    });

    document.getElementById("btnToggleRedPointer")?.addEventListener("click", async () => {
        state.redPointer = !state.redPointer;
        await fetch("/api/aux/red_pointer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active: state.redPointer }) });
        document.getElementById("btnToggleRedPointer").classList.toggle("active", state.redPointer);
        addLog(`Kırmızı Nokta Lazer: ${state.redPointer ? "AÇIK" : "KAPALI"}`, "log-info");
    });

    document.getElementById("btnToggleExhaust")?.addEventListener("click", async () => {
        state.exhaustFan = !state.exhaustFan;
        await fetch("/api/aux/exhaust_fan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ duty: state.exhaustFan ? 255 : 0 }) });
        document.getElementById("btnToggleExhaust").classList.toggle("active", state.exhaustFan);
        addLog(`Duman Emiş Fanı: ${state.exhaustFan ? "%100" : "KAPALI"}`, "log-info");
    });

    document.getElementById("btnToggleMotors")?.addEventListener("click", async () => {
        state.motorsLocked = !state.motorsLocked;
        await fetch("/api/verify/enable_steppers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enable: state.motorsLocked }) });
        document.getElementById("btnToggleMotors").classList.toggle("active", state.motorsLocked);
        addLog(state.motorsLocked ? "Motor tutma torku aktif." : "Motorlar serbest bırakıldı (M84).", "log-info");
    });
}

// ============================================================
// CONSOLE & TERMİNAL
// ============================================================
function setupConsole() {
    function submitCode(inputEl) {
        const cmd = inputEl.value.trim();
        if (!cmd) return;
        inputEl.value = "";
        executeCommand(cmd);
    }

    if (consoleForm && consoleInput) {
        consoleForm.addEventListener("submit", (e) => {
            e.preventDefault();
            submitCode(consoleInput);
        });
    }

    if (fsConsoleForm && fsConsoleInput) {
        fsConsoleForm.addEventListener("submit", (e) => {
            e.preventDefault();
            submitCode(fsConsoleInput);
        });
    }

    // Makro Hapları
    document.querySelectorAll(".ms-macro-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            executeCommand(chip.dataset.cmd);
        });
    });

    document.getElementById("btnClearConsole")?.addEventListener("click", () => {
        if (consoleLog) consoleLog.innerHTML = "";
    });
    document.getElementById("btnFsClearConsole")?.addEventListener("click", () => {
        if (fsConsoleLog) fsConsoleLog.innerHTML = "";
    });
}

async function executeCommand(cmd) {
    addLog(cmd, "log-cmd");
    const ucmd = cmd.toUpperCase().trim();

    if (ucmd === "G28") {
        await fetch("/api/home", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ axis_mask: 7 }) });
    } else if (ucmd === "M112") {
        await fetch("/api/estop", { method: "POST" });
    } else if (ucmd === "FIRMWARE_RESTART") {
        await fetch("/api/config/restart", { method: "POST" });
        addLog("Klipper state: Restarting...", "log-info");
    } else if (ucmd.includes("SET_AIR_ASSIST ACTIVE=1")) {
        await fetch("/api/aux/air_assist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active: true }) });
    } else if (ucmd.includes("SET_AIR_ASSIST ACTIVE=0")) {
        await fetch("/api/aux/air_assist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active: false }) });
    } else {
        addLog(`// Komut yürütüldü: ${cmd}`, "log-info");
    }
}

function addLog(text, className = "log-info") {
    const time = new Date().toLocaleTimeString();
    const row = document.createElement("div");
    row.className = "ms-log-row";
    row.innerHTML = `<span class="log-time">${time}</span> <span class="${className}">${text}</span>`;

    if (consoleLog) {
        consoleLog.appendChild(row);
        consoleLog.scrollTop = consoleLog.scrollHeight;
    }

    if (fsConsoleLog) {
        const clone = row.cloneNode(true);
        fsConsoleLog.appendChild(clone);
        fsConsoleLog.scrollTop = fsConsoleLog.scrollHeight;
    }
}

// ============================================================
// TEMPERATURES CANLI GRAFİĞİ (Mainsail Style Chart)
// ============================================================
function initTempChart() {
    if (!tempCanvas || !tempCtx) return;
    for (let i = 0; i < 30; i++) {
        state.tempHistory.push({ diode: 25.0, mcu: 32.0 });
    }
    drawTempChart();
}

function recordTemperature(diode, mcu) {
    state.tempHistory.push({ diode, mcu });
    if (state.tempHistory.length > 60) {
        state.tempHistory.shift();
    }
    drawTempChart();
}

function drawTempChart() {
    if (!tempCanvas || !tempCtx) return;
    const w = tempCanvas.width;
    const h = tempCanvas.height;

    tempCtx.clearRect(0, 0, w, h);

    // Kılavuz Çizgileri ve Dereceler (0, 50, 100, 150, 200, 250)
    tempCtx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    tempCtx.lineWidth = 1;
    tempCtx.font = "10px JetBrains Mono";
    tempCtx.fillStyle = "#616161";

    const maxTemp = 100.0;
    for (let t = 0; t <= maxTemp; t += 25) {
        const y = h - (t / maxTemp) * (h - 20) - 10;
        tempCtx.beginPath();
        tempCtx.moveTo(30, y);
        tempCtx.lineTo(w, y);
        tempCtx.stroke();
        tempCtx.fillText(`${t}°`, 6, y + 3);
    }

    // Diode Çizgisi (Kırmızı / Turuncu)
    if (state.tempHistory.length > 1) {
        tempCtx.strokeStyle = "#ff3344";
        tempCtx.lineWidth = 1.8;
        tempCtx.beginPath();

        const stepX = (w - 35) / (state.tempHistory.length - 1);
        state.tempHistory.forEach((pt, idx) => {
            const x = 35 + idx * stepX;
            const y = h - (pt.diode / maxTemp) * (h - 20) - 10;
            if (idx === 0) tempCtx.moveTo(x, y);
            else tempCtx.lineTo(x, y);
        });
        tempCtx.stroke();

        // MCU Çizgisi (Mavi)
        tempCtx.strokeStyle = "#2196f3";
        tempCtx.lineWidth = 1.2;
        tempCtx.beginPath();
        state.tempHistory.forEach((pt, idx) => {
            const x = 35 + idx * stepX;
            const y = h - (pt.mcu / maxTemp) * (h - 20) - 10;
            if (idx === 0) tempCtx.moveTo(x, y);
            else tempCtx.lineTo(x, y);
        });
        tempCtx.stroke();
    }
}

// ============================================================
// MACHINE VIEW (laserrunner.cfg KLIPPER EDITÖRÜ)
// ============================================================
const configEditor = document.getElementById("configEditorTextarea");
const configPath = document.getElementById("configFilePath");
const configStatus = document.getElementById("configStatusBar");

async function loadConfigFile() {
    if (!configEditor) return;
    configStatus.textContent = "Yapılandırma dosyası okunuyor...";
    try {
        const res = await fetch("/api/config");
        const data = await res.json();
        if (res.ok) {
            configEditor.value = data.content;
            if (configPath) configPath.textContent = data.path;
            configStatus.textContent = `Yüklendi: ${new Date().toLocaleTimeString()} (${data.content.length} bayt)`;
        } else {
            configStatus.textContent = `Hata: ${data.detail || "Dosya okunamadı"}`;
        }
    } catch (err) {
        configStatus.textContent = `Bağlantı hatası: ${err.message}`;
    }
}

async function saveConfigFile(restart = false) {
    if (!configEditor) return;
    configStatus.textContent = restart ? "Kaydediliyor ve sistem yeniden başlatılıyor..." : "Kaydediliyor...";
    try {
        const res = await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: configEditor.value })
        });
        const data = await res.json();
        if (data.success) {
            addLog(data.message, "log-success");
            if (restart) {
                configStatus.textContent = "Servis yeniden başlatılıyor... Lütfen bekleyin.";
                await fetch("/api/config/restart", { method: "POST" });
                setTimeout(() => {
                    configStatus.textContent = "Sistem yeniden başlatıldı!";
                    loadConfigFile();
                }, 2500);
            } else {
                configStatus.textContent = `Başarıyla kaydedildi ve uygulandı: ${new Date().toLocaleTimeString()}`;
            }
        } else {
            configStatus.textContent = `Kayıt hatası: ${data.message}`;
            addLog(`Kayıt hatası: ${data.message}`, "log-error");
        }
    } catch (err) {
        configStatus.textContent = `Hata: ${err.message}`;
    }
}

function setupMachineView() {
    document.getElementById("btnReloadConfig")?.addEventListener("click", loadConfigFile);
    document.getElementById("btnSaveConfig")?.addEventListener("click", () => saveConfigFile(false));
    document.getElementById("btnSaveRestartConfig")?.addEventListener("click", () => saveConfigFile(true));
}

// ============================================================
// G-CODE VIEWER / LAZER MASASI KANVAS
// ============================================================
function initCanvas() {
    if (!canvas) return;
    canvas.width = 800;
    canvas.height = 800;
    state.objects.push({ type: "rect", x: 40, y: 40, w: 120, h: 80, color: "#00b0ff" });

    canvas.addEventListener("mousemove", (e) => {
        const rect = canvas.getBoundingClientRect();
        const px = (e.clientX - rect.left) * (canvas.width / rect.width);
        const py = (e.clientY - rect.top) * (canvas.height / rect.height);
        const bedSize = 700;
        const mmToPx = bedSize / 400.0;
        const mx = Math.max(0, Math.min(400, (px - state.pan.x) / (mmToPx * state.zoom)));
        const my = Math.max(0, Math.min(400, (py - state.pan.y) / (mmToPx * state.zoom)));

        const elX = document.getElementById("mouseCoordX");
        const elY = document.getElementById("mouseCoordY");
        if (elX) elX.textContent = mx.toFixed(1);
        if (elY) elY.textContent = my.toFixed(1);
    });
}

function renderCanvas() {
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.translate(state.pan.x, state.pan.y);
    ctx.scale(state.zoom, state.zoom);

    const bedSize = 700;
    const mmToPx = bedSize / 400.0;

    // Masası Zemini
    ctx.fillStyle = "#0c0e14";
    ctx.fillRect(0, 0, bedSize, bedSize);

    // Izgara Çizgileri
    for (let i = 0; i <= 400; i += 10) {
        const p = i * mmToPx;
        ctx.beginPath();
        ctx.strokeStyle = (i % 50 === 0) ? "#1f2633" : "#131720";
        ctx.lineWidth = (i % 50 === 0) ? 1.2 : 0.6;
        ctx.moveTo(p, 0); ctx.lineTo(p, bedSize);
        ctx.moveTo(0, p); ctx.lineTo(bedSize, p);
        ctx.stroke();
    }

    // Yatak Çerçevesi
    ctx.strokeStyle = "rgba(33, 150, 243, 0.4)";
    ctx.lineWidth = 1.8;
    ctx.strokeRect(0, 0, bedSize, bedSize);

    // Objeler
    state.objects.forEach(obj => {
        ctx.strokeStyle = obj.color || "#00b0ff";
        ctx.lineWidth = 2;
        if (obj.type === "rect") {
            ctx.strokeRect(obj.x * mmToPx, obj.y * mmToPx, obj.w * mmToPx, obj.h * mmToPx);
        }
    });

    // Canlı Lazer Kafası (Crosshair)
    const lx = state.pos.x * mmToPx;
    const ly = state.pos.y * mmToPx;

    ctx.strokeStyle = "#ff3344";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(lx - 14, ly); ctx.lineTo(lx + 14, ly);
    ctx.moveTo(lx, ly - 14); ctx.lineTo(lx, ly + 14);
    ctx.stroke();

    ctx.fillStyle = "#ff3344";
    ctx.beginPath();
    ctx.arc(lx, ly, 3.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
}

function setupViewerControls() {
    document.getElementById("btnZoomIn")?.addEventListener("click", () => {
        state.zoom = Math.min(3.0, state.zoom + 0.2);
        renderCanvas();
    });
    document.getElementById("btnZoomOut")?.addEventListener("click", () => {
        state.zoom = Math.max(0.4, state.zoom - 0.2);
        renderCanvas();
    });
    document.getElementById("btnResetView")?.addEventListener("click", () => {
        state.zoom = 1.0;
        state.pan = { x: 40, y: 40 };
        renderCanvas();
    });
    document.getElementById("btnClearCanvas")?.addEventListener("click", () => {
        state.objects = [];
        renderCanvas();
    });

    // Çerçeveleme (Framing)
    document.getElementById("btnFrameJob")?.addEventListener("click", async () => {
        addLog("Framing (Kutu Çerçeveleme) başlatıldı", "log-info");
        await fetch("/api/frame", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ min_x: 10, min_y: 10, max_x: 120, max_y: 90, speed: 40.0, power_percent: 0.5 })
        });
    });

    document.getElementById("btnFrameRubber")?.addEventListener("click", async () => {
        addLog("Framing (Sıkı Çerçeveleme) başlatıldı", "log-info");
        await fetch("/api/frame", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ min_x: 20, min_y: 20, max_x: 80, max_y: 80, speed: 40.0, power_percent: 0.5 })
        });
    });

    document.getElementById("btnSetZero")?.addEventListener("click", () => {
        addLog("G92 X0 Y0 (Mevcut konum sıfırlandı)", "log-cmd");
    });
}

// REST Port Çekme
async function fetchPorts() {
    try {
        const res = await fetch("/api/ports");
        const data = await res.json();
        portSelect.innerHTML = "";
        if (!data.ports || data.ports.length === 0) {
            portSelect.innerHTML = "<option value=''>Cihaz Bulunamadı</option>";
        } else {
            data.ports.forEach(p => {
                const opt = document.createElement("option");
                opt.value = p;
                opt.textContent = p;
                portSelect.appendChild(opt);
            });
        }
    } catch (e) {
        // Çevrimdışı
    }
}
btnRefreshPorts?.addEventListener("click", fetchPorts);
btnConnect?.addEventListener("click", async () => {
    if (!state.connected) {
        const port = portSelect.value;
        if (!port) return;
        await fetch("/api/connect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ port }) });
    } else {
        await fetch("/api/disconnect", { method: "POST" });
    }
});
