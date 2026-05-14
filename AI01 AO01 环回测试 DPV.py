import os
from ctypes import *
import numpy as np
import time
import sys
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import matplotlib.pyplot as plt

# ====================== DLL ======================
dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Usb_Daq_V6505.dll")
DAQdll = WinDLL(dll_path)

dev = 0
ADC_RATE = 1000
READ_BLOCK = 200

# ====================== DPV 参数 ======================
E_init = -0.2
E_final = 0.2
E_incr = 0.004

amplitude = 0.05
pulse_width = 0.05
pulse_period = 0.5
quiet_time = 1.0

POINTS_PER_PERIOD = 100
DA_RATE = int(POINTS_PER_PERIOD / pulse_period)

# ====================== 继电器 ======================
relay_channel = 1
relay_settle_time = 0.05

def get_relay_mask(ch):
    if ch == 0: return 15
    if ch == 1: return 240
    if ch == 2: return 3840
    return 0

# ====================== DAC ======================
def voltage_to_da(v):
    return int((v + 10.0) / 20.0 * 65535 + 0.5)

# ====================== 打开设备 ======================
err = DAQdll.OpenUSB()
if err != 0:
    raise RuntimeError("设备打开失败")

# ✔️ 统一：继电器控制（必须在DAQ开始前）
DAQdll.Write_Port_Out(dev, get_relay_mask(relay_channel))
time.sleep(relay_settle_time)

# ====================== DPV生成 ======================
def generate_dpv():

    steps = []
    E = E_init
    while True:
        steps.append(E)
        if E >= E_final:
            break
        E += E_incr
    steps = np.array(steps)

    N_base = int(POINTS_PER_PERIOD * (1 - pulse_width / pulse_period))
    N_pulse = POINTS_PER_PERIOD - N_base

    waveform = []

    N_quiet = int(quiet_time * DA_RATE)
    waveform.append(np.full(N_quiet, E_init))

    for E_step in steps:
        base = np.full(N_base, E_step)
        pulse = np.full(N_pulse, E_step + amplitude)
        waveform.append(np.concatenate([base, pulse]))

    return np.concatenate(waveform)

# ====================== waveform ======================
E_total = generate_dpv()
wave_data = np.array([voltage_to_da(v) for v in E_total], dtype=np.uint16)

total_time = len(E_total) / DA_RATE
total_samples = int(total_time * ADC_RATE)

print("DAC:", len(wave_data), "ADC:", total_samples)

# ====================== DA ======================
DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 1)
DAQdll.Sent_DaData(dev, len(wave_data), (c_uint * len(wave_data))(*wave_data))

# ====================== ADC ======================
adc_buffer = (c_float * total_samples)()
collected = 0

DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)
t0 = time.time()

# ====================== UI ======================
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

app = QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(title="DPV实时采集")
win.resize(1000, 600)

plot = win.addPlot()
plot.setLabel('left', 'Voltage (V)')
plot.setLabel('bottom', 't (s)')
plot.setYRange(-0.5, 0.5)

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
            adc_buffer[collected:collected + r] = tmp[:r]
            collected += r

            t = np.arange(collected) / ADC_RATE
            curve.setData(t, np.array(adc_buffer[:collected]))

    if collected >= total_samples:

        timer.stop()

        DAQdll.AD_Continu_Stop(dev)
        DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 0)

        t = np.arange(total_samples) / ADC_RATE

        np.savetxt(
            "dpv_result.csv",
            np.column_stack([t, np.array(adc_buffer[:total_samples])]),
            delimiter=",",
            header="time,voltage",
            comments=""
        )

        plt.figure(figsize=(10, 5))
        plt.plot(t, adc_buffer[:total_samples])
        plt.xlabel("Time (s)")
        plt.ylabel("Voltage (V)")
        plt.title("DPV Result")
        plt.savefig("dpv_result.png", dpi=300)

        print("完成，数据已保存")

        QTimer.singleShot(1000, app.quit)

# ====================== timer ======================
timer = QTimer()
timer.timeout.connect(task)
timer.start(30)

# ====================== 统一安全退出 ======================
try:
    sys.exit(app.exec_())
finally:
    try:
        DAQdll.AD_Continu_Stop(dev)
    except:
        pass

    try:
        DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 0)
    except:
        pass

    try:
        DAQdll.Write_Port_Out(dev, 0)
    except:
        pass

    try:
        DAQdll.CloseUSB()
    except:
        pass