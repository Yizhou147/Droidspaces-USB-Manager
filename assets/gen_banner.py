#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1920, 1080
bg = Image.new('RGB', (W, H), (255, 255, 255))
draw = ImageDraw.Draw(bg)

# 中文字体
zh_font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
zh_bold_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
en_bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

try:
    title_font = ImageFont.truetype(zh_bold_path, 72)
    sub_font = ImageFont.truetype(zh_font_path, 36)
    small_font = ImageFont.truetype(zh_font_path, 28)
    tag_font = ImageFont.truetype(zh_font_path, 26)
except:
    title_font = ImageFont.truetype(en_bold_path, 72)
    sub_font = ImageFont.truetype(en_bold_path, 36)
    small_font = ImageFont.truetype(en_bold_path, 28)
    tag_font = small_font

# 加载截图 - 缩小
screenshot_path = "/home/xieyizhou/Documents/Droidspaces usb直通/usb-manager/Screenshot_2026-07-18-10-37-20-546_com.anland.consumer-edit.jpg"
app_window = Image.open(screenshot_path).convert('RGBA')

target_h = 600
ratio = target_h / app_window.height
target_w = int(app_window.width * ratio)
app_window = app_window.resize((target_w, target_h), Image.LANCZOS)

# 布局：左文右图，整体居中
gap = 80
total_w = 600 + gap + target_w
start_x = (W - total_w) // 2
img_x = start_x + 600 + gap
img_y = (H - target_h) // 2

# 左侧文字
text_x = start_x
title_y = img_y + 50

draw.text((text_x, title_y), "Droidspaces", fill='#333333', font=title_font)
draw.text((text_x, title_y + 90), "USB 管理器", fill='#4A90D9', font=title_font)
draw.text((text_x, title_y + 200), "专为 Droidspaces 设计", fill='#666666', font=sub_font)
draw.text((text_x, title_y + 250), "的 USB 设备管理工具", fill='#666666', font=sub_font)

# 功能标签
tags = ['自动检测', '自动挂载', 'ADB 支持', '一键弹出']
tag_y = title_y + 340
tag_x = text_x
for tag in tags:
    bbox = draw.textbbox((0, 0), tag, font=tag_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tag_w = tw + 30
    tag_h = 44
    tx = tag_x + (tag_w - tw) // 2
    ty = tag_y + (tag_h - th) // 2 - bbox[1]
    draw.rounded_rectangle([tag_x, tag_y, tag_x + tag_w, tag_y + tag_h], radius=12, fill='#E8F0FE', outline='#4A90D9')
    draw.text((tx, ty), tag, fill='#4A90D9', font=tag_font)
    tag_x += tag_w + 16

# GitHub
draw.text((text_x, tag_y + 80), "github.com/Yizhou147/Droidspaces-USB-Manager", fill='#999999', font=small_font)

# 贴截图
bg.paste(app_window, (img_x, img_y), app_window)

out = "/home/xieyizhou/Documents/Droidspaces usb直通/usb-manager/assets/banner.png"
bg.save(out, quality=95)
print(f"题图已保存: {out}")
