import os, sys, time
import numpy as np
from ctypes import *
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import matplotlib.pyplot as plt
from datetime import datetime

# ====================== 输出路径（对齐DPV） ======================
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
BASE_DIR = "SWV_data"
OUT_DIR = os.path.join(BASE_DIR, RUN_TS)
os.makedirs(OUT_DIR, exist_ok=True)

# ====================== DLL ======================
DAQdll = WinDLL(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Usb_Daq_V6505.dll"
    )
)

dev = 0

# ====================== 多通道参数 ======================
CH_FIRST = 0
CH_LAST = 8
N_CHANNELS = CH_LAST - CH_FIRST + 1

ADC_PER_CHANNEL = 1000
ADC_RATE = ADC_PER_CHANNEL * N_CHANNELS

READ_BLOCK = 200

# ====================== SWV参数 ======================
E_init = -0.2
E_final = 0.6
E_incr = 0.004

amplitude = 0.025
frequency = 10
quiet_time = 2.0
polarity = 1

POINTS_PER_PERIOD = 100
DA_RATE = int(POINTS_PER_PERIOD * frequency)

# ====================== 差分参数 ======================
IDX_LOW = 38
IDX_HIGH = 59

# ====================== 继电器 ======================
relay_channel = 1
relay_settle_time = 0.05


def get_relay_mask(ch):
    if ch == 0: return 15
    if ch == 1: return 240
    if ch == 2: return 3840
    return 0


# ====================== 设备初始化 ======================
err = DAQdll.OpenUSB()
if err != 0:
    raise RuntimeError("USB open failed")

DAQdll.Write_Port_Out(dev, get_relay_mask(relay_channel))
time.sleep(relay_settle_time)


def v2d(v):
    return int((v + 10) / 20 * 65535 + 0.5)


# ====================== SWV生成 ======================
def gen_swv():
    Nq = int(quiet_time * DA_RATE)
    E_q = np.full(Nq, E_init)

    steps = []
    e = E_init

    while True:
        steps.append(e)

        if e >= E_final:
            break

        e += E_incr

    steps = np.array(steps)

    Nh = POINTS_PER_PERIOD // 2
    wave = []

    for e in steps:

        if polarity:
            c = np.concatenate([
                np.full(Nh, e - amplitude),
                np.full(Nh, e + amplitude)
            ])

        else:
            c = np.concatenate([
                np.full(Nh, e + amplitude),
                np.full(Nh, e - amplitude)
            ])

        wave.append(c)

    return np.concatenate([E_q] + wave)


E = gen_swv()

dac = np.array(
    [v2d(x) for x in E],
    dtype=np.uint16
)

total_time = len(E) / DA_RATE
samples_per_channel = int(total_time * ADC_PER_CHANNEL)
total_samples = samples_per_channel * N_CHANNELS

print(
    "DA_RATE:", DA_RATE,
    "DAC:", len(dac),
    "ADC_TOTAL:", total_samples
)

# ====================== DA ======================
DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 1)

DAQdll.Sent_DaData(
    dev,
    len(dac),
    (c_uint * len(dac))(*dac)
)

# ====================== ADC ======================
buf = (c_float * total_samples)()
collected = 0

DAQdll.Ad_Continu_Conf(
    dev,
    CH_FIRST,
    CH_LAST,
    1,      # 单端
    0,
    ADC_RATE,
    0,
    0,
    0,
    0
)

t0 = time.time()

# ====================== UI ======================
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

app = QApplication(sys.argv)

win = pg.GraphicsLayoutWidget(title="SWV Multi-Channel")
win.resize(1000, 600)

plot = win.addPlot()

plot.setLabel('left', 'Voltage (V)')
plot.setLabel('bottom', 'Time (s)')

curve = plot.plot(pen='r')

win.show()


# ====================== 差分计算 ======================
def swv_diff(v):

    # 去静默段
    quiet_points = int(quiet_time * ADC_PER_CHANNEL)
    v = v[quiet_points:]

    # 每周期ADC点数
    P = int((1 / frequency) * ADC_PER_CHANNEL)

    delta = []

    n = 0

    while True:

        low_idx = IDX_LOW + n * P
        high_idx = IDX_HIGH + n * P

        if high_idx >= len(v):
            break

        delta.append(
            v[high_idx] - v[low_idx]
        )

        n += 1

    delta = np.array(delta)

    E = E_init + np.arange(len(delta)) * E_incr

    return E, delta


# ====================== 采集 ======================
def task():
    global collected

    n = DAQdll.Get_AdBuf_Size(dev)

    if n >= READ_BLOCK and collected < total_samples:

        m = min(
            READ_BLOCK,
            total_samples - collected
        )

        tmp = (c_float * m)()

        r = DAQdll.Read_AdBuf(
            dev,
            tmp,
            m
        )

        if r > 0:

            buf[collected:collected + r] = tmp[:r]

            collected += r

            # 实时显示CH0
            raw_now = np.array(
                buf[:collected]
            )

            ch0 = raw_now[0::N_CHANNELS]

            t = np.arange(
                len(ch0)
            ) / ADC_PER_CHANNEL

            curve.setData(
                t,
                ch0
            )

    if collected >= total_samples:

        timer.stop()

        DAQdll.AD_Continu_Stop(dev)

        DAQdll.Set_DA_Scan(
            dev,
            0,
            DA_RATE,
            0
        )

        raw = np.array(
            buf[:total_samples]
        )

        # ====================== 解复用9通道 ======================
        for ch in range(N_CHANNELS):

            ch_data = raw[ch::N_CHANNELS]

            t = np.arange(
                len(ch_data)
            ) / ADC_PER_CHANNEL

            # ====================== 原始数据 ======================
            raw_csv = os.path.join(
                OUT_DIR,
                f"CH{ch}_swv_result_{RUN_TS}.csv"
            )

            raw_png = os.path.join(
                OUT_DIR,
                f"CH{ch}_swv_result_{RUN_TS}.png"
            )

            np.savetxt(
                raw_csv,
                np.column_stack([
                    t,
                    ch_data
                ]),
                delimiter=",",
                header="time,voltage",
                comments=""
            )

            plt.figure(figsize=(10, 5))

            plt.plot(
                t,
                ch_data
            )

            plt.xlabel("Time (s)")
            plt.ylabel("Voltage (V)")
            plt.title(f"CH{ch} SWV Raw")

            plt.tight_layout()

            plt.savefig(
                raw_png,
                dpi=300
            )

            plt.close()

            # ====================== 差分处理 ======================
            E_diff, delta = swv_diff(
                ch_data
            )

            diff_csv = os.path.join(
                OUT_DIR,
                f"CH{ch}_swv_processed_L{IDX_LOW}_H{IDX_HIGH}_{RUN_TS}.csv"
            )

            diff_png = os.path.join(
                OUT_DIR,
                f"CH{ch}_swv_processed_L{IDX_LOW}_H{IDX_HIGH}_{RUN_TS}.png"
            )

            np.savetxt(
                diff_csv,
                np.column_stack([
                    E_diff,
                    delta
                ]),
                delimiter=",",
                header="E(V),deltaV",
                comments=""
            )

            plt.figure(figsize=(8, 4))

            plt.plot(
                E_diff,
                delta
            )

            plt.xlabel("Potential (V)")
            plt.ylabel("ΔV")
            plt.title(f"CH{ch} SWV Differential")

            plt.tight_layout()

            plt.savefig(
                diff_png,
                dpi=300
            )

            plt.close()

        print("done:", time.time() - t0)

        QTimer.singleShot(
            1000,
            app.quit
        )


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
        DAQdll.Set_DA_Scan(
            dev,
            0,
            DA_RATE,
            0
        )
    except:
        pass

    try:
        DAQdll.Write_Port_Out(
            dev,
            0
        )
    except:
        pass

    try:
        DAQdll.CloseUSB()
    except:
        pass