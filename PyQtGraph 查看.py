import os
import sys
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication


# ====================== CSV路径 ======================
# 方式1：当前目录文件
csv_path = "dpv_result.csv"

# 方式2：绝对路径（取消注释即可）
# csv_path = r"E:\Projects\data\swv_result.csv"


# ====================== 路径处理 ======================
# 如果不是绝对路径，则默认从当前脚本目录查找
if not os.path.isabs(csv_path):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, csv_path)

if not os.path.exists(csv_path):
    raise FileNotFoundError(f"文件不存在：{csv_path}")

print("加载文件：", csv_path)


# ====================== 读取CSV ======================
# 默认格式：
# time,voltage
data = np.loadtxt(
    csv_path,
    delimiter=",",
    skiprows=1
)

t = data[:, 0]
v = data[:, 1]


# ====================== PyQtGraph ======================
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

app = QApplication(sys.argv)

win = pg.GraphicsLayoutWidget(title="Wave Viewer")
win.resize(1200, 700)

plot = win.addPlot()
plot.setLabel('left', 'Voltage (V)')
plot.setLabel('bottom', 'Time (s)')
plot.showGrid(x=True, y=True)
# plot.showGrid(x=False, y=False)

curve = plot.plot(t, v, pen='r')

# 自动显示全图
plot.autoRange()

win.show()

sys.exit(app.exec_())