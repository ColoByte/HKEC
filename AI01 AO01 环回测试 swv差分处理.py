
import os
import numpy as np
import matplotlib.pyplot as plt

# ====================== 输入文件 ======================
FILE_NAME = "swv_result.csv"

# ====================== SWV基础参数 ======================
QUIET_TIME_SEC = 2.0
ADC_RATE = 1000

POINTS_PER_PERIOD = 100

E_INIT = -0.2
E_INCR = 0.004

# ====================== IDX范围 ======================
IDX_LOW_RANGE = (5, 44)
IDX_HIGH_RANGE = (45, 60)

# ====================== 读取数据 ======================
data = np.loadtxt(FILE_NAME, delimiter=",", skiprows=1)
v = data[:, 1]

# ====================== 去静默段 ======================
quiet_points = int(QUIET_TIME_SEC * ADC_RATE)
v = v[quiet_points:]

# ====================== 截断周期 ======================
n_cycles = len(v) // POINTS_PER_PERIOD
v = v[:n_cycles * POINTS_PER_PERIOD]
v_cycles = v.reshape(n_cycles, POINTS_PER_PERIOD)

# ====================== 电位轴 ======================
E_cycles = E_INIT + np.arange(n_cycles) * E_INCR

# ====================== 输出目录（关键修改） ======================
OUT_DIR = "SWV_data"
os.makedirs(OUT_DIR, exist_ok=True)

# ====================== 穷举计算 ======================
for low in range(IDX_LOW_RANGE[0], IDX_LOW_RANGE[1] + 1):
    for high in range(IDX_HIGH_RANGE[0], IDX_HIGH_RANGE[1] + 1):

        if low >= high:
            continue

        delta_v = v_cycles[:, high] - v_cycles[:, low]

        tag = f"L{low}_H{high}"

        csv_path = os.path.join(OUT_DIR, f"swv_processed_{tag}.csv")
        png_path = os.path.join(OUT_DIR, f"swv_processed_{tag}.png")

        np.savetxt(
            csv_path,
            np.column_stack([E_cycles, delta_v]),
            delimiter=",",
            header="E(V),deltaV",
            comments=""
        )

        plt.figure(figsize=(8, 4))
        plt.plot(E_cycles, delta_v, linewidth=1.2)
        plt.xlabel("Potential (V)")
        plt.ylabel("ΔV")
        plt.title(f"SWV {tag}")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(png_path, dpi=300)
        plt.close()

        print(f"saved: {tag}")