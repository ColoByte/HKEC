import os
import time
import numpy as np
from ctypes import *
from datetime import datetime

# ====================== 输出路径 ======================
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")

BASE_DIR = "恒定电位采集"
OUT_DIR = os.path.join(BASE_DIR, RUN_TS)

os.makedirs(OUT_DIR, exist_ok=True)

# ====================== DLL ======================
dll_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Usb_Daq_V6505.dll"
)

DAQdll = WinDLL(dll_path)

dev = 0

# ====================== 参数区 ======================

# ADC采样率
ADC_RATE = 10

# DAC刷新率
DAC_RATE = 10

# 每次读取点数
READ_BLOCK = 20

# 静默稳定时间（秒）
SETTLE_TIME = 2.0

# 实际采集时间（秒）
MEASURE_TIME = 3.0

# DAC恒定偏置电压（V）
DAC_OUTPUT = 0.6

# ADC采集通道
CHANNEL = 3

# 外部负载电阻（Ω）
R = 480000

# 跨阻档位
# 0 -> 1kΩ
# 1 -> 10kΩ
# 2 -> 100kΩ
relay_channel = 0

# 继电器切换稳定时间
relay_settle_time = 0.05

# ====================== 跨阻映射 ======================
R_FEEDBACK = {
    0: 1e3,
    1: 10e3,
    2: 100e3
}

R_VALUE = R_FEEDBACK[relay_channel]

# ====================== 继电器mask ======================
def get_relay_mask(ch):

    if ch == 0:
        return 15

    if ch == 1:
        return 240

    if ch == 2:
        return 3840

    return 0

# ====================== DAC码值转换 ======================
def voltage_to_da(v):
    return int((v + 10.0) / 20.0 * 65535 + 0.5)

# ====================== 初始化设备 ======================
err = DAQdll.OpenUSB()

if err != 0:
    raise RuntimeError("设备打开失败")

# 设置跨阻继电器
DAQdll.Write_Port_Out(dev, get_relay_mask(relay_channel))

time.sleep(relay_settle_time)

# ====================== DAC输出 ======================

# DAC总输出时间：
# 静默 + 采集
TOTAL_TIME = SETTLE_TIME + MEASURE_TIME

dac_points = int(TOTAL_TIME * DAC_RATE)

dac_wave = np.full(dac_points, DAC_OUTPUT)

dac_data = np.array(
    [voltage_to_da(v) for v in dac_wave],
    dtype=np.uint16
)

print("启动DAC恒定输出...")

DAQdll.Set_DA_Scan(dev, 0, DAC_RATE, 1)

DAQdll.Sent_DaData(
    dev,
    len(dac_data),
    (c_uint * len(dac_data))(*dac_data)
)

# ====================== 静默等待 ======================
print(f"静默稳定 {SETTLE_TIME:.1f} s ...")

time.sleep(SETTLE_TIME)

# ====================== ADC采集配置 ======================
total_samples = int(MEASURE_TIME * ADC_RATE)

adc_buffer = (c_float * total_samples)()

print("开始ADC采集...")

DAQdll.Ad_Continu_Conf(
    dev,
    CHANNEL,
    CHANNEL,
    1,
    0,
    ADC_RATE,
    0,
    0,
    0,
    0
)

# ====================== 连续读取 ======================
collected = 0

t0 = time.time()

while collected < total_samples:

    n = DAQdll.Get_AdBuf_Size(dev)

    if n >= READ_BLOCK:

        m = min(READ_BLOCK, total_samples - collected)

        tmp = (c_float * m)()

        r = DAQdll.Read_AdBuf(dev, tmp, m)

        if r > 0:

            adc_buffer[collected:collected + r] = tmp[:r]

            collected += r

    time.sleep(0.01)

# ====================== 停止DAQ ======================
DAQdll.AD_Continu_Stop(dev)

DAQdll.Set_DA_Scan(dev, 0, DAC_RATE, 0)

# ====================== 数据处理 ======================
voltage = np.array(adc_buffer[:total_samples])

# 实际电流（mA）
current_mA = voltage / R_VALUE * 1000

# 时间轴
t = np.arange(total_samples) / ADC_RATE

# ====================== 理论电流 ======================
theory_current_A = DAC_OUTPUT / R

theory_current_mA = theory_current_A * 1000

# ====================== 实际平均电流 ======================
actual_current_mA = np.mean(current_mA)

# ====================== 比值 ======================
if theory_current_mA != 0:
    ratio = actual_current_mA / theory_current_mA
else:
    ratio = np.nan

# ====================== 平均电压 ======================
voltage_mean = np.mean(voltage)

# ====================== 输出CSV ======================
csv_path = os.path.join(
    OUT_DIR,
    f"CH{CHANNEL}_{RUN_TS}.csv"
)

np.savetxt(
    csv_path,
    np.column_stack([t, voltage, current_mA]),
    delimiter=",",
    header="time,voltage(V),current(mA)",
    comments="",
    fmt="%.6e"
)

# ====================== 输出TXT统计报告 ======================
txt_path = os.path.join(
    OUT_DIR,
    f"CH{CHANNEL}_report_{RUN_TS}.txt"
)

with open(txt_path, "w", encoding="utf-8") as f:

    f.write("=" * 60 + "\n")
    f.write("恒定电位电流验证报告\n")
    f.write("=" * 60 + "\n\n")

    f.write("【实验参数】\n")
    f.write(f"时间戳: {RUN_TS}\n")
    f.write(f"通道: CH{CHANNEL}\n")
    f.write(f"ADC采样率: {ADC_RATE} Hz\n")
    f.write(f"DAC刷新率: {DAC_RATE} Hz\n")
    f.write(f"静默时间: {SETTLE_TIME:.3f} s\n")
    f.write(f"采集时间: {MEASURE_TIME:.3f} s\n")
    f.write(f"偏置电压: {DAC_OUTPUT:.6f} V\n")
    f.write(f"跨阻反馈电阻: {R_VALUE:.0f} Ω\n")
    f.write(f"外部负载电阻 R: {R:.0f} Ω\n\n")

    f.write("【测量结果】\n")
    f.write(f"平均电压: {voltage_mean:.6e} V\n")
    f.write(f"实际平均电流: {actual_current_mA:.6e} mA\n")
    f.write(f"理论电流: {theory_current_mA:.6e} mA\n")
    f.write(f"实际/理论: {ratio:.6f}\n\n")

    f.write("=" * 60 + "\n")
    f.write(
        "生成时间: " +
        datetime.now().strftime("%Y-%m-%d %H:%M:%S") +
        "\n"
    )
    f.write("=" * 60 + "\n")

# ====================== 终端输出 ======================
print("\n==============================")
print("恒定电位电流验证完成")
print("==============================")

print(f"通道: CH{CHANNEL}")

print(f"跨阻值: {R_VALUE:.0f} Ω")

print(f"外部电阻 R: {R:.0f} Ω")

print(f"平均实际电流: {actual_current_mA:.6e} mA")

print(f"理论电流: {theory_current_mA:.6e} mA")

print(f"实际/理论: {ratio:.6f}")

print("------------------------------")

print(f"CSV文件: {csv_path}")

print(f"统计报告: {txt_path}")

print(f"总耗时: {time.time() - t0:.3f} s")

print("==============================\n")

# ====================== 安全退出 ======================
try:

    DAQdll.Write_Port_Out(dev, 0)

    DAQdll.CloseUSB()

except:
    pass