import matplotlib.pyplot as plt
from cv_waveform import generate_cv_waveform, save_waveform


# ===== 测试参数 =====
E_init = 0
E_low = -0.2
E_high = 0.6
scan_rate = 0.2      # V/s
segments = 10         # 半周期数
quiet_time = 2       # s
direction = 0        # 先向 High
fs = 100             # Hz

# ===== 生成波形 =====
t, E = generate_cv_waveform(
    E_init,
    E_low,
    E_high,
    scan_rate,
    segments,
    quiet_time,
    direction,
    fs
)

# ===== 保存 =====
save_waveform("cv_waveform.csv", t, E)

# ===== 可视化 =====
plt.figure(figsize=(10, 5))
plt.plot(t, E)

# 标记关键电位
plt.axhline(E_high, linestyle='--', label='High')
plt.axhline(E_low, linestyle='--', label='Low')
plt.axhline(E_init, linestyle=':', label='Initial')

plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.title("CV Waveform (Triangle Scan)")
plt.legend()
plt.grid(True)

plt.show()