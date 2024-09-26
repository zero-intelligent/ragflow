from datetime import datetime
import os
from os import cpu_count
from pathlib import Path
import sys
import time
import glob
import numpy as np
from paddleocr import PaddleOCR
import pdfplumber
from multiprocessing import Pool




def process_page(page):
    try:
        return page.to_image(resolution=150).annotated
    except Exception as e:
        print(f"Failed to process page: {e}")
        return None

def get_pdf_pages(pdf_file):
    pdf = pdfplumber.open(pdf_file)
    return [process_page(p) for p in pdf.pages]

def ocr_pdf_file(input_path,output_txt_file,index):
    # 初始化 OCR
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')  # 根据需要选择语言

    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {input_path},{os.path.getsize(input_path)/1024/1024.0:.2f}M")
    start = time.time()
    images = get_pdf_pages(input_path)
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {input_path} get_pdf_pages {time.time()-start:.2f}s")
    
    # 执行 OCR 识别
    ocr_results = []
    for img in images:
        results = ocr.ocr(np.array(img), cls=True)
        for result in results:
            for r in result:
                ocr_results.append(r[1][0])    
                
    with open(output_txt_file, "a") as f:
        f.write('\n'.join(ocr_results))
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {output_txt_file} {index}/{total_cnt} ocr finished {time.time()-start:.2f}s")
    return True

total_cnt = 0 

def process_directory(current_dir):
    # 递归搜索所有PDF文件
    pdf_files = glob.glob(f"{current_dir}/**/*.pdf", recursive=True)
    pdf_files += glob.glob(f"{current_dir}/**/*.PDF", recursive=True)
    valid_files = [f for f in pdf_files if not Path(f+".txt").exists()]
    global total_cnt
    total_cnt = len(valid_files)
    proc_num = min(16,cpu_count() * 2)
    with Pool(processes=proc_num) as pool:  # 根据需要调整进程数
        results = pool.starmap(ocr_pdf_file, [(f,f+".txt",i) for i,f in enumerate(valid_files)])
                
def main():
    # 从输入目录开始处理
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "."
    process_directory(pdf_path)
    print("All files processed.")

if __name__ == "__main__":
    
    main()

