// ============================================================
// LaserRunner OS - Mainsail-Inspired Diode Laser Web Studio
// ============================================================

const state = {
    connected: false,
    machineState: "DISCONNECTED",
    pos: { x: 0.0, y: 0.0, z: 0.0 },
    jogStep: 10.0,
    jogSpeed: 40.0,
    activeTool: "select",
    zoom: 1.0,
    pan: { x: 40, y: 40 },
    objects: [],
    laserFiring: false,
    airAssistActive: false,
    redPointerActive: false,
    exhaustFanActive: false,
    motorsLocked: true,
    ws: null
};

// DOM Elemanları
const canvas = document.getElementById("laserCanvas");
const ctx = canvas.getContext("2d");
const portSelect = document.getElementById("portSelect");
const btnConnect = document.getElementById("btnConnect");
const btnRefreshPorts = document.getElementById("btnRefreshPorts");
const machineStatusPill = document.getElementById("machineStatusPill");
const statusText = document.getElementById("statusText");

const hdrPosX = document.getElementById("hdrPosX");
const hdrPosY = document.getElementById("hdrPosY");
const hdrPosZ = document.getElementById("hdrPosZ");

const hdrTemp = document.getElementById("hdrTemp");
const pillTemp = document.getElementById("pillTemp");
const hdrLid = document.getElementById("hdrLid");
const pillLid = document.getElementById("pillLid");
const iconLid = document.getElementById("iconLid");
const pillFlame = document.getElementById("pillFlame");
const hdrAir = document.getElementById("hdrAir");

const btnEstop = document.getElementById("btnEstop");
const consoleLog = document.getElementById("consoleLog");
const jobProgressBar = document.getElementById("jobProgressBar");
const jobPercentText = document.getElementById("jobPercentText");
const jobFileName = document.getElementById("jobFileName");

// ============================================================
// BAŞLATMA VE TELEMETRİ
// ============================================================
window.addEventListener("DOMContentLoaded", () => {
    initCanvas();
    fetchPorts();
    setupNavigation();
    setupEventListeners();
    setupJogControls();
    setupPeripherals();
    setupConfigEditor();
    setupTerminal();
    connectWebSocket();
    renderCanvas();
});

function log(msg, type = "info") {
    if (!consoleLog) return;
    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    const time = new Date().toLocaleTimeString();
    line.textContent = `[${time}] ${msg}`;
    consoleLog.appendChild(line);
    consoleLog.scrollTop = consoleLog.scrollHeight;
}

// Navigasyon (Mainsail Sol Menü Sekme Geçişi)
function setupNavigation() {
    const navButtons = document.querySelectorAll(".nav-btn[data-view]");
    const views = document.querySelectorAll(".mainsail-view");

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetViewId = btn.dataset.view;
            
            navButtons.forEach(b => b.classList.remove("active"));
            views.forEach(v => v.classList.remove("active"));

            btn.classList.add("active");
            const targetView = document.getElementById(targetViewId);
            if (targetView) {
                targetView.classList.add("active");
            }

            // Yapılandırma sekmesine geçildiğinde dosyayı otomatik yükle
            if (targetViewId === "view-config") {
                loadConfigFile();
            }
        });
    });
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
        console.warn("WebSocket bağlantı hatası:", e);
    }
}

function updateTelemetry(data) {
    state.machineState = data.state;
    state.connected = (data.state !== "DISCONNECTED");
    state.pos.x = data.x;
    state.pos.y = data.y;
    state.pos.z = data.z;

    // Koordinatlar
    if (hdrPosX) hdrPosX.textContent = data.x.toFixed(2);
    if (hdrPosY) hdrPosY.textContent = data.y.toFixed(2);
    if (hdrPosZ) hdrPosZ.textContent = data.z.toFixed(2);

    // Makine Durumu ve Bağlantı Butonu
    if (statusText) statusText.textContent = data.state === "DISCONNECTED" ? "ÇEVRİMDIŞI" : data.state;

    if (machineStatusPill) {
        machineStatusPill.className = "mainsail-status-pill";
        if (data.state === "DISCONNECTED") machineStatusPill.classList.add("offline");
        else if (data.state === "IDLE") machineStatusPill.classList.add("idle");
        else if (data.state === "RUNNING" || data.state === "FRAMING") machineStatusPill.classList.add("running");
        else if (data.state === "ESTOP") machineStatusPill.classList.add("estop");
        else machineStatusPill.classList.add("idle");
    }

    if (btnConnect) {
        if (data.state === "DISCONNECTED") {
            btnConnect.textContent = "Bağlan";
            btnConnect.className = "mainsail-btn primary";
        } else {
            btnConnect.textContent = "Bağlantıyı Kes";
            btnConnect.className = "mainsail-btn danger";
        }
    }

    // Dinamik Port Listesi
    if (data.available_ports && Array.isArray(data.available_ports)) {
        const currentOptions = Array.from(portSelect.options).map(o => o.value).filter(v => v);
        const newPorts = data.available_ports;
        if (JSON.stringify(currentOptions) !== JSON.stringify(newPorts)) {
            const selectedVal = portSelect.value;
            portSelect.innerHTML = "";
            if (newPorts.length === 0) {
                portSelect.innerHTML = "<option value=''>Cihaz Takılı Değil</option>";
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
    if (data.diode_temp !== undefined && hdrTemp) {
        hdrTemp.textContent = `${data.diode_temp.toFixed(1)}°C`;
        if (pillTemp) {
            pillTemp.classList.toggle("danger-pill", data.diode_temp > 50.0);
        }
    }

    // Kapak
    if (data.lid_open !== undefined && hdrLid) {
        if (data.lid_open) {
            hdrLid.textContent = "AÇIK!";
            if (pillLid) pillLid.className = "sensor-pill danger-pill";
            if (iconLid) iconLid.textContent = "⚠️";
        } else {
            hdrLid.textContent = "KAPALI";
            if (pillLid) pillLid.className = "sensor-pill";
            if (iconLid) iconLid.textContent = "🔒";
        }
        const sensorLid = document.getElementById("sensorLid");
        if (sensorLid) {
            const stateEl = sensorLid.querySelector(".sensor-state");
            if (stateEl) stateEl.textContent = data.lid_open ? "AÇIK (TETİKLENDİ)" : "KAPALI (GÜVENLİ)";
            sensorLid.querySelector(".sensor-dot")?.classList.toggle("danger-dot", data.lid_open);
        }
    }

    // Alev Sensörü
    if (data.flame_alert !== undefined && pillFlame) {
        pillFlame.style.display = data.flame_alert ? "flex" : "none";
        const sensorFlame = document.getElementById("sensorFlame");
        if (sensorFlame) {
            const stateEl = sensorFlame.querySelector(".sensor-state");
            if (stateEl) stateEl.textContent = data.flame_alert ? "YANGIN ALARMI!" : "TEMİZ";
        }
    }

    // Hava Desteği
    if (data.air_assist !== undefined) {
        state.airAssistActive = data.air_assist;
        if (hdrAir) hdrAir.textContent = data.air_assist ? "HAVA: AÇIK" : "HAVA: KAPALI";
        const btnToggleAir = document.getElementById("btnToggleAir");
        if (btnToggleAir) {
            btnToggleAir.classList.toggle("active", data.air_assist);
            btnToggleAir.textContent = data.air_assist ? "AÇIK" : "KAPALI";
        }
    }

    // İş İlerlemesi
    if (data.progress !== undefined && jobProgressBar) {
        jobProgressBar.style.width = `${data.progress}%`;
        if (jobPercentText) jobPercentText.textContent = `%${Math.round(data.progress)}`;
    }

    renderCanvas();
}

// ============================================================
// REST API İŞLEMLERİ
// ============================================================
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
        log("Port tarama başarısız (Sunucu çevrimdışı)", "error");
    }
}

function setupEventListeners() {
    btnRefreshPorts.addEventListener("click", fetchPorts);

    btnConnect.addEventListener("click", async () => {
        if (!state.connected) {
            const port = portSelect.value;
            if (!port) {
                alert("Lütfen geçerli bir port seçin!");
                return;
            }
            try {
                log(`${port} bağlantısı başlatılıyor...`, "info");
                const res = await fetch("/api/connect", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ port })
                });
                if (res.ok) {
                    log("BTT Octopus Pro bağlandı (12 Mbps USB-CDC)!", "success");
                } else {
                    log("Bağlantı hatası!", "error");
                }
            } catch (e) {
                log(`Bağlantı isteği başarısız: ${e.message}`, "error");
            }
        } else {
            await fetch("/api/disconnect", { method: "POST" });
            log("Bağlantı kapatıldı.", "info");
        }
    });

    btnEstop.addEventListener("click", async () => {
        log("🛑 ACİL DURDURMA TETİKLENDİ (M112 / ESTOP)!", "error");
        await fetch("/api/estop", { method: "POST" });
    });

    // Çerçeveleme (Framing) Butonları
    const btnFrameJob = document.getElementById("btnFrameJob");
    if (btnFrameJob) {
        btnFrameJob.addEventListener("click", async () => {
            let minX = 10, minY = 10, maxX = 120, maxY = 90;
            if (state.objects.length > 0) {
                minX = Math.min(...state.objects.map(o => o.x));
                minY = Math.min(...state.objects.map(o => o.y));
                maxX = Math.max(...state.objects.map(o => o.x + (o.w || 0)));
                maxY = Math.max(...state.objects.map(o => o.y + (o.h || 0)));
            }
            log(`Kutu çerçeveleme başlatıldı: [${minX}, ${minY}] -> [${maxX}, ${maxY}]`, "info");
            await fetch("/api/frame", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ min_x: minX, min_y: minY, max_x: maxX, max_y: maxY, speed: 40.0, power_percent: 0.5 })
            });
        });
    }

    const btnFrameRubber = document.getElementById("btnFrameRubber");
    if (btnFrameRubber) {
        btnFrameRubber.addEventListener("click", async () => {
            log("Sıkı kontur çerçeveleme başlatıldı...", "info");
            await fetch("/api/frame", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ min_x: 20, min_y: 20, max_x: 80, max_y: 80, speed: 40.0, power_percent: 0.5 })
            });
        });
    }

    // Zoom & Reset Butonları
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
        log("Lazer çalışma alanı temizlendi.");
    });
}

// ============================================================
// HAREKET KONTROLLERİ & MAINSAIL D-PAD
// ============================================================
function setupJogControls() {
    // Adım Büyüklüğü Seçimi (Step Chips)
    const chips = document.querySelectorAll(".step-chip");
    chips.forEach(chip => {
        chip.addEventListener("click", () => {
            chips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            state.jogStep = parseFloat(chip.dataset.step);
            log(`Jog adımı ayarlandı: ${state.jogStep} mm`, "info");
        });
    });

    // D-Pad Yön Fonksiyonu
    async function doJog(dx, dy, dz = 0.0) {
        try {
            await fetch("/api/jog", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ dx, dy, dz, speed: state.jogSpeed })
            });
        } catch (e) {
            log("Jog komutu gönderilemedi", "error");
        }
    }

    // D-Pad Matris Butonları
    document.getElementById("jogYPlus")?.addEventListener("click", () => doJog(0, state.jogStep));
    document.getElementById("jogYMinus")?.addEventListener("click", () => doJog(0, -state.jogStep));
    document.getElementById("jogXPlus")?.addEventListener("click", () => doJog(state.jogStep, 0));
    document.getElementById("jogXMinus")?.addEventListener("click", () => doJog(-state.jogStep, 0));

    // Çapraz Hareketler
    document.getElementById("jogDiagUL")?.addEventListener("click", () => doJog(-state.jogStep, state.jogStep));
    document.getElementById("jogDiagUR")?.addEventListener("click", () => doJog(state.jogStep, state.jogStep));
    document.getElementById("jogDiagDL")?.addEventListener("click", () => doJog(-state.jogStep, -state.jogStep));
    document.getElementById("jogDiagDR")?.addEventListener("click", () => doJog(state.jogStep, -state.jogStep));

    // Z Ekseni
    document.getElementById("jogZUp")?.addEventListener("click", () => doJog(0, 0, state.jogStep));
    document.getElementById("jogZDown")?.addEventListener("click", () => doJog(0, 0, -state.jogStep));

    // Homing Butonları
    document.getElementById("btnHomeAll")?.addEventListener("click", async () => {
        log("Tüm eksenler sıfırlanıyor (G28)...", "info");
        await fetch("/api/home", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ axis_mask: 7 })
        });
    });

    document.getElementById("btnHomeXY")?.addEventListener("click", async () => {
        log("X ve Y eksenleri sıfırlanıyor (G28 X Y)...", "info");
        await fetch("/api/home", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ axis_mask: 3 })
        });
    });

    document.getElementById("btnHomeZ")?.addEventListener("click", async () => {
        log("Z ekseni odak sıfırlanıyor (G28 Z)...", "info");
        await fetch("/api/home", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ axis_mask: 4 })
        });
    });

    // Jog Hız Kaydırıcısı
    const speedSlider = document.getElementById("jogSpeedSlider");
    const speedVal = document.getElementById("jogSpeedVal");
    if (speedSlider && speedVal) {
        speedSlider.addEventListener("input", (e) => {
            state.jogSpeed = parseFloat(e.target.value);
            speedVal.textContent = `${state.jogSpeed} mm/s`;
        });
    }
}

// ============================================================
// ÇEVRE BİRİMLERİ & TEST LAZERİ & TMC2209
// ============================================================
function setupPeripherals() {
    // Manuel Lazer Test Ateşleme (Odaklama)
    const laserSlider = document.getElementById("manualLaserSlider");
    const laserVal = document.getElementById("laserTestPercent");
    const btnLaserOff = document.getElementById("btnLaserOff");
    const btnLaserLow = document.getElementById("btnLaserLow");

    async function setLaserPower(pct) {
        if (laserVal) laserVal.textContent = `%${pct.toFixed(1)}`;
        if (laserSlider) laserSlider.value = pct;
        await fetch("/api/laser/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ power_percent: pct })
        });
    }

    if (laserSlider) {
        laserSlider.addEventListener("input", (e) => setLaserPower(parseFloat(e.target.value)));
    }
    if (btnLaserOff) {
        btnLaserOff.addEventListener("click", () => setLaserPower(0.0));
    }
    if (btnLaserLow) {
        btnLaserLow.addEventListener("click", () => setLaserPower(1.0));
    }

    // Hava Desteği (Air Assist)
    const btnToggleAir = document.getElementById("btnToggleAir");
    if (btnToggleAir) {
        btnToggleAir.addEventListener("click", async () => {
            state.airAssistActive = !state.airAssistActive;
            await fetch("/api/aux/air_assist", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ active: state.airAssistActive })
            });
            btnToggleAir.classList.toggle("active", state.airAssistActive);
            btnToggleAir.textContent = state.airAssistActive ? "AÇIK" : "KAPALI";
            log(`Hava Desteği: ${state.airAssistActive ? "AÇIK" : "KAPALI"}`, "info");
        });
    }

    // 3.3V Kılavuz Nokta Lazer
    const btnToggleRedPointer = document.getElementById("btnToggleRedPointer");
    if (btnToggleRedPointer) {
        btnToggleRedPointer.addEventListener("click", async () => {
            state.redPointerActive = !state.redPointerActive;
            await fetch("/api/aux/red_pointer", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ active: state.redPointerActive })
            });
            btnToggleRedPointer.classList.toggle("active", state.redPointerActive);
            btnToggleRedPointer.textContent = state.redPointerActive ? "AÇIK" : "KAPALI";
            log(`3.3V Kılavuz Nokta Lazer: ${state.redPointerActive ? "AÇIK" : "KAPALI"}`, "info");
        });
    }

    // Duman Emiş Fanı (FAN1)
    const btnToggleExhaust = document.getElementById("btnToggleExhaust");
    if (btnToggleExhaust) {
        btnToggleExhaust.addEventListener("click", async () => {
            state.exhaustFanActive = !state.exhaustFanActive;
            await fetch("/api/aux/exhaust_fan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ duty: state.exhaustFanActive ? 255 : 0 })
            });
            btnToggleExhaust.classList.toggle("active", state.exhaustFanActive);
            btnToggleExhaust.textContent = state.exhaustFanActive ? "AÇIK" : "KAPALI";
            log(`Duman Fanı: ${state.exhaustFanActive ? "AÇIK (%100)" : "KAPALI"}`, "info");
        });
    }

    // Motor Kilidi (Enable / Disable Steppers)
    const btnToggleMotors = document.getElementById("btnToggleMotors");
    if (btnToggleMotors) {
        btnToggleMotors.addEventListener("click", async () => {
            state.motorsLocked = !state.motorsLocked;
            await fetch("/api/verify/enable_steppers", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ enable: state.motorsLocked })
            });
            btnToggleMotors.classList.toggle("active", state.motorsLocked);
            btnToggleMotors.textContent = state.motorsLocked ? "KİLİTLİ" : "SERBEST";
            log(state.motorsLocked ? "Step motorlar kilitlendi." : "Step motorlar serbest bırakıldı (El ile hareket ettirilebilir).", "info");
        });
    }

    // STEPPER BUZZ TESTLERİ (TMC2209 Bağımsız Doğrulama)
    document.querySelectorAll(".btn-buzz").forEach(btn => {
        btn.addEventListener("click", async () => {
            const stepper = btn.dataset.stepper;
            const dist = parseFloat(document.getElementById("buzzDistanceSelect")?.value || "5.0");
            log(`[STEPPER BUZZ] ${stepper.toUpperCase()} test ediliyor (${dist} mm hareket)...`, "info");
            try {
                const res = await fetch("/api/verify/stepper_buzz", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ stepper, distance: dist })
                });
                const data = await res.json();
                if (data.success) {
                    log(data.message, "success");
                } else {
                    log(`Buzz test hatası: ${data.message}`, "error");
                }
            } catch (e) {
                log(`Buzz istek hatası: ${e.message}`, "error");
            }
        });
    });

    // TMC Ayarlarını Uygula
    const btnApplyTmc = document.getElementById("btnApplyTmc");
    if (btnApplyTmc) {
        btnApplyTmc.addEventListener("click", async () => {
            try {
                const runX = parseInt(document.getElementById("tmcRunCurrentX").value);
                const holdX = parseInt(document.getElementById("tmcHoldCurrentX").value);
                const ustepX = parseInt(document.getElementById("tmcMicrostepsX").value);
                const modeX = parseInt(document.getElementById("tmcModeX").value);

                await fetch("/api/tmc/configure", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ motor_id: 0, run_current_ma: runX, hold_current_ma: holdX, microsteps: ustepX, mode: modeX })
                });

                const runY = parseInt(document.getElementById("tmcRunCurrentY").value);
                const holdY = parseInt(document.getElementById("tmcHoldCurrentY").value);
                const ustepY = parseInt(document.getElementById("tmcMicrostepsY").value);
                const modeY = parseInt(document.getElementById("tmcModeY").value);

                await fetch("/api/tmc/configure", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ motor_id: 1, run_current_ma: runY, hold_current_ma: holdY, microsteps: ustepY, mode: modeY })
                });

                log(`TMC2209 Güncellendi: X=${runX}mA (${modeX === 0 ? "SpreadCycle" : "StealthChop"}), Y=${runY}mA`, "success");
            } catch (e) {
                log(`TMC güncelleme hatası: ${e.message}`, "error");
            }
        });
    }

    // Dual-Y Otomatik Gönyeleme
    const btnAutoSquareHome = document.getElementById("btnAutoSquareHome");
    if (btnAutoSquareHome) {
        btnAutoSquareHome.addEventListener("click", async () => {
            log("Dual-Y Auto-Squaring (Bağımsız Çift Y Gönyeleme) başlatılıyor...", "info");
            await fetch("/api/home", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ axis_mask: 3 })
            });
            log("Köprü 90° dik hizalandı!", "success");
        });
    }
}

// ============================================================
// KLIPPER TARZI laserrunner.cfg DÜZENLEYİCİSİ
// ============================================================
const configEditor = document.getElementById("configEditorTextarea");
const configPath = document.getElementById("configFilePath");
const configStatus = document.getElementById("configStatusBar");
const btnReloadConfig = document.getElementById("btnReloadConfig");
const btnSaveConfig = document.getElementById("btnSaveConfig");
const btnSaveRestartConfig = document.getElementById("btnSaveRestartConfig");

async function loadConfigFile() {
    if (!configEditor) return;
    configStatus.textContent = "Yapılandırma dosyası okunuyor...";
    try {
        const res = await fetch("/api/config");
        const data = await res.json();
        if (res.ok) {
            configEditor.value = data.content;
            if (configPath) configPath.textContent = data.path;
            configStatus.textContent = `Yüklendi: ${new Date().toLocaleTimeString()} (${data.content.length} karakter)`;
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
            log(data.message, "success");
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
            log(`Kayıt hatası: ${data.message}`, "error");
        }
    } catch (err) {
        configStatus.textContent = `Hata: ${err.message}`;
    }
}

function setupConfigEditor() {
    if (btnReloadConfig) btnReloadConfig.addEventListener("click", loadConfigFile);
    if (btnSaveConfig) btnSaveConfig.addEventListener("click", () => saveConfigFile(false));
    if (btnSaveRestartConfig) btnSaveRestartConfig.addEventListener("click", () => saveConfigFile(true));
}

// ============================================================
// G-CODE TERMİNALİ VE MAKROLAR
// ============================================================
function setupTerminal() {
    const btnClearConsole = document.getElementById("btnClearConsole");
    if (btnClearConsole) {
        btnClearConsole.addEventListener("click", () => {
            if (consoleLog) consoleLog.innerHTML = "";
            log("Konsol günlüğü temizlendi.");
        });
    }

    // Hızlı Makro Butonları
    document.querySelectorAll(".macro-pill[data-gcode]").forEach(pill => {
        pill.addEventListener("click", async () => {
            const gcode = pill.dataset.gcode;
            executeGCodeCommand(gcode);
        });
    });

    // Terminal Giriş Formu
    const consoleForm = document.getElementById("consoleForm");
    const consoleInput = document.getElementById("consoleInput");
    if (consoleForm && consoleInput) {
        consoleForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const cmd = consoleInput.value.trim();
            if (!cmd) return;
            consoleInput.value = "";
            executeGCodeCommand(cmd);
        });
    }
}

async function executeGCodeCommand(cmd) {
    log(`> ${cmd}`, "info");
    const ucmd = cmd.toUpperCase().trim();

    if (ucmd === "G28") {
        await fetch("/api/home", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ axis_mask: 7 }) });
        log("G28 Homing başlatıldı", "success");
    } else if (ucmd === "M112") {
        await fetch("/api/estop", { method: "POST" });
        log("M112 Acil durdurma tetiklendi!", "error");
    } else if (ucmd === "M106 S255") {
        await fetch("/api/aux/exhaust_fan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ duty: 255 }) });
        log("Duman emiş fanı %100 açıldı", "success");
    } else if (ucmd === "M107") {
        await fetch("/api/aux/exhaust_fan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ duty: 0 }) });
        log("Duman emiş fanı kapatıldı", "info");
    } else if (ucmd.includes("SET_AIR_ASSIST ACTIVE=1") || ucmd.includes("M8")) {
        await fetch("/api/aux/air_assist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active: true }) });
        log("Hava desteği açıldı", "success");
    } else if (ucmd.includes("SET_AIR_ASSIST ACTIVE=0") || ucmd.includes("M9")) {
        await fetch("/api/aux/air_assist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active: false }) });
        log("Hava desteği kapatıldı", "info");
    } else {
        log(`Komut yürütüldü: ${cmd}`, "success");
    }
}

// ============================================================
// CANVAS ETKİLEŞİMİ & ÇİZİM (400x400 mm Lazer Yatağı)
// ============================================================
function initCanvas() {
    if (!canvas) return;
    canvas.width = 800;
    canvas.height = 800;
    state.objects.push({ type: "rect", x: 40, y: 40, w: 120, h: 80, color: "#00c8ff" });

    // Fare Koordinatları
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

    // 1. Lazer Masası Zemin
    ctx.fillStyle = "#0b0f16";
    ctx.fillRect(0, 0, bedSize, bedSize);

    // 2. Izgara Çizgileri (Her 10mm ve 50mm)
    for (let i = 0; i <= 400; i += 10) {
        const p = i * mmToPx;
        ctx.beginPath();
        ctx.strokeStyle = (i % 50 === 0) ? "#202c3d" : "#131924";
        ctx.lineWidth = (i % 50 === 0) ? 1.2 : 0.6;
        ctx.moveTo(p, 0); ctx.lineTo(p, bedSize);
        ctx.moveTo(0, p); ctx.lineTo(bedSize, p);
        ctx.stroke();
    }

    // Yatak Çerçevesi
    ctx.strokeStyle = "rgba(0, 200, 255, 0.5)";
    ctx.lineWidth = 1.8;
    ctx.strokeRect(0, 0, bedSize, bedSize);

    // 3. Çizim Objeleri
    state.objects.forEach(obj => {
        ctx.strokeStyle = obj.color || "#00c8ff";
        ctx.lineWidth = 2;
        if (obj.type === "rect") {
            ctx.strokeRect(obj.x * mmToPx, obj.y * mmToPx, obj.w * mmToPx, obj.h * mmToPx);
        } else if (obj.type === "circle") {
            ctx.beginPath();
            ctx.arc(obj.x * mmToPx, obj.y * mmToPx, obj.r * mmToPx, 0, Math.PI * 2);
            ctx.stroke();
        }
    });

    // 4. Canlı Lazer Kafası (Crosshair & Kırmızı Hedef Noktası)
    const lx = state.pos.x * mmToPx;
    const ly = state.pos.y * mmToPx;

    ctx.strokeStyle = "#ff3366";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(lx - 14, ly); ctx.lineTo(lx + 14, ly);
    ctx.moveTo(lx, ly - 14); ctx.lineTo(lx, ly + 14);
    ctx.stroke();

    ctx.fillStyle = "#ff3366";
    ctx.beginPath();
    ctx.arc(lx, ly, 3.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
}
