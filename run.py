import asyncio
import logging
import random
import math
import hashlib
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn


from tradesys.data.bars import Bar
from tradesys.strategy.grid import GridStrategy, GridConfig
from tradesys.strategy.regime import MacroRegimeEngine
from tradesys.oms.store import OrderStore
from tradesys.ta.atr import atr_series
from tradesys.ta.indicators import Indicators
from tradesys.adapters.base import Fill


def patched_ema(values, period):
    if len(values) < period or period <= 0:
        return [float("nan")] * len(values)
    multiplier = 2.0 / (period + 1.0)
    ema_values = [float("nan")] * (period - 1)
    sma = sum(values[: period]) / period 
    ema_values.append(sma)
    for price in values[period:]:
        new_ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(new_ema)
    return ema_values 

Indicators.ema = staticmethod(patched_ema)


class ConnectionManager:
    def __init__(self):
        self.active_connections = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try: await connection.send_json(message)
            except: pass

manager = ConnectionManager()

class UILogHandler(logging.Handler):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop
    def emit(self, record):
        msg = self.format(record)
        level = "INFO"
        if record.levelno >= logging.CRITICAL: level = "CRIT"
        elif record.levelno >= logging.WARNING: level = "WARN"
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": "log", "level": level, "msg": msg}), self.loop
        )


class LiveDemoOrchestrator:
    def __init__(self, db_path="live_demo.db"):
        self.db_path = db_path
        self.running = True
        self.speed = 0.5
        self.vix_override = None
        self._init_components()

    def _init_components(self):
        self.store = OrderStore(self.db_path)
        self.strategy = GridStrategy("live-demo", GridConfig())
        self.regime_engine = MacroRegimeEngine(vix_crisis_threshold=24.0)
        self.bars_history = []
        self.tick_count = 0
        self.current_vix = 14.0
        
        lots, avg_entry, last_entry = self.store.reconciled_position()
        if lots != 0:
            self.strategy.seed_position(lots, avg_entry, last_entry)
            logging.getLogger("tradesys").info(f"RECOVERED STATE: {lots} lots @ {avg_entry:.2f}")
        
        self.strategy.seed_sequence(self.store.count_orders())

    def generate_live_bar(self) -> Bar:
        prev_close = self.bars_history[-1].close if self.bars_history else 22000.0
        if self.vix_override:
            self.current_vix = self.vix_override
        else:
            self.current_vix += (14.0 - self.current_vix) * 0.1 + random.uniform(-1, 1)

        volatility = self.current_vix / 1000.0
        change = random.gauss(0, 1) * volatility * prev_close
        open_px = prev_close
        close_px = max(0.5, prev_close + change)
        wick = abs(random.gauss(0, 1)) * volatility * prev_close * 0.3
        
        bar = Bar(
            ts=self.tick_count, open=open_px, high=max(open_px, close_px) + wick,
            low=max(0.1, min(open_px, close_px) - wick), close=close_px
        )
        self.tick_count += 1
        return bar

    async def run_live_loop(self):
        logger = logging.getLogger("tradesys")
        while True:
            if not self.running:
                await asyncio.sleep(0.1)
                continue

            bar = self.generate_live_bar()
            self.bars_history.append(bar)
            if len(self.bars_history) > 100: self.bars_history.pop(0)

            current_atr = None
            fast_ema = bar.close
            if len(self.bars_history) >= self.strategy.config.atr_period:
                atrs = atr_series(self.bars_history, self.strategy.config.atr_period)
                current_atr = atrs[-1]
                
            if len(self.bars_history) >= 9:
                emas = Indicators.ema([b.close for b in self.bars_history], 9)
                if emas and not math.isnan(emas[-1]):
                    fast_ema = emas[-1]

            policy = self.regime_engine.evaluate_regime(self.current_vix, bar.close, fast_ema)
            self.strategy.config.grid_spacing_multiplier = policy.grid_spacing_multiplier
            self.strategy.config.max_lots = policy.max_pyramiding_levels
            
            if policy.allow_new_entries or self.strategy.lots != 0:
                orders = self.strategy.decide(self.bars_history, current_atr)
                for order in orders:
                    coid = hashlib.sha256(f"{self.strategy.strategy_id}:{order.seq}".encode()).hexdigest()[:16]
                    
                    if not self.store.record_intent(coid, order, bar_index=bar.ts):
                        continue 
                    
                    fill = Fill(coid, bar.close, order.qty, 0.0, bar.ts)
                    self.strategy.on_fill(order, fill.price)
                    self.store.record_fill(coid, fill)
                    
                    # Enhanced Log Math Context
                    calc_ctx = f"[Px: {bar.close:.2f} | ATR: {current_atr:.2f}]"
                    if self.strategy.avg_entry:
                        calc_ctx = f"[Px: {bar.close:.2f} | Avg: {self.strategy.avg_entry:.2f} | ATR: {current_atr:.2f}]"
                        
                    logger.info(f"EXECUTION: {order.side.value} {order.qty} @ ₹{fill.price:.2f} | Reason: {order.reason.value} | {calc_ctx} | ID: {coid[:6]}")
                    await manager.broadcast({"type": "fill", "side": order.side.value, "qty": order.qty, "price": fill.price, "reason": order.reason.value, "coid": coid[:6]})

            await manager.broadcast({
                "type": "tick", "bar": {"close": bar.close},
                "vix": round(self.current_vix, 2), "regime": policy.regime.value,
                "atr": round(current_atr, 2) if current_atr else 0.0,
                "ema": round(fast_ema, 2)
            })
            await manager.broadcast({
                "type": "state", "lots": self.strategy.lots,
                "avg": round(self.strategy.avg_entry, 2) if self.strategy.avg_entry else None,
                "halted": self.strategy.halted
            })

            await asyncio.sleep(self.speed)


app = FastAPI()
orchestrator = LiveDemoOrchestrator()

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    logger = logging.getLogger("tradesys")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = UILogHandler(loop)
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', "%H:%M:%S"))
    logger.addHandler(handler)
    
    logger.info("SYSTEM START: Event Orchestrator Initialized.")
    asyncio.create_task(orchestrator.run_live_loop())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            cmd = data.get("cmd")
            logger = logging.getLogger("tradesys")
            
            if cmd == "pause":
                orchestrator.running = not orchestrator.running
            elif cmd == "speed":
                orchestrator.speed = float(data.get("val")) / 1000.0
            elif cmd == "kill":
                orchestrator.strategy.halted = True
                logger.critical("MANUAL KILL SWITCH ENGAGED. System Halted.")
            elif cmd == "vix_shock":
                orchestrator.vix_override = 35.0
                logger.warning("MACRO EVENT: VIX spiking artificially to 35.0. Pyramiding disabled.")
            elif cmd == "vix_normal":
                orchestrator.vix_override = None
                logger.info("MACRO EVENT: VIX normalizing. Resuming standard grid.")
            elif cmd == "crash":
                orchestrator.running = False
                logger.critical("SIMULATING FATAL PROCESS CRASH... Dropping event loop.")
                await asyncio.sleep(2)
                orchestrator._init_components() 
                logger.info("SYSTEM REBOOTED: Reconciled memory state from OMS SQLite database.")
                orchestrator.running = True
            elif cmd == "reset":
                try:
                    orchestrator.store.conn.execute("DROP TABLE IF EXISTS orders")
                    orchestrator.store.conn.execute("DROP TABLE IF EXISTS fills")
                    orchestrator.store.conn.commit()
                except Exception:
                    pass
                orchestrator._init_components()
                orchestrator.vix_override = None
                logger.info("OMS database tables dropped and reset.")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/")
async def get():
    html_content = """
    <!doctype html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <title>Engine Terminal</title>
    <style>
    :root{
      --bg:#0B0E14; --panel:#131820; --ink:#E7E9EC; --muted:#8B95A5; --border:#232B38;
      --buy:#4FB286; --sell:#D1685A; --warn:#E0A339; --grid:#1B2230; --vix:#82AAFF;
      box-sizing:border-box; font-family: ui-monospace, Consolas, monospace; font-size: 13px;
    }
    body { background: var(--bg); color: var(--ink); margin: 0; padding: 20px; }
    h1 { margin: 0; font-size: 20px; font-family: system-ui; }
    .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 15px; margin-top: 15px; }
    .panel { background: var(--panel); border: 1px solid var(--border); padding: 15px; border-radius: 6px; }
    .header-bar { display: flex; justify-content: space-between; align-items: center; background: var(--panel); padding: 15px; border-radius: 6px; border: 1px solid var(--border);}
    
    .metrics-row { display: flex; gap: 10px; margin-bottom: 15px; }
    .metric-box { background: var(--bg); border: 1px solid var(--border); padding: 8px; border-radius: 4px; flex: 1; text-align: center; font-size: 11px; }
    .metric-val { font-size: 16px; font-weight: bold; margin-top: 5px; }
    .buy { color: var(--buy); } .sell { color: var(--sell); } .vix { color: var(--vix); }
    
    button { background: var(--bg); color: var(--ink); border: 1px solid var(--border); padding: 8px 12px; cursor: pointer; border-radius: 4px; font-weight: bold;}
    button:hover { border-color: var(--ink); }
    button.danger { border-color: var(--sell); color: var(--sell); }
    button.warn { border-color: var(--warn); color: var(--warn); }
    select { background: var(--bg); color: var(--ink); border: 1px solid var(--border); padding: 7px; border-radius: 4px; }
    
    .log-box { height: 250px; overflow-y: auto; background: var(--grid); border-radius: 4px; padding: 10px; margin-top: 10px; font-size: 12px; }
    .log-box div { margin-bottom: 4px; }
    .CRIT { color: var(--sell); font-weight: bold; } .WARN { color: var(--warn); } 
    
    table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11.5px; }
    th, td { text-align: left; padding: 6px; border-bottom: 1px solid var(--grid); }
    canvas { width: 100%; height: 250px; background: var(--grid); border-radius: 4px; }
    </style>
    </head>
    <body>
        <div class="header-bar">
            <div>
                <h1>tradesys </h1>
                
            </div>
            <div>
                <button id="btnPause">Pause Engine</button>
                <select id="speed"><option value="500">Slow</option><option value="200" selected>Normal</option><option value="50">Fast</option></select>
                <button id="btnVix" class="vix">Simulate VIX Spike</button>
                <button id="btnCrash" class="warn">Simulate Hard Crash</button>
                <button id="btnKill" class="danger">Manual Kill Switch</button>
                <button id="btnReset">Reset Data</button>
            </div>
        </div>

        <div class="grid">
            <div class="panel">
                <div class="metrics-row">
                    <div class="metric-box">Live Price<div id="px" class="metric-val">—</div></div>
                    <div class="metric-box">ATR (14)<div id="atr-val" class="metric-val">—</div></div>
                    <div class="metric-box">EMA (9)<div id="ema-val" class="metric-val">—</div></div>
                    <div class="metric-box">VIX<div id="vix-val" class="metric-val">—</div></div>
                    <div class="metric-box">Regime<div id="regime" class="metric-val vix">—</div></div>
                </div>
                <canvas id="chart"></canvas>
            </div>
            <div class="panel">
                <div class="metrics-row">
                    <div class="metric-box">Net Lots<div id="lots" class="metric-val">0</div></div>
                    <div class="metric-box">Avg Entry<div id="avg" class="metric-val">—</div></div>
                </div>
                <div style="font-weight: bold; border-bottom: 1px solid var(--border); padding-bottom: 5px;">OMS Execution Blotter</div>
                <table>
                    <thead><tr><th>ID</th><th>Side</th><th>Reason</th><th>Price</th></tr></thead>
                    <tbody id="blotter"></tbody>
                </table>
            </div>
        </div>
        
        <div class="panel" style="margin-top: 15px;">
            <div style="font-weight: bold;">Observability Layer (tradesys.engine)</div>
            <div id="logs" class="log-box"></div>
        </div>

    <script>
        const ws = new WebSocket("ws://localhost:8000/ws");
        let chartData = [];

        document.getElementById('btnPause').onclick = (e) => { ws.send(JSON.stringify({cmd: 'pause'})); e.target.innerText = e.target.innerText === "Pause Engine" ? "Resume Engine" : "Pause Engine";};
        document.getElementById('speed').onchange = (e) => ws.send(JSON.stringify({cmd: 'speed', val: e.target.value}));
        document.getElementById('btnKill').onclick = () => ws.send(JSON.stringify({cmd: 'kill'}));
        document.getElementById('btnCrash').onclick = () => ws.send(JSON.stringify({cmd: 'crash'}));
        
        let isVixSpiked = false;
        document.getElementById('btnVix').onclick = (e) => {
            isVixSpiked = !isVixSpiked;
            ws.send(JSON.stringify({cmd: isVixSpiked ? 'vix_shock' : 'vix_normal'}));
            e.target.innerText = isVixSpiked ? "Normalize VIX" : "Simulate VIX Spike";
        };

        document.getElementById('btnReset').onclick = () => { 
            chartData = []; 
            document.getElementById('blotter').innerHTML = ''; 
            document.getElementById('logs').innerHTML = ''; 
            document.getElementById('chart').getContext('2d').clearRect(0,0,1000,1000);
            ws.send(JSON.stringify({cmd: 'reset'})); 
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'tick') {
                chartData.push(data.bar.close);
                if(chartData.length > 100) chartData.shift();
                
                document.getElementById('px').innerText = data.bar.close.toFixed(2);
                document.getElementById('vix-val').innerText = data.vix.toFixed(2);
                document.getElementById('atr-val').innerText = data.atr.toFixed(2);
                document.getElementById('ema-val').innerText = data.ema.toFixed(2);
                
                const regEl = document.getElementById('regime');
                regEl.innerText = data.regime.replace("TRENDING_", "").replace("_PANIC", "");
                if(data.regime.includes("PANIC")) regEl.className = "metric-val sell";
                else if(data.regime.includes("BULL") || data.regime.includes("BEAR")) regEl.className = "metric-val buy";
                else regEl.className = "metric-val vix";
                
                drawChart();
            } else if (data.type === 'state') {
                const l = document.getElementById('lots');
                l.innerText = data.lots;
                l.className = data.lots > 0 ? "metric-val buy" : (data.lots < 0 ? "metric-val sell" : "metric-val");
                document.getElementById('avg').innerText = data.avg ? data.avg.toFixed(2) : "—";
            } else if (data.type === 'fill') {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td style="color: var(--muted);">${data.coid}</td><td class="${data.side === 'BUY' ? 'buy' : 'sell'}">${data.side}</td><td>${data.reason}</td><td>${data.price.toFixed(2)}</td>`;
                const tbody = document.getElementById('blotter');
                tbody.insertBefore(tr, tbody.firstChild);
                if (tbody.children.length > 6) tbody.removeChild(tbody.lastChild);
            } else if (data.type === 'log') {
                const logs = document.getElementById('logs');
                logs.innerHTML += `<div class="${data.level}">[${data.level}] ${data.msg}</div>`;
                logs.scrollTop = logs.scrollHeight;
            }
        };

        function drawChart() {
            const c = document.getElementById('chart'), ctx = c.getContext('2d');
            c.width = c.clientWidth; c.height = 250; ctx.clearRect(0,0,c.width,c.height);
            if(chartData.length < 2) return;
            const min = Math.min(...chartData), max = Math.max(...chartData);
            const w = c.width / (chartData.length - 1);
            
            ctx.strokeStyle = '#E7E9EC'; ctx.lineWidth = 2; ctx.beginPath();
            chartData.forEach((px, i) => {
                const y = 250 - ((px - min) / (max - min || 1) * 230 + 10);
                i === 0 ? ctx.moveTo(0, y) : ctx.lineTo(i * w, y);
            });
            ctx.stroke();
        }
        window.addEventListener('resize', drawChart);
    </script>
    </body>
    </html>
    """
    return HTMLResponse(html_content)

if __name__ == "__main__":
    uvicorn.run("run:app", host="127.0.0.1", port=8000, reload=True)