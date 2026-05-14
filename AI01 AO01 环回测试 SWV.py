import os, sys, time
import numpy as np
from ctypes import *
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import matplotlib.pyplot as plt

# ====================== DLL ======================
DAQdll = WinDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), "Usb_Daq_V6505.dll"))
dev = 0

ADC_RATE, READ_BLOCK = 1000, 200

# ====================== SWV参数 ======================
# 电位扫描参数
E_init = -0.2       # 初始电位 (V)
E_final = 0.2       # 终点电位 (V)
E_incr = 0.004      # 电位增量/步长 (V)

# 脉冲与时间参数
amplitude = 0.025   # 脉冲振幅 (V)
frequency = 10      # 频率 (Hz)
quiet_time = 2.0    # 静置时间 (s)
polarity = 1

POINTS_PER_PERIOD = 100
DA_RATE = int(POINTS_PER_PERIOD * frequency)

#继电器控制策略
relay_channel = 1      # 0/1/2
relay_settle_time = 0.05

#继电器映射
def get_relay_mask(ch):
    if ch == 0: return 15
    if ch == 1: return 240
    if ch == 2: return 3840
    return 0

# ====================== 设备初始化 ======================
err = DAQdll.OpenUSB()
if err != 0: raise RuntimeError("USB open failed")

DAQdll.Write_Port_Out(dev, get_relay_mask(relay_channel))
time.sleep(relay_settle_time)

def v2d(v): return int((v + 10) / 20 * 65535 + 0.5)

# ====================== SWV生成 ======================
def gen_swv():
    Nq = int(quiet_time * DA_RATE)
    E_q = np.full(Nq, E_init)

    steps, e = [], E_init
    while True:
        steps.append(e)
        if e >= E_final: break
        e += E_incr
    steps = np.array(steps)

    Nh = POINTS_PER_PERIOD // 2
    wave = []

    for e in steps:
        if polarity:
            c = np.concatenate([np.full(Nh, e - amplitude), np.full(Nh, e + amplitude)])
        else:
            c = np.concatenate([np.full(Nh, e + amplitude), np.full(Nh, e - amplitude)])
        wave.append(c)

    return np.concatenate([E_q] + wave)

E = gen_swv()
dac = np.array([v2d(x) for x in E], dtype=np.uint16)

total_time = len(E) / DA_RATE
total_samples = int(total_time * ADC_RATE)

print("DA_RATE:", DA_RATE, "DAC:", len(dac), "ADC:", total_samples)

# ====================== DA ======================
DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 1)
DAQdll.Sent_DaData(dev, len(dac), (c_uint * len(dac))(*dac))

# ====================== ADC ======================
buf = (c_float * total_samples)()
collected = 0
DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)
t0 = time.time()

# ====================== UI ======================
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

app = QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(title="SWV")
win.resize(1000, 600)
plot = win.addPlot()
plot.setLabel('left', 'Voltage (mV)')
plot.setLabel('bottom', 't(s)')
# plot.setYRange(E_init - amplitude - 0.1, E_final + amplitude + 0.1)
plot.setYRange(-5, 5.5)
curve = plot.plot(pen='r')
win.show()

# ====================== 采集 ======================
def task():
    global collected
    n = DAQdll.Get_AdBuf_Size(dev)

    if n >= READ_BLOCK and collected < total_samples:
        m = min(READ_BLOCK, total_samples - collected)
        tmp = (c_float * m)()
        r = DAQdll.Read_AdBuf(dev, tmp, m)
        if r > 0:
            buf[collected:collected + r] = tmp[:r]
            collected += r
            t = np.arange(collected) / ADC_RATE
            curve.setData(t, np.array(buf[:collected]))

    if collected >= total_samples:
        timer.stop()
        DAQdll.AD_Continu_Stop(dev)
        DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 0)
        DAQdll.Write_Port_Out(dev, get_relay_mask(relay_channel))
        time.sleep(0.1)
        DAQdll.CloseUSB()

        t = np.arange(total_samples) / ADC_RATE
        np.savetxt("swv_result.csv", np.column_stack([t, np.array(buf[:total_samples])]),
                   delimiter=",", header="time,voltage", comments="")

        plt.figure(figsize=(10,5))
        plt.plot(t, buf[:total_samples])
        plt.xlabel("t(s)"); plt.ylabel("V"); plt.title("SWV")
        plt.tight_layout(); plt.savefig("swv_result.png", dpi=300); plt.close()

        print("done:", time.time() - t0)
        QTimer.singleShot(1000, app.quit)

timer = QTimer()
timer.timeout.connect(task)
timer.start(30)

sys.exit(app.exec_())
try:
    sys.exit(app.exec_())
finally:
    DAQdll.Write_Port_Out(dev, 0)
