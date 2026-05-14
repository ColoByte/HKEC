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

# ====================== CV参数 ======================
E_init, E_low, E_high = -0.2, -0.2, 0.6
scan_rate = 0.1
segments = 4
quiet_time = 2.0
direction = 0
fs = 100

# ====================== 继电器控制 ======================
relay_channel = 1
relay_settle_time = 0.05

def get_relay_mask(ch):
    if ch == 0: return 15
    if ch == 1: return 240
    if ch == 2: return 3840
    return 0

# ====================== 打开设备 ======================
err = DAQdll.OpenUSB()
if err != 0: raise RuntimeError("USB open failed")

DAQdll.Write_Port_Out(dev, get_relay_mask(relay_channel))
time.sleep(relay_settle_time)

# ====================== DAC转换 ======================
def v2d(v): return int((v + 10) / 20 * 65535 + 0.5)

# ====================== CV波形生成 ======================
def generate_cv_waveform(E_init, E_low, E_high, scan_rate, segments, quiet_time, direction, fs):

    dt = 1 / fs

    T_half = (E_high - E_low) / scan_rate
    N_half = int(np.floor(T_half * fs))
    N_total = segments * N_half

    N_quiet = int(np.floor(quiet_time * fs))
    E_quiet = np.full(N_quiet, E_init)

    up = np.linspace(E_low, E_high, N_half, endpoint=False)
    down = np.linspace(E_high, E_low, N_half, endpoint=False)

    waveform = []
    current_up = (direction == 0)

    for _ in range(segments + 1):
        waveform.append(up if current_up else down)
        current_up = not current_up

    E_full = np.concatenate(waveform)

    ratio = (E_init - E_low) / (E_high - E_low) if direction == 0 else (E_high - E_init) / (E_high - E_low)
    idx = int(round(ratio * N_half))

    E_main = E_full[idx:idx + N_total]
    E_total = np.concatenate([E_quiet, E_main])

    t = np.arange(len(E_total)) * dt
    return t, E_total


# ====================== 生成CV波形 ======================
t, E_total = generate_cv_waveform(
    E_init, E_low, E_high,
    scan_rate, segments,
    quiet_time, direction, fs
)

dac = np.array([v2d(x) for x in E_total], dtype=np.uint16)

total_time = len(E_total) / fs
total_samples = int(total_time * ADC_RATE)

print("DAC:", len(dac), "ADC:", total_samples)

# ====================== DA ======================
DAQdll.Set_DA_Scan(dev, 0, fs, 1)
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
win = pg.GraphicsLayoutWidget(title="CV")
win.resize(1000, 600)

plot = win.addPlot()
plot.setLabel('left', 'V')
plot.setLabel('bottom', 't(s)')
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

            tt = np.arange(collected) / ADC_RATE
            curve.setData(tt, np.array(buf[:collected]))

    if collected >= total_samples:

        timer.stop()

        DAQdll.AD_Continu_Stop(dev)
        DAQdll.Set_DA_Scan(dev, 0, fs, 0)
        DAQdll.Write_Port_Out(dev, 0)

        t_adc = np.arange(total_samples) / ADC_RATE

        np.savetxt(
            "cv_result.csv",
            np.column_stack([t_adc, np.array(buf[:total_samples])]),
            delimiter=",",
            header="time,voltage",
            comments=""
        )

        plt.figure(figsize=(10, 5))
        plt.plot(t_adc, buf[:total_samples])
        plt.xlabel("t(s)")
        plt.ylabel("V")
        plt.title("CV")
        plt.tight_layout()
        plt.savefig("cv_result.png", dpi=300)
        plt.close()

        DAQdll.CloseUSB()
        print("done:", time.time() - t0)
        QTimer.singleShot(1000, app.quit)

# ====================== timer ======================
timer = QTimer()
timer.timeout.connect(task)
timer.start(30)

try:
    sys.exit(app.exec_())
finally:
    DAQdll.AD_Continu_Stop(dev)
    DAQdll.Set_DA_Scan(dev, 0, fs, 0)
    DAQdll.Write_Port_Out(dev, 0)
    DAQdll.CloseUSB()