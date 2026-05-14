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
    CV 波形生成（linspace + 首尾裁切）

    核心思想：
        1）生成 segments+1 个完整半周期
        2）从 E_init 对应位置裁切起点
        3）按“时间长度”裁掉尾部

    参数：
        E_init      初始电位
        E_low       下限
        E_high      上限
        scan_rate   扫描速率
        segments    半周期数（时间定义）
        quiet_time  静默时间
        direction   0=先上升，1=先下降
        fs          采样率

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

    # 总点数（严格按时间定义）
    N_total = segments * N_half

    # ---------- Quiet Time ----------
    N_quiet = int(np.floor(quiet_time * fs))
    E_quiet = np.full(N_quiet, E_init)

    # ---------- 构造标准半周期模板 ----------
    # endpoint=False 避免边界重复
    up = np.linspace(E_low, E_high, N_half, endpoint=False)
    down = np.linspace(E_high, E_low, N_half, endpoint=False)

    # ---------- 构造 segments+1 个半周期 ----------
    waveform = []

    # 初始方向决定第一个半周期类型
    current_is_up = (direction == 0)

    for i in range(segments + 1):
        if current_is_up:
            waveform.append(up)
        else:
            waveform.append(down)

        # 方向交替
        current_is_up = not current_is_up

    # 拼接为一个长序列
    E_full = np.concatenate(waveform)

    # ---------- 起点裁切（对齐 E_init）----------
    # 找到 E_init 在半周期中的位置
    if direction == 0:
        # 上升方向：E_low → E_high
        ratio = (E_init - E_low) / (E_high - E_low)
    else:
        # 下降方向：E_high → E_low
        ratio = (E_high - E_init) / (E_high - E_low)

    # 使用 round 比 int 更准确（减少偏移）
    idx_offset = int(round(ratio * N_half))

    # 从该位置开始裁切
    E_shifted = E_full[idx_offset:]

    # ---------- 尾部裁切（按时间长度）----------
    E_main = E_shifted[:N_total]

    # ---------- 合并 ----------
    E_total = np.concatenate([E_quiet, E_main])

    # ---------- 时间轴 ----------
    t = np.arange(len(E_total)) * dt

    return t, E_total


def save_waveform(filename, t, E):
    """
    保存为 CSV（控制精度，避免浮点尾巴）
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