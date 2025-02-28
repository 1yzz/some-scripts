import cv2
import numpy as np
import os
import time

def extract_figures(image_path, output_dir):
    """
    从白底图中提取人物模型并保存为白底正方形图片，过滤像素面积小于 200 的元素。

    Args:
        image_path: 图片路径。
        output_dir: 输出文件夹路径。
    """
    # 读取图片
    image = cv2.imread(image_path)

    # 将图片转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 使用调整后的阈值二值化（阈值230可根据情况调整）
    _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)

    # 查找轮廓
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 遍历轮廓
    for i, contour in enumerate(contours):
        # 计算轮廓的面积
        area = cv2.contourArea(contour)

        # 设置最小轮廓面积阈值
        min_area = 100*100

        # 过滤像素面积小于 100*100 的元素
        if area < min_area:
            continue

        # 计算轮廓的边界框
        x, y, w, h = cv2.boundingRect(contour)

        # 提取人物模型区域
        figure_image = image[y:y+h, x:x+w]

        # 获取人物模型尺寸
        height, width, _ = figure_image.shape

        # 计算正方形边长
        size = max(height, width)

        # 创建白色背景图片
        new_image = np.zeros((size, size, 3), np.uint8)
        new_image[:] = (255, 255, 255)  # 设置为白色

        # 计算粘贴位置
        x_offset = (size - width) // 2
        y_offset = (size - height) // 2

        # 将人物模型粘贴到白色背景上
        new_image[y_offset:y_offset+height, x_offset:x_offset+width] = figure_image

        # 构建输出路径
        filename = os.path.splitext(os.path.basename(image_path))[0]
        output_path = os.path.join(output_dir, f"{filename}_figure{i}.png")

        # 保存图片
        cv2.imwrite(output_path, new_image)

if __name__ == "__main__":
    input_folder = "../build/input_images/bsp_item"  # 输入文件夹路径

    # 获取当前时间戳
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    # 构建输出文件夹名称，加上时间戳
    output_folder = f"../build/input_images/output_figures_{timestamp}"

    # 创建输出文件夹
    os.makedirs(output_folder, exist_ok=True)

    # 遍历输入文件夹及其子文件夹中的所有图片
    for root, _, files in os.walk(input_folder):
        for filename in files:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(root, filename)
                # 构建相对于输入文件夹的输出路径，保持文件夹结构
                relative_path = os.path.relpath(root, input_folder)
                output_subdirectory = os.path.join(output_folder, relative_path)
                os.makedirs(output_subdirectory, exist_ok=True)
                extract_figures(image_path, output_subdirectory)