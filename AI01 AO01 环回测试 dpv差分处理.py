import os
import numpy as np
import matplotlib.pyplot as plt

# ====================== 输入文件 ======================
FILE_NAME = r"E:\Projects\Pycharm\Electrochem_platform\HKEC\DPV_data\20260515_165103\dpv_result.csv"

# ====================== DPV基础参数（与采集保持一致） ======================
QUIET_TIME_SEC = 1.0
ADC_RATE = 1000

# DPV周期（ADC视角）
PULSE_PERIOD_SEC = 0.5
POINTS_PER_PERIOD = int(PULSE_PERIOD_SEC * ADC_RATE)   # 500

# DPV电位参数（与采集保持一致）
E_INIT = -0.2
E_INCR = 0.004

# ====================== IDX范围 ======================
# 第一个周期内的采样位置
IDX_LOW_RANGE = (340, 360)
IDX_HIGH_RANGE = (400, 416)

# 穷举步长（你可自由改）
IDX_LOW_STEP = 1
IDX_HIGH_STEP = 1

# ====================== 读取数据 ======================
data = np.loadtxt(FILE_NAME, delimiter=",", skiprows=1)
v = data[:, 1]

# ====================== 输出目录（文件同级目录） ======================
file_dir = os.path.dirname(os.path.abspath(FILE_NAME))
OUT_DIR = os.path.join(file_dir, "差分处理")
os.makedirs(OUT_DIR, exist_ok=True)

# ====================== 去静默段 ======================
quiet_points = int(QUIET_TIME_SEC * ADC_RATE)

if len(v) <= quiet_points:
    raise ValueError("数据长度不足，无法去静默")

v = v[quiet_points:]

# # ====================== 输出目录 ======================
# OUT_DIR = "DPV_data"
# os.makedirs(OUT_DIR, exist_ok=True)

# ====================== 穷举 ======================
for low0 in range(
        IDX_LOW_RANGE[0],
        IDX_LOW_RANGE[1] + 1,
        IDX_LOW_STEP):

    for high0 in range(
            IDX_HIGH_RANGE[0],
            IDX_HIGH_RANGE[1] + 1,
            IDX_HIGH_STEP):

        if low0 >= high0:
            continue

        delta_v = []

        # ====================== 周期递推（关键修改） ======================
        n = 0

        while True:

            low_idx = low0 + n * POINTS_PER_PERIOD
            high_idx = high0 + n * POINTS_PER_PERIOD

            # 最后一个周期越界，直接丢弃
            if low_idx >= len(v):
                break

            if high_idx >= len(v):
                break

            dv = v[high_idx] - v[low_idx]
            delta_v.append(dv)

            n += 1

        # 没有有效点，跳过
        if len(delta_v) == 0:
            continue

        delta_v = np.array(delta_v)

        # ====================== 电位轴 ======================
        E_cycles = E_INIT + np.arange(len(delta_v)) * E_INCR

        # ====================== 文件名 ======================
        tag = f"L{low0}_H{high0}"

        csv_path = os.path.join(
            OUT_DIR,
            f"dpv_processed_{tag}.csv"
        )

        png_path = os.path.join(
            OUT_DIR,
            f"dpv_processed_{tag}.png"
        )

        # ====================== 保存CSV ======================
        np.savetxt(
            csv_path,
            np.column_stack([E_cycles, delta_v]),
            delimiter=",",
            header="E(V),deltaV",
            comments=""
        )

        # ====================== 绘图 ======================
        plt.figure(figsize=(8, 4))

        plt.plot(
            E_cycles,
            delta_v,
            linewidth=1.2
        )

        plt.xlabel("Potential (V)")
        plt.ylabel("ΔV")
        plt.title(f"DPV {tag}")

        plt.grid(alpha=0.3)
        plt.tight_layout()

        plt.savefig(
            png_path,
            dpi=300
        )

        plt.close()

        print(f"saved: {tag}")

print("全部处理完成")