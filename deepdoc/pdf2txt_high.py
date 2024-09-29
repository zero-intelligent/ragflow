from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
import random
from pathlib import Path
import sys
import time
import glob
import traceback
import numpy as np
from paddleocr import PaddleOCR
import fitz

    
# 初始化 OCR
ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=True)

def extract_images_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    images = []

    for page_idx,page in enumerate(doc):
        # 提取当前页面的图像列表
        
        page_images = page.get_images(full=True)
        text_content = page.get_text()
        for img_index, img in enumerate(page_images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            
            image_bytes = base_image["image"]
            images.append(image_bytes)

    doc.close()
    return images

def ocr_pdf_file(input_path,index=0):
    locker_file = Path(f"{input_path}.lock")
    output_txt_file = Path(f"{input_path}.txt")
    error_file = Path(f"{input_path}.err")
    if locker_file.exists() or output_txt_file.exists() or error_file.exists():
        return False
    try:
        locker_file.touch()
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {input_path},{os.path.getsize(input_path)/1024/1024.0:.2f}M")
        start = time.time()
        images = extract_images_from_pdf(input_path)
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {input_path} get {len(images)} pdf_pages {time.time()-start:.2f}s")
        if not images:
            return False
        
        # 执行 OCR 识别
        ocr_results = []
        
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(ocr.ocr, np.array(img)) for img in images]
            for future in futures:
                result = future.result()
                if result:
                    for r in result:
                        ocr_results.append(r[1][0])
                    
        # for img in images:
        #     results = ocr.ocr(np.array(img), cls=True)
        #     for result in results:
        #         if not result:
        #             continue
        #         for r in result:
        #             ocr_results.append(r[1][0])
        
        with open(output_txt_file, "a") as f:
            f.write('\n'.join(ocr_results))
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {output_txt_file} {index}/{total_cnt} ocr finished {time.time()-start:.2f}s")
        return True

    except Exception as ex:
        with open(error_file, 'w', encoding='utf-8') as file:
            file.write(f"Exception: {ex}\n")
            file.write(f"Traceback:\n{traceback.format_exc()}\n")
        
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Failed to ocr_pdf_file {input_path}: {ex}")
        return False
    finally:
        locker_file.unlink(missing_ok=True)
    
    
total_cnt = 0 

def process_directory(current_dir):
    # 递归搜索所有PDF文件
    pdf_files = glob.glob(f"{current_dir}/**/*.pdf", recursive=True)
    pdf_files += glob.glob(f"{current_dir}/**/*.PDF", recursive=True)
    valid_files = [f for f in pdf_files if not Path(f+".txt").exists()]
    
    #打乱顺序，确保多线程不冲突
    random.shuffle(valid_files)
    global total_cnt
    total_cnt = len(valid_files)
    for i,f in enumerate(valid_files):
        ocr_pdf_file(f,i)
                
def main():
    # 从输入目录开始处理
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "."
    if Path(pdf_path).is_dir():
        process_directory(pdf_path)
    elif  Path(pdf_path).is_file():
        ocr_pdf_file(pdf_path)
    else:
        print(f"{pdf_path} is not a file or directory.")
        
    print("All files processed.")





if __name__ == "__main__":

    main()

