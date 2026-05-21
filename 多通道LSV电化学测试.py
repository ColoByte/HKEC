import os
import sys
import time
import numpy as np
from ctypes import *

import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

import matplotlib.pyplot as plt
from datetime import datetime

# ====================== 输出路径（对齐DPV/SWV/CV） ======================
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")

BASE_DIR = "LSV_data"

OUT_DIR = os.path.join(
    BASE_DIR,
    RUN_TS
)

os.makedirs(
    OUT_DIR,
    exist_ok=True
)

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

# ====================== LSV参数 ======================
E_init = -0.2
E_final = 0.6

scan_rate = 0.1

quiet_time = 2.0

fs = 100

# ====================== 继电器 ======================
relay_channel = 1

relay_settle_time = 0.05

def get_relay_mask(ch):

    if ch == 0:
        return 15

    if ch == 1:
        return 240

    if ch == 2:
        return 3840

    return 0

# ====================== DAC转换 ======================
def v2d(v):

    return int(
        (v + 10.0) / 20.0 * 65535 + 0.5
    )

# ====================== 初始化 ======================
err = DAQdll.OpenUSB()

if err != 0:
    raise RuntimeError("USB open failed")

DAQdll.Write_Port_Out(
    dev,
    get_relay_mask(relay_channel)
)

time.sleep(relay_settle_time)

# ====================== cleanup ======================
cleanup_done = False

def cleanup():

    global cleanup_done

    if cleanup_done:
        return

    cleanup_done = True

    try:
        DAQdll.AD_Continu_Stop(dev)
    except:
        pass

    try:
        DAQdll.Set_DA_Scan(
            dev,
            0,
            fs,
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

# ====================== LSV waveform ======================
def generate_lsv():

    dt = 1 / fs

    # 静默段
    Nq = int(round(
        quiet_time * fs
    ))

    E_q = np.full(
        Nq,
        E_init
    )

    # ramp
    dE = scan_rate * dt

    ramp = np.arange(
        E_init,
        E_final,
        dE
    )

    # 总波形
    E_total = np.concatenate([
        E_q,
        ramp
    ])

    return E_total

# ====================== waveform ======================
E_total = generate_lsv()

dac = np.array(
    [v2d(v) for v in E_total],
    dtype=np.uint16
)

total_time = len(E_total) / fs

samples_per_channel = int(
    total_time * ADC_PER_CHANNEL
)

total_samples = (
    samples_per_channel *
    N_CHANNELS
)

print(
    "DAC:", len(dac),
    "ADC_TOTAL:", total_samples
)

# ====================== DA ======================
DAQdll.Set_DA_Scan(
    dev,
    0,
    fs,
    1
)

DAQdll.Sent_DaData(
    dev,
    len(dac),
    (c_uint * len(dac))(*dac)
)

# ====================== ADC ======================
adc_buffer = (
    c_float * total_samples
)()

collected = 0

DAQdll.Ad_Continu_Conf(
    dev,
    CH_FIRST,
    CH_LAST,
    1,
    0,
    ADC_RATE,
    0,
    0,
    0,
    0
)

t0 = time.time()

# ====================== UI ======================
pg.setConfigOption(
    'background',
    'w'
)

pg.setConfigOption(
    'foreground',
    'k'
)

app = QApplication(sys.argv)

win = pg.GraphicsLayoutWidget(
    title="LSV Multi-Channel"
)

win.resize(1000, 600)

plot = win.addPlot()

plot.setLabel(
    'left',
    'Voltage (V)'
)

plot.setLabel(
    'bottom',
    'Time (s)'
)

curve = plot.plot(
    pen='r'
)

win.show()

# ====================== task ======================
def task():

    global collected

    n = DAQdll.Get_AdBuf_Size(dev)

    if (
        n >= READ_BLOCK and
        collected < total_samples
    ):

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

            adc_buffer[
                collected:collected + r
            ] = tmp[:r]

            collected += r

            # 实时显示CH0
            raw_now = np.array(
                adc_buffer[:collected]
            )

            ch0 = raw_now[
                0::N_CHANNELS
            ]

            t = np.arange(
                len(ch0)
            ) / ADC_PER_CHANNEL

            curve.setData(
                t,
                ch0
            )

    # ====================== 采集结束 ======================
    if collected >= total_samples:

        timer.stop()

        cleanup()

        raw = np.array(
            adc_buffer[:total_samples]
        )

        all_curves = []

        # ====================== 解复用多通道 ======================
        for ch in range(N_CHANNELS):

            ch_data = raw[
                ch::N_CHANNELS
            ]

            t = np.arange(
                len(ch_data)
            ) / ADC_PER_CHANNEL

            csv_path = os.path.join(
                OUT_DIR,
                f"CH{ch}_lsv_{RUN_TS}.csv"
            )

            png_path = os.path.join(
                OUT_DIR,
                f"CH{ch}_lsv_{RUN_TS}.png"
            )

            # ====================== CSV ======================
            np.savetxt(
                csv_path,
                np.column_stack([
                    t,
                    ch_data
                ]),
                delimiter=",",
                header="time,voltage",
                comments=""
            )

            # ====================== PNG ======================
            plt.figure(figsize=(10, 5))

            plt.plot(
                t,
                ch_data
            )

            plt.xlabel("Time (s)")
            plt.ylabel("Voltage (V)")

            plt.title(f"CH{ch} LSV")

            plt.tight_layout()

            plt.savefig(
                png_path,
                dpi=300
            )

            plt.close()

            all_curves.append(
                (t, ch_data)
            )

        # ====================== 总图 ======================
        plt.figure(figsize=(10, 6))

        for ch in range(N_CHANNELS):

            plt.plot(
                all_curves[ch][0],
                all_curves[ch][1],
                label=f"CH{ch}"
            )

        plt.xlabel("Time (s)")
        plt.ylabel("Voltage (V)")

        plt.title(
            "LSV Multi-Channel Overlay"
        )

        plt.legend()

        plt.tight_layout()

        plt.savefig(
            os.path.join(
                OUT_DIR,
                f"ALL_CH_lsv_{RUN_TS}.png"
            ),
            dpi=300
        )

        plt.close()

        print(
            "done:",
            time.time() - t0
        )

        QTimer.singleShot(
            1000,
            app.quit
        )

# ====================== timer ======================
timer = QTimer()

timer.timeout.connect(task)

timer.start(30)

# ====================== 安全退出 ======================
try:

    sys.exit(app.exec_())

finally:

    cleanup()