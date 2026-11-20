# -*- coding: utf-8 -*-
"""生成视频封面：竖屏 1080x1920（抖音）+ 横屏 1146x717（B站）"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
FB = "C:/Windows/Fonts/msyhbd.ttc"   # 微软雅黑 Bold
FR = "C:/Windows/Fonts/msyh.ttc"     # 微软雅黑 Regular


def font(path, size):
    return ImageFont.truetype(path, size)


def gradient(w, h, c1, c2):
    img = Image.new("RGB", (1, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.point((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    return img.resize((w, h))


def rounded(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


# ───────── 竖屏 1080×1920 ─────────
W, H = 1080, 1920
img = gradient(W, H, (11, 22, 40), (27, 79, 138))
d = ImageDraw.Draw(img, "RGBA")

# 顶部标签
rounded(d, (72, 120, 400, 196), 38, (255, 255, 255, 28))
d.text((100, 138), "秋招实战", font=font(FB, 40), fill=(160, 200, 245))

# 主标题（两行）
f_main = font(FB, 132)
d.text((72, 250), "招聘会", font=f_main, fill=(255, 255, 255))
d.text((72, 410), "别瞎逛了", font=f_main, fill=(255, 190, 80))

# 分隔线
d.rounded_rectangle((72, 600, 320, 612), radius=6, fill=(255, 190, 80))

# 数据三行
f_num = font(FB, 96)
f_lab = font(FR, 42)
items = [("89", "家企业", (255, 255, 255)), ("375", "个岗位", (255, 255, 255)),
         ("100%", "JD 全文", (120, 220, 180))]
y = 700
for num, lab, col in items:
    d.text((72, y), num, font=f_num, fill=col)
    wnum = d.textlength(num, font=f_num)
    d.text((72 + wnum + 24, y + 40), lab, font=f_lab, fill=(190, 205, 220))
    y += 170

# 右下角：勾选卡片示意
bx, by = 620, 1080
rounded(d, (bx, by, bx + 380, by + 300), 34, (255, 255, 255, 235))
rounded(d, (bx + 34, by + 40, bx + 94, by + 100), 14, (14, 124, 102))
# 勾
d.line([(bx + 48, by + 70), (bx + 62, by + 86), (bx + 82, by + 54)],
       fill=(255, 255, 255), width=9, joint="curve")
d.text((bx + 116, by + 44), "已投递", font=font(FB, 44), fill=(15, 26, 43))
for i, w in enumerate([280, 220, 250]):
    d.rounded_rectangle((bx + 34, by + 130 + i * 52, bx + 34 + w, by + 152 + i * 52),
                        radius=11, fill=(226, 233, 242))

# 底部信息
f_bot = font(FB, 48)
d.text((72, H - 400), "3 个脚本搞定", font=f_bot, fill=(255, 255, 255))
d.text((72, H - 330), "附开源代码 · 可复现", font=font(FR, 40), fill=(150, 175, 200))

# 左下角装饰点
for i in range(3):
    d.ellipse((72 + i * 34, H - 240, 92 + i * 34, H - 220),
              fill=(255, 190, 80) if i == 0 else (70, 100, 140))

img.save(os.path.join(OUT, "封面-竖屏-1080x1920.png"), quality=95)
print("竖屏封面 OK")

# ───────── 横屏 1146×717（B站）─────────
W2, H2 = 1146, 717
img2 = gradient(W2, H2, (11, 22, 40), (24, 68, 120))
d2 = ImageDraw.Draw(img2, "RGBA")

d2.text((60, 74), "秋招 · 招聘会信息筛选", font=font(FB, 30), fill=(140, 178, 220))
d2.text((60, 130), "我用 3 个脚本", font=font(FB, 68), fill=(255, 255, 255))
d2.text((60, 212), "扒完了整场招聘会", font=font(FB, 68), fill=(255, 190, 80))
d2.rounded_rectangle((60, 308, 210, 316), radius=4, fill=(255, 190, 80))
d2.text((60, 340), "89 家企业 · 375 个岗位", font=font(FR, 34), fill=(178, 196, 214))
d2.text((60, 386), "全量 JD · 简历自动匹配", font=font(FR, 34), fill=(178, 196, 214))
d2.text((60, 620), "github.com/myzhgjb/jobfair-toolkit", font=font(FR, 26), fill=(115, 142, 180))

# 右侧：清单卡片
CX = 690
for i, (yy, ww, al) in enumerate([(96, 330, 42), (196, 300, 96)]):
    rounded(d2, (CX + (370 - ww), yy, CX + 370, yy + 76), 14, (255, 255, 255, al))

# 主卡：白底 + 勾选 + 文字条
rounded(d2, (CX, 300, CX + 370, 560), 20, (255, 255, 255, 245))
rounded(d2, (CX + 26, 328, CX + 76, 378), 10, (14, 124, 102))
d2.line([(CX + 37, 353), (CX + 48, 366), (CX + 66, 340)], fill=(255, 255, 255), width=7, joint="curve")
d2.text((CX + 92, 332), "已投递 7 / 89", font=font(FB, 30), fill=(15, 26, 43))
for i, w in enumerate([300, 250, 285, 210]):
    d2.rounded_rectangle((CX + 26, 408 + i * 34, CX + 26 + w, 428 + i * 34),
                         radius=9, fill=(226, 233, 242))
d2.text((CX + 26, 512), "★ 对口岗　　备注已记录", font=font(FR, 22), fill=(120, 140, 165))

img2.save(os.path.join(OUT, "封面-横屏-1146x717.png"), quality=95)
print("横屏封面 OK")
