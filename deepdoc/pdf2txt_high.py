import io
import cv2
import os
import random
from pathlib import Path
import sys
import time
import glob
import traceback
import numpy as np
import statistics
from concurrent.futures import ThreadPoolExecutor
import fitz
from PIL import Image
from loguru import logger as log

log.add(sys.stdout, 
           format="{time} {level} {message}", 
           filter=lambda record: record["level"].no < 40,  # 输出低于 ERROR 级别的日志到控制台
           colorize=True)

# 文件输出配置
log.add("logs/pdf2txt.log", 
           format="{time} {level} {message}",
           filter=lambda record: record["level"].no >= 30)  # 输出 ERROR 级别及以上的日志到文件

def estimate_char_size(vertical_projection, tolerance=5):
    """估计字符宽度和字符间距，返回平均字符宽度和字符间距的元组"""
    character_sizes = []
    gaps = []
    current_length = 0
    current_gap = 0
    in_character = False

    for val in vertical_projection:
        if val < 255:  # 字符区域
            if current_gap > 0:  # 结束了一个间隔
                gaps.append(current_gap)
                current_gap = 0
            current_length += 1
            in_character = True
        else:  # 背景区域
            if in_character:
                if current_length > 0:
                    character_sizes.append(current_length)
                    current_length = 0
                in_character = False
            current_gap += 1  # 计算间隔

    # 处理最后一个字符和间隔
    if current_length > 0:
        character_sizes.append(current_length)
    if current_gap > 0:
        gaps.append(current_gap)

    mean_char_size = np.mean(character_sizes) if character_sizes else 0
    std_char_size = np.std(character_sizes) if character_sizes else 0
    mean_gap = np.mean(gaps) if gaps else 0
    std_gap = np.std(gaps) if gaps else 0

    return (mean_char_size, std_char_size, mean_gap, std_gap)

def evaluate_text_image_char_size(image: np.array):
    """处理多行文本的图像，计算行间距、字符宽度和字符间距"""

    # 水平投影法找到行边界
    horizontal_projection = np.sum(image, axis=1) / image.shape[1]
    line_boundaries = []
    start = None
    tolerance = 5

    for i, val in enumerate(horizontal_projection):
        if val < 255:  # 行内有字符
            if start is None:
                start = i
        else:  # 行间有空白
            if start is not None:
                line_boundaries.append((start, i))
                start = None

    # 处理最后一行
    if start is not None:
        line_boundaries.append((start, len(horizontal_projection)))

    # 计算行间距、字符宽度和字符间距
    line_spacing = []
    char_sizes_info = []

    for i in range(len(line_boundaries)):
        top, bottom = line_boundaries[i]
        line_image = image[top:bottom, :]
        vertical_projection = np.sum(line_image, axis=0) / line_image.shape[0]
        
        # 计算行内字符宽度和字符间距
        char_size_info = estimate_char_size(vertical_projection)
        char_sizes_info.append(char_size_info)

        # 计算行间距
        if i > 0:
            prev_bottom = line_boundaries[i-1][1]
            spacing = top - prev_bottom
            line_spacing.append(spacing)

    # 返回结果
    return {
        "line_spacing": line_spacing,
        "char_sizes_info": char_sizes_info
    }

def segment_image_by_columns(image: np.array,page_index:int = 0):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # cv2.imwrite(f'page_{page_index}_0_gray.jpg', gray)
    
    binary =  cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY, 11, 2)
    # cv2.imwrite(f'page_{page_index}_1_binary.jpg', binary)

    # 水平投影法找到行边界
    horizontal_projection = np.sum(binary, axis=1) / binary.shape[1]
    row_boundaries = []
    start = None
    preIdx = None
    tolerance = 2
    min_height_gap = 50  # 最小间隔
    min_inter_height = 20

    for i, val in enumerate(horizontal_projection):
        if val < 255 - tolerance and start is None:
            start = i
        elif val >= 255 -tolerance and start is not None:
            height = i - start
            if height > min_height_gap \
                and preIdx is not None and i - preIdx > min_inter_height:
                row_boundaries.append((start, i))
                start = None
        elif val < 255 - tolerance and start is not None:
            preIdx = i
                
    if not row_boundaries:
        row_boundaries = [(0,len(horizontal_projection))]
        
    segment_results = []
    # 处理每一行
    column_boundaries_per_row = []
    for top, bottom in row_boundaries:
        row_image = binary[top:bottom, :]
        vertical_projection = np.sum(row_image, axis=0) / row_image.shape[0]
        
        # 估计字符宽度
        char_info = evaluate_text_image_char_size(row_image)
        linespace = statistics.median(char_info['line_spacing']) if char_info['line_spacing'] else 20
        mean_char_size = statistics.median([mean_char_size for mean_char_size, std_char_size, mean_char_gap, std_char_gap in char_info['char_sizes_info']]) if char_info['char_sizes_info'] else 14
        std_char_size = statistics.median([std_char_size for mean_char_size, std_char_size, mean_char_gap, std_char_gap in char_info['char_sizes_info']]) if char_info['char_sizes_info'] else 14
        mean_char_gap = statistics.median([mean_char_gap for mean_char_size, std_char_size, mean_char_gap, std_char_gap in char_info['char_sizes_info']]) if char_info['char_sizes_info'] else 14
        std_char_gap = statistics.median([std_char_gap for mean_char_size, std_char_size, mean_char_gap, std_char_gap in char_info['char_sizes_info']]) if char_info['char_sizes_info'] else 14
        
        min_char_width = 2 * int(mean_char_size + 2 * std_char_size)  # 最小区间宽度
        min_inter_width = mean_char_gap  # 最小区间宽度

        column_boundaries = []
        start = None

        for i, val in enumerate(vertical_projection):
            if val < 255 - tolerance and start is None:
                start = i
            elif val >= 255 - tolerance and start is not None:
                width = i - start
                if width > min_char_width \
                    and preIdx is not None \
                    and i - preIdx > min_inter_width:
                    column_boundaries.append((start, i))
                    start = None
            elif val < 255 - tolerance and start is not None:
                preIdx = i
                
        if not column_boundaries:
            column_boundaries = [(0,len(vertical_projection))]

        column_boundaries_per_row.append(column_boundaries)

        # # 绘制边界框
        # for left, right in column_boundaries:
        #     cv2.rectangle(image, (left, top), (right, bottom), (255, 0, 0), 2)  # 画边框
            
        # 分割每一栏
        for i, (left, right) in enumerate(column_boundaries):
            cropped_image = image[top:bottom, left:right]
            segment_results.append(cropped_image)
            # cv2.imwrite(f'page_{page_index}_row_{len(column_boundaries_per_row)-1}_column_{i}.jpg', cropped_image)

    # cv2.imshow('Original Image with Boundaries', image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    
    return segment_results


def pdf_file_analysis(pdf_path):
    doc = fitz.open(pdf_path)
    page_cnt = len(doc)
    txt_page_cnt = len([p for p in doc if p.get_text()])
    
    log.info(f"{pdf_path} is_pure_image_pdf {txt_page_cnt == 0}, txt rate:{txt_page_cnt/page_cnt * 100.0:.2f}%")
    doc.close()
    return txt_page_cnt == 0


def extract_txt_images_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)

    for page_idx, page in enumerate(doc):
        # 提取当前页面的图像列表

        page_images = page.get_images(full=True)
        text_content = page.get_text()
        images = []
        for img_index, img in enumerate(page_images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))

            images.append(image)
        yield (text_content, images)
    doc.close()


# 初始化 OCR
ocr = None

def ocr_pdf_file(input_path, index=0):
    locker_file = Path(f"{input_path}.lock")
    output_txt_file = Path(f"{input_path}.txt")
    error_file = Path(f"{input_path}.err")
    if locker_file.exists() or output_txt_file.exists() or error_file.exists():
        log.warning(f"{input_path}.lock or .txt or .err exists, return")
        return False
    try:
        locker_file.touch()
        log.info(f"{input_path},{os.path.getsize(input_path)/1024/1024.0:.2f}M")
        start = time.time()
        txt_images = extract_txt_images_from_pdf(input_path)

        # 执行 OCR 识别
        ocr_results = []
        
        for page_index,(txt,images) in enumerate(txt_images):
            if txt:
                ocr_results.append(txt)
            for image in images:
                image_blocks = segment_image_by_columns(np.array(image),page_index)
                for block_idx,img in enumerate(image_blocks):
                    results = ocr.ocr(np.array(img), cls=True)
                    box_texts = [box_text[1][0] for line in results if line for box_text in line]
                    join_texts = '\n'.join(box_texts)
                    ocr_results.append(join_texts)
                    log.info(f"{output_txt_file} {index}/{total_cnt},page:{page_index} block:{block_idx},ocr text:{join_texts}")
                        
        if ocr_results:
            with open(output_txt_file, "a") as f:
                f.write('\n'.join(ocr_results))
        
        log.info(f"{output_txt_file} {index}/{total_cnt} {page_index} pages ocr finished {time.time()-start:.2f}s")
        return True

    except Exception as ex:
        with open(error_file, 'w', encoding='utf-8') as file:
            log.error(f"Traceback:\n{traceback.format_exc()}\n")
            file.write(f"Exception: {ex}\n")
            file.write(f"Traceback:\n{traceback.format_exc()}\n")

        log.info(f"Failed to ocr_pdf_file {input_path}: {ex}")
        return False
    finally:
        locker_file.unlink(missing_ok=True)


total_cnt = 0


def process_directory(current_dir):
    # 递归搜索所有PDF文件
    pdf_files = glob.glob(f"{current_dir}/**/*.pdf", recursive=True)
    pdf_files += glob.glob(f"{current_dir}/**/*.PDF", recursive=True)
    valid_files = [f for f in pdf_files if not Path(f+".txt").exists()]

    # 打乱顺序，确保多线程不冲突
    random.shuffle(valid_files)
    global total_cnt
    total_cnt = len(valid_files)
    for i, f in enumerate(valid_files):
        ocr_pdf_file(f, i)


def main():
    from paddleocr import PaddleOCR
    global ocr
    
    use_gpu = "CUDA_VISIBLE_DEVICES" in os.environ
    ocr = PaddleOCR(use_angle_cls=True, lang='ch',use_gpu=use_gpu)

    # 从输入目录开始处理
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "."
    if Path(pdf_path).is_dir():
        process_directory(pdf_path)
    elif Path(pdf_path).is_file():
        ocr_pdf_file(pdf_path)
    else:
        log.info(f"{pdf_path} is not a file or directory.")

    log.info("All files processed.")


if __name__ == "__main__":
    main()