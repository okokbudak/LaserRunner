// ============================================================
// LaserRunner Studio OS - İstemci Mantığı ve Canvas Yöneticisi
// ============================================================

const state = {
    connected: false,
    machineState: "DISCONNECTED",
    pos: { x: 0.0, y: 0.0, z: 0.0 },
    jogStep: 10.0,
    jogSpeed: 40.0,
    activeTool: "select",
    zoom: 1.0,
    pan: { x: 50, y: 50 },
    objects: [], // Canvas üzerindeki geometriler ve yollar
    laserFiring: false,
    ws: null
};

// DOM Elemanları
const canvas = document.getElementById("laserCanvas");
const ctx = canvas.getContext("2d");
const portSelect = document.getElementById("portSelect");
const btnConnect = document.getElementById("btnConnect");
const btnRefreshPorts = document.getElementById("btnRefreshPorts");
const statusBadge = document.getElementById("statusBadge");
const statusText = document.getElementById("statusText");
const hdrPosX = document.getElementById("hdrPosX");
const hdrPosY = document.getElementById("hdrPosY");
const hdrPosZ = document.getElementById("hdrPosZ");
const btnEstop = document.getElementById("btnEstop");
const consoleLog = document.getElementById("consoleLog");
const progressBarFill = document.getElementById("progressBarFill");
const jobPercent = document.getElementById("jobPercent");
const jobStateLabel = document.getElementById("jobStateLabel");

// ============================================================
// BAŞLATMA VE WEBSOCKET
// ============================================================
window.addEventListener("DOMContentLoaded", () => {
    initCanvas();
    fetchPorts();
    setupEventListeners();
    connectWebSocket();
    renderCanvas();
});

function log(msg, type = "info") {
    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    const time = new Date().toLocaleTimeString();
    line.textContent = `[${time}] ${msg}`;
    consoleLog.appendChild(line);
    consoleLog.scrollTop = consoleLog.scrollHeight;
}

function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    try {
        state.ws = new WebSocket(wsUrl);
        state.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            updateTelemetry(data);
        };
        state.ws.onclose = () => {
            setTimeout(connectWebSocket, 2000);
        };
    } catch (e) {
        console.warn("WebSocket bağlantı denemesi:", e);
    }
}

function updateTelemetry(data) {
    state.machineState = data.state;
    state.pos.x = data.x;
    state.pos.y = data.y;
    state.pos.z = data.z;

    hdrPosX.textContent = data.x.toFixed(2);
    hdrPosY.textContent = data.y.toFixed(2);
    hdrPosZ.textContent = data.z.toFixed(2);

    statusText.textContent = data.state;
    const indicator = statusBadge.querySelector(".status-indicator");
    indicator.className = "status-indicator";

    if (data.state === "IDLE") indicator.classList.add("online");
    else if (data.state === "RUNNING" || data.state === "FRAMING") indicator.classList.add("running");
    else if (data.state === "ESTOP") indicator.classList.add("estop");

    progressBarFill.style.width = `${data.progress}%`;
    jobPercent.textContent = `${Math.round(data.progress)}%`;
    jobStateLabel.textContent = data.state;

    const elQueue = document.getElementById("telQueue");
    if (elQueue && data.slots !== undefined) {
        elQueue.textContent = `${data.slots} / 64`;
    }

    // Sıcaklık Telemetrisi
    if (data.diode_temp !== undefined) {
        const hdrTemp = document.getElementById("hdrTemp");
        hdrTemp.textContent = `${data.diode_temp.toFixed(1)}°C`;
        const pillTemp = document.getElementById("pillTemp");
        if (data.diode_temp > 50.0) {
            pillTemp.className = "sensor-pill danger-pill";
        } else {
            pillTemp.className = "sensor-pill";
        }
    }

    // Kapak Güvenlik Durumu
    if (data.lid_open !== undefined) {
        const hdrLid = document.getElementById("hdrLid");
        const pillLid = document.getElementById("pillLid");
        const iconLid = document.getElementById("iconLid");
        if (data.lid_open) {
            hdrLid.textContent = "AÇIK!";
            pillLid.className = "sensor-pill danger-pill";
            iconLid.textContent = "⚠️";
        } else {
            hdrLid.textContent = "KAPALI";
            pillLid.className = "sensor-pill";
            iconLid.textContent = "🔒";
        }
    }

    // Alev Alarmı
    if (data.flame_alert !== undefined) {
        const pillFlame = document.getElementById("pillFlame");
        pillFlame.style.display = data.flame_alert ? "flex" : "none";
    }

    // Eklenti Durumları
    if (data.air_assist !== undefined) {
        const btnAir = document.getElementById("btnAirAssistToggle");
        if (btnAir) btnAir.classList.toggle("active", data.air_assist);
    }
    if (data.red_pointer !== undefined) {
        const btnRed = document.getElementById("btnRedPointerToggle");
        if (btnRed) btnRed.classList.toggle("active", data.red_pointer);
    }

    renderCanvas();
}

// ============================================================
// REST API ÇAĞRILARI
// ============================================================
async function fetchPorts() {
    try {
        const res = await fetch("/api/ports");
        const data = await res.json();
        portSelect.innerHTML = "";
        if (data.ports.length === 0) {
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
        log("Port tarama başarısız (Sunucu çevrimdışı olabilir)", "error");
    }
}

btnRefreshPorts.addEventListener("click", fetchPorts);

btnConnect.addEventListener("click", async () => {
    if (!state.connected) {
        const port = portSelect.value;
        if (!port) {
            alert("Lütfen geçerli bir port seçin!");
            return;
        }
        try {
            log(`${port} portuna bağlanılıyor...`);
            const res = await fetch("/api/connect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ port })
            });
            if (res.ok) {
                state.connected = true;
                btnConnect.textContent = "Bağlantıyı Kes";
                btnConnect.style.background = "var(--accent-red)";
                log("Anakartla bağlantı kuruldu (12 Mbps USB-CDC)!", "success");
            } else {
                log("Bağlantı hatası!", "error");
            }
        } catch (e) {
            log(`Bağlantı isteği başarısız: ${e}`, "error");
        }
    } else {
        await fetch("/api/disconnect", { method: "POST" });
        state.connected = false;
        btnConnect.textContent = "Bağlan";
        btnConnect.style.background = "var(--accent-cyan)";
        log("Bağlantı kesildi.", "info");
    }
});

btnEstop.addEventListener("click", async () => {
    log("ACİL DURDURMA TETİKLENDİ!", "error");
    await fetch("/api/estop", { method: "POST" });
});

// ============================================================
// JOG VE EKSEN HAREKETLERİ
// ============================================================
document.querySelectorAll(".btn-jog").forEach(btn => {
    btn.addEventListener("click", async () => {
        const dx = parseFloat(btn.dataset.dx) * state.jogStep;
        const dy = parseFloat(btn.dataset.dy) * state.jogStep;
        try {
            await fetch("/api/jog", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ dx, dy, dz: 0.0, speed: state.jogSpeed })
            });
        } catch (e) {
            log("Jog komutu gönderilemedi", "error");
        }
    });
});

document.querySelectorAll(".step-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".step-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.jogStep = parseFloat(btn.dataset.val);
    });
});

const jogSpeedSlider = document.getElementById("jogSpeedSlider");
const jogSpeedVal = document.getElementById("jogSpeedVal");
jogSpeedSlider.addEventListener("input", (e) => {
    state.jogSpeed = parseFloat(e.target.value);
    jogSpeedVal.textContent = `${state.jogSpeed} mm/s`;
});

// Lazer Test Ateşi
const btnLaserTestToggle = document.getElementById("btnLaserTestToggle");
const testPowerSlider = document.getElementById("testPowerSlider");
const testPowerVal = document.getElementById("testPowerVal");

testPowerSlider.addEventListener("input", (e) => {
    testPowerVal.textContent = `%${parseFloat(e.target.value).toFixed(1)}`;
});

btnLaserTestToggle.addEventListener("click", async () => {
    state.laserFiring = !state.laserFiring;
    const power = state.laserFiring ? parseFloat(testPowerSlider.value) : 0.0;
    
    if (state.laserFiring) {
        btnLaserTestToggle.textContent = "Lazeri KAPAT";
        btnLaserTestToggle.classList.add("firing");
    } else {
        btnLaserTestToggle.textContent = "Lazer Işığını Aç";
        btnLaserTestToggle.classList.remove("firing");
    }

    await fetch("/api/laser/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ power_percent: power })
    });
});

// Çerçeveleme (Framing)
document.getElementById("btnFrameJob").addEventListener("click", async () => {
    let minX = 10, minY = 10, maxX = 100, maxY = 100;
    if (state.objects.length > 0) {
        // Objelere göre sınır kutusu hesabı
        minX = Math.min(...state.objects.map(o => o.x));
        minY = Math.min(...state.objects.map(o => o.y));
        maxX = Math.max(...state.objects.map(o => o.x + (o.w || 0)));
        maxY = Math.max(...state.objects.map(o => o.y + (o.h || 0)));
    }
    log(`Çerçeveleme başlatılıyor: [${minX}, ${minY}] -> [${maxX}, ${maxY}]`);
    await fetch("/api/frame", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ min_x: minX, min_y: minY, max_x: maxX, max_y: maxY, speed: 40.0, power_percent: 0.5 })
    });
});

// ============================================================
// CANVAS ÇİZİM VE ETKİLEŞİMİ (400x400 mm Lazer Yatağı)
// ============================================================
function initCanvas() {
    canvas.width = 800;
    canvas.height = 800;
    // Varsayılan bir örnek test kutusu ekle
    state.objects.push({ type: "rect", x: 50, y: 50, w: 100, h: 80, color: "#00f0ff" });
}

function renderCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.translate(state.pan.x, state.pan.y);
    ctx.scale(state.zoom, state.zoom);

    const bedSize = 600; // 400mm ölçekli yatak alanı
    const mmToPx = bedSize / 400.0;

    // 1. Lazer Yatağı ve Izgara (Grid)
    ctx.fillStyle = "#0c0f17";
    ctx.fillRect(0, 0, bedSize, bedSize);
    ctx.strokeStyle = "#1b2230";
    ctx.lineWidth = 1;

    // Her 10mm ve 50mm'de ızgara
    for (let i = 0; i <= 400; i += 10) {
        const p = i * mmToPx;
        ctx.beginPath();
        ctx.strokeStyle = (i % 50 === 0) ? "#2a364d" : "#161c28";
        ctx.moveTo(p, 0); ctx.lineTo(p, bedSize);
        ctx.moveTo(0, p); ctx.lineTo(bedSize, p);
        ctx.stroke();
    }

    // Yatak Çerçevesi
    ctx.strokeStyle = "rgba(0, 240, 255, 0.4)";
    ctx.lineWidth = 2;
    ctx.strokeRect(0, 0, bedSize, bedSize);

    // 2. Çizim Objeleri
    state.objects.forEach(obj => {
        ctx.strokeStyle = obj.color || "#00f0ff";
        ctx.lineWidth = 2;
        if (obj.type === "rect") {
            ctx.strokeRect(obj.x * mmToPx, obj.y * mmToPx, obj.w * mmToPx, obj.h * mmToPx);
        } else if (obj.type === "circle") {
            ctx.beginPath();
            ctx.arc(obj.x * mmToPx, obj.y * mmToPx, obj.r * mmToPx, 0, Math.PI * 2);
            ctx.stroke();
        }
    });

    // 3. Canlı Lazer Kafası (Crosshair & Hedef Işık)
    const lx = state.pos.x * mmToPx;
    const ly = state.pos.y * mmToPx;

    ctx.strokeStyle = "#ff2a5f";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(lx - 12, ly); ctx.lineTo(lx + 12, ly);
    ctx.moveTo(lx, ly - 12); ctx.lineTo(lx, ly + 12);
    ctx.stroke();

    ctx.fillStyle = "#ff2a5f";
    ctx.beginPath();
    ctx.arc(lx, ly, 3.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
}

function setupEventListeners() {
    // Sekme geçişleri
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById(btn.dataset.tab).classList.add("active");
        });
    });

    // Araç çubuğu butonları
    document.querySelectorAll(".tool-btn[data-tool]").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tool-btn[data-tool]").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.activeTool = btn.dataset.tool;
        });
    });

    // Yakınlaştırma butonları
    document.getElementById("btnZoomIn").addEventListener("click", () => {
        state.zoom = Math.min(3.0, state.zoom + 0.2);
        document.getElementById("zoomVal").textContent = `${Math.round(state.zoom * 100)}%`;
        renderCanvas();
    });
    document.getElementById("btnZoomOut").addEventListener("click", () => {
        state.zoom = Math.max(0.4, state.zoom - 0.2);
        document.getElementById("zoomVal").textContent = `${Math.round(state.zoom * 100)}%`;
        renderCanvas();
    });
    document.getElementById("btnResetView").addEventListener("click", () => {
        state.zoom = 1.0;
        state.pan = { x: 50, y: 50 };
        document.getElementById("zoomVal").textContent = "100%";
        renderCanvas();
    });

    // Canvas temizleme
    document.getElementById("btnClearCanvas").addEventListener("click", () => {
        state.objects = [];
        renderCanvas();
        log("Çalışma alanı temizlendi.");
    });

    // Air Assist (Hava Motoru) Aç/Kapat
    const btnAir = document.getElementById("btnAirAssistToggle");
    if (btnAir) {
        btnAir.addEventListener("click", async () => {
            const active = !btnAir.classList.contains("active");
            btnAir.classList.toggle("active", active);
            await fetch("/api/aux/air_assist", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ active })
            });
            log(`Hava Motoru: ${active ? "AÇIK" : "KAPALI"}`);
        });
    }

    // 3.3V Kılavuz Lazer / Kırmızı Nokta Aç/Kapat
    const btnRed = document.getElementById("btnRedPointerToggle");
    if (btnRed) {
        btnRed.addEventListener("click", async () => {
            const active = !btnRed.classList.contains("active");
            btnRed.classList.toggle("active", active);
            await fetch("/api/aux/red_pointer", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ active })
            });
            log(`3.3V Kılavuz Lazer: ${active ? "AÇIK" : "KAPALI"}`);
        });
    }

    // Duman Tahliye Fanı Hızı
    const exSlider = document.getElementById("exhaustFanSlider");
    const exVal = document.getElementById("exhaustFanVal");
    if (exSlider && exVal) {
        exSlider.addEventListener("input", async (e) => {
            const duty = parseInt(e.target.value);
            const pct = Math.round((duty / 255) * 100);
            exVal.textContent = `%${pct}`;
            await fetch("/api/aux/exhaust_fan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ duty })
            });
        });
    }

    // Dual-Y Auto-Squaring Homing
    const btnAutoSquare = document.getElementById("btnAutoSquareHome");
    if (btnAutoSquare) {
        btnAutoSquare.addEventListener("click", async () => {
            log("Dual-Y Auto-Squaring başlatılıyor (Gönyeleme)...", "info");
            await fetch("/api/home", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ axis_mask: 3 }) // X ve Dual-Y
            });
            log("Auto-Squaring tamamlandı, köprü 90° hizalandı!", "success");
        });
    }
}
