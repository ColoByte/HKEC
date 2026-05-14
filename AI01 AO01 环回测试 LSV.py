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

# ====================== LSV参数 ======================
E_init = -0.2
E_final = 0.6
scan_rate = 0.1
quiet_time = 2.0
fs = 100

relay_channel = 1
relay_settle_time = 0.05

def get_relay_mask(ch):
    if ch == 0: return 15
    if ch == 1: return 240
    if ch == 2: return 3840
    return 0

# ====================== DAC ======================
def v2d(v): return int((v + 10) / 20 * 65535 + 0.5)

# ====================== 设备初始化 ======================
err = DAQdll.OpenUSB()
if err != 0: raise RuntimeError("USB open failed")

DAQdll.Write_Port_Out(dev, get_relay_mask(relay_channel))
time.sleep(relay_settle_time)

# ====================== LSV生成 ======================
def generate_lsv(E_init, E_final, scan_rate, quiet_time, fs):

    dt = 1 / fs

    Nq = int(round(quiet_time * fs))
    E_q = np.full(Nq, E_init)

    dE = scan_rate * dt
    ramp = np.arange(E_init, E_final, dE)

    E_total = np.concatenate([E_q, ramp])
    t = np.arange(len(E_total)) * dt

    return t, E_total

# ====================== waveform ======================
t, E_total = generate_lsv(E_init, E_final, scan_rate, quiet_time, fs)
dac = np.array([v2d(x) for x in E_total], dtype=np.uint16)

total_time = len(E_total) / fs
total_samples = int(total_time * ADC_RATE)

print("DAC:", len(dac), "ADC:", total_samples)

# ====================== DAC ======================
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
win = pg.GraphicsLayoutWidget(title="LSV")
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

            t_adc = np.arange(collected) / ADC_RATE
            curve.setData(t_adc, np.array(buf[:collected]))

    if collected >= total_samples:

        timer.stop()
        DAQdll.AD_Continu_Stop(dev)
        DAQdll.Set_DA_Scan(dev, 0, fs, 0)

        t_adc = np.arange(total_samples) / ADC_RATE

        np.savetxt(
            "lsv_result.csv",
            np.column_stack([t_adc, np.array(buf[:total_samples])]),
            delimiter=",",
            header="time,voltage",
            comments=""
        )

        plt.figure(figsize=(10, 5))
        plt.plot(t_adc, buf[:total_samples])
        plt.xlabel("t(s)")
        plt.ylabel("V")
        plt.title("LSV")
        plt.tight_layout()
        plt.savefig("lsv_result.png", dpi=300)
        plt.close()

        DAQdll.Write_Port_Out(dev, 0)
        DAQdll.CloseUSB()

        print("done:", time.time() - t0)
        QTimer.singleShot(60000, app.quit)

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