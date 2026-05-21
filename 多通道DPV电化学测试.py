import os
import sys
import time
import numpy as np
from ctypes import *

import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from datetime import datetime

# ====================== 输出路径 ======================
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")

BASE_DIR = "DPV_data"

OUT_DIR = os.path.join(
    BASE_DIR,
    RUN_TS
)

os.makedirs(
    OUT_DIR,
    exist_ok=True
)

# ====================== DLL ======================
dll_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Usb_Daq_V6505.dll"
)

DAQdll = WinDLL(dll_path)

dev = 0

# ====================== 多通道参数 ======================
CH_FIRST = 0
CH_LAST = 8

N_CHANNELS = CH_LAST - CH_FIRST + 1

ADC_PER_CHANNEL = 1000
ADC_RATE = ADC_PER_CHANNEL * N_CHANNELS

READ_BLOCK = 200

# ====================== DPV 参数 ======================
E_init = -0.2
E_final = 0.6
E_incr = 0.004

amplitude = 0.05

pulse_width = 0.1
pulse_period = 0.5

quiet_time = 2.0

POINTS_PER_PERIOD = 100

DA_RATE = int(
    POINTS_PER_PERIOD / pulse_period
)

# ====================== 差分参数 ======================
IDX_LOW = 352
IDX_HIGH = 412

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
def voltage_to_da(v):

    return int(
        (v + 10.0) / 20.0 * 65535 + 0.5
    )


# ====================== 打开设备 ======================
err = DAQdll.OpenUSB()

if err != 0:
    raise RuntimeError("设备打开失败")

DAQdll.Write_Port_Out(
    dev,
    get_relay_mask(relay_channel)
)

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

    N_base = int(
        POINTS_PER_PERIOD *
        (1 - pulse_width / pulse_period)
    )

    N_pulse = (
        POINTS_PER_PERIOD - N_base
    )

    waveform = []

    N_quiet = int(
        quiet_time * DA_RATE
    )

    waveform.append(
        np.full(N_quiet, E_init)
    )

    for E_step in steps:

        base = np.full(
            N_base,
            E_step
        )

        pulse = np.full(
            N_pulse,
            E_step + amplitude
        )

        waveform.append(
            np.concatenate([
                base,
                pulse
            ])
        )

    return np.concatenate(waveform)


# ====================== waveform ======================
E_total = generate_dpv()

wave_data = np.array(
    [voltage_to_da(v) for v in E_total],
    dtype=np.uint16
)

total_time = len(E_total) / DA_RATE

samples_per_channel = int(
    total_time * ADC_PER_CHANNEL
)

total_samples = (
    samples_per_channel *
    N_CHANNELS
)

print(
    "DAC:", len(wave_data),
    "ADC_TOTAL:", total_samples
)

# ====================== DA ======================
DAQdll.Set_DA_Scan(
    dev,
    0,
    DA_RATE,
    1
)

DAQdll.Sent_DaData(
    dev,
    len(wave_data),
    (c_uint * len(wave_data))(*wave_data)
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
    title="DPV Multi-Channel"
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

# ====================== DPV差分 ======================
def dpv_diff(v):

    quiet_points = int(
        quiet_time *
        ADC_PER_CHANNEL
    )

    v = v[quiet_points:]

    P = int(
        pulse_period *
        ADC_PER_CHANNEL
    )

    delta = []

    n = 0

    while True:

        low_idx = IDX_LOW + n * P

        high_idx = IDX_HIGH + n * P

        if high_idx >= len(v):
            break

        delta.append(
            v[high_idx] -
            v[low_idx]
        )

        n += 1

    delta = np.array(delta)

    E_axis = (
        E_init +
        np.arange(len(delta)) * E_incr
    )

    return E_axis, delta


# ====================== 采集 ======================
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

            raw_now = np.array(
                adc_buffer[:collected]
            )

            ch0 = raw_now[0::N_CHANNELS]

            t = np.arange(
                len(ch0)
            ) / ADC_PER_CHANNEL

            curve.setData(
                t,
                ch0
            )

    # ====================== 结束 ======================
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
            adc_buffer[:total_samples]
        )

        # ====== 新增：用于总图 ======
        all_delta = []
        E_ref = None

        # ====================== 解复用9通道 ======================
        for ch in range(N_CHANNELS):

            ch_data = raw[
                ch::N_CHANNELS
            ]

            t = np.arange(
                len(ch_data)
            ) / ADC_PER_CHANNEL

            raw_csv = os.path.join(
                OUT_DIR,
                f"CH{ch}_dpv_result_{RUN_TS}.csv"
            )

            raw_png = os.path.join(
                OUT_DIR,
                f"CH{ch}_dpv_result_{RUN_TS}.png"
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
            plt.plot(t, ch_data)
            plt.xlabel("Time (s)")
            plt.ylabel("Voltage (V)")
            plt.title(f"CH{ch} DPV Raw")
            plt.tight_layout()

            plt.savefig(raw_png, dpi=300)
            plt.close()

            # ====================== 差分 ======================
            E_diff, delta = dpv_diff(ch_data)

            if E_ref is None:
                E_ref = E_diff

            all_delta.append(delta)

            diff_csv = os.path.join(
                OUT_DIR,
                f"CH{ch}_dpv_processed_L{IDX_LOW}_H{IDX_HIGH}_{RUN_TS}.csv"
            )

            diff_png = os.path.join(
                OUT_DIR,
                f"CH{ch}_dpv_processed_L{IDX_LOW}_H{IDX_HIGH}_{RUN_TS}.png"
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
            plt.plot(E_diff, delta)
            plt.xlabel("Potential (V)")
            plt.ylabel("ΔV")
            plt.title(f"CH{ch} DPV Differential")
            plt.tight_layout()

            plt.savefig(diff_png, dpi=300)
            plt.close()

        # ====================== 9通道差分总图 ======================
        plt.figure(figsize=(10, 6))

        for ch in range(N_CHANNELS):
            plt.plot(
                E_ref,
                all_delta[ch],
                label=f"CH{ch}"
            )

        plt.xlabel("Potential (V)")
        plt.ylabel("ΔV")
        plt.title("DPV Differential - All Channels")

        plt.legend()
        plt.tight_layout()

        plt.savefig(
            os.path.join(
                OUT_DIR,
                f"ALL_CH_dpv_differential_{RUN_TS}.png"
            ),
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