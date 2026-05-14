# 这个版本是针对起始点不是low E 的
# import numpy as np
#
#
# def generate_cv_waveform(
#     E_init,
#     E_low,
#     E_high,
#     scan_rate,
#     segments,
#     quiet_time,
#     direction=0,
#     fs=100
# ):
#     """
#     生成CV三角波（线性推进 + 边界反射）
#
#     参数：
#         E_init      : 初始电位 (V)
#         E_low       : 下限电位 (V)
#         E_high      : 上限电位 (V)
#         scan_rate   : 扫描速率 (V/s)
#         segments    : 半周期数（按时间截断）
#         quiet_time  : 静置时间 (s)
#         direction   : 0=正向（先向High），1=反向（先向Low）
#         fs          : 采样率 (Hz)
#
#     返回：
#         t : 时间数组
#         E : 电压数组
#     """
#
#     # ---------- 参数检查 ----------
#     if not (E_low < E_high):
#         raise ValueError("E_low 必须小于 E_high")
#
#     if not (E_low <= E_init <= E_high):
#         raise ValueError("E_init 必须在 [E_low, E_high] 范围内")
#
#     if scan_rate <= 0:
#         raise ValueError("scan_rate 必须 > 0")
#
#     if segments <= 0 or int(segments) != segments:
#         raise ValueError("segments 必须为正整数")
#
#     if fs <= 0:
#         raise ValueError("fs 必须 > 0")
#
#     # ---------- 时间参数 ----------
#     dt = 1.0 / fs
#     delta_E = scan_rate * dt
#
#     T_half = (E_high - E_low) / scan_rate
#     T_total = segments * T_half
#
#     N_main = int(np.floor(T_total * fs))
#     N_quiet = int(np.floor(quiet_time * fs))
#
#     # ---------- 初始化 ----------
#     total_length = N_quiet + N_main
#     E = np.zeros(total_length)
#     t = np.arange(total_length) * dt
#
#     # ---------- Quiet Time ----------
#     if N_quiet > 0:
#         E[:N_quiet] = E_init
#
#     # ---------- 扫描初始化 ----------
#     current_E = E_init
#     slope_sign = 1 if direction == 0 else -1
#
#     # ---------- 主循环 ----------
#     for i in range(N_quiet, total_length):
#         next_E = current_E + slope_sign * delta_E
#
#         # --- 边界镜像反射 ---
#         if next_E > E_high:
#             next_E = E_high - (next_E - E_high)
#             slope_sign *= -1
#
#         elif next_E < E_low:
#             next_E = E_low + (E_low - next_E)
#             slope_sign *= -1
#
#         E[i] = next_E
#         current_E = next_E
#
#     return t, E
#
#
# def save_waveform_to_file(filename, t, E):
#     """
#     保存波形到文件（csv）
#     """
#     data = np.column_stack((t, E))
#     np.savetxt(filename, data, delimiter=",", header="time,voltage", comments="")


#这个版本针对起始点是low E,使用了 linspace
import numpy as np


def generate_cv_waveform(
    E_init,
    E_low,
    E_high,
    scan_rate,
    segments,
    quiet_time,
    direction=0,
    fs=100
):
    """
    使用 linspace 分段生成 CV 波形（避免误差累积）

    参数：
        E_init      : 初始电位
        E_low       : 下限
        E_high      : 上限
        scan_rate   : 扫描速率 (V/s)
        segments    : 半周期数
        quiet_time  : 静置时间 (s)
        direction   : 0=先向上, 1=先向下
        fs          : 采样率

    返回：
        t, E
    """

    # ---------- 参数检查 ----------
    if not (E_low < E_high):
        raise ValueError("E_low 必须小于 E_high")

    if not (E_low <= E_init <= E_high):
        raise ValueError("E_init 必须在范围内")

    if scan_rate <= 0:
        raise ValueError("scan_rate 必须 > 0")

    if segments <= 0 or int(segments) != segments:
        raise ValueError("segments 必须为正整数")

    # ---------- 时间参数 ----------
    dt = 1 / fs

    # 半周期时间
    T_half = (E_high - E_low) / scan_rate
    N_half = int(np.floor(T_half * fs))

    # ---------- Quiet ----------
    N_quiet = int(np.floor(quiet_time * fs))
    E_quiet = np.full(N_quiet, E_init)

    # ---------- 构造标准半周期 ----------
    # endpoint=False 保证拼接连续
    up = np.linspace(E_low, E_high, N_half, endpoint=False)
    down = np.linspace(E_high, E_low, N_half, endpoint=False)

    # ---------- 找到起点在半周期中的位置 ----------
    if direction == 0:
        # 上升方向
        idx = int((E_init - E_low) / (E_high - E_low) * N_half)
        first_half = up[idx:]
        next_is_up = False
    else:
        # 下降方向
        idx = int((E_high - E_init) / (E_high - E_low) * N_half)
        first_half = down[idx:]
        next_is_up = True

    waveform = [first_half]

    # ---------- 拼接剩余 segments ----------
    for i in range(segments - 1):
        if next_is_up:
            waveform.append(up)
        else:
            waveform.append(down)
        next_is_up = not next_is_up

    E_main = np.concatenate(waveform)

    # ---------- 合并 ----------
    E_total = np.concatenate([E_quiet, E_main])

    # ---------- 时间轴 ----------
    t = np.arange(len(E_total)) * dt

    return t, E_total


def save_waveform(filename, t, E):
    """
    保存波形（控制输出精度，去除浮点尾巴）
    """
    data = np.column_stack((t, E))

    np.savetxt(
        filename,
        data,
        delimiter=",",
        header="time,voltage",
        comments="",
        fmt="%.6f"
    )