import matplotlib.pyplot as plt
from lsv_waveform import generate_lsv_waveform, save_waveform

# ===== 参数 =====
E_init = -0.2
E_final = 0.6
scan_rate = 0.1   # V/s
quiet_time = 2

# ===== 生成 =====
t, E = generate_lsv_waveform(
    E_init,
    E_final,
    scan_rate,
    quiet_time
)

# ===== 保存 =====
save_waveform("lsv_waveform.csv", t, E)

# ===== 全局波形 =====
plt.figure(figsize=(10, 4))
plt.plot(t, E)
plt.title("LSV Waveform")
plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.grid(True)


# =====================================================
# ===== 局部放大（统一DPV/SWV逻辑）=====
# =====================================================
enable_zoom = True

# 参数（按需改）
start = 0.0   # float=ratio，int=索引
end = 1.0     # float=ratio，int=索引
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

    plt.figure(figsize=(10, 4))
    plt.plot(t[s:e], E[s:e])
    plt.title(f"LSV Zoom [{s}:{e}]")
    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (V)")
    plt.grid(True)

plt.show()