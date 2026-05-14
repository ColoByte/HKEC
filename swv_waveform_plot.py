import matplotlib.pyplot as plt
from swv_waveform import generate_swv_waveform, save_waveform

# ===== 参数 =====
E_init = -0.2
E_final = 0.8
E_incr = 0.004

amplitude = 0.025   # 半幅
frequency = 10      # Hz
quiet_time = 2

# ===== 生成 =====
t, E = generate_swv_waveform(
    E_init,
    E_final,
    E_incr,
    amplitude,
    frequency,
    quiet_time,
    polarity=1
)

# ===== 保存 =====
save_waveform("swv_waveform.csv", t, E)

# ===== 全局图 =====
plt.figure(figsize=(12, 4))
plt.plot(t, E)
plt.title("SWV Waveform (Global)")
plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.grid(True)


# =====================================================
# ===== 局部放大（同DPV逻辑）=====
# =====================================================
enable_zoom = True

# 参数（按需改）
start = 0.0  # float=ratio，int=索引
end = 0.2     # float=ratio，int=索引
step = 0      # >0优先（长度），=0用end

if enable_zoom:
    N = len(t)

    # start
    if isinstance(start, float):
        s = int(N * start)
    else:
        s = int(start)

    # end / step
    if step > 0:
        e = s + step
    else:
        if isinstance(end, float):
            e = int(N * end)
        else:
            e = int(end)

    # 边界保护
    s = max(0, s)
    e = min(N, e)

    plt.figure(figsize=(12, 4))
    plt.plot(t[s:e], E[s:e])
    plt.title(f"SWV Waveform (Zoom [{s}:{e}])")
    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (V)")
    plt.grid(True)

plt.show()