import json
import os
from tkinter.dialog import DIALOG_ICON

import pandas as pd
import requests
from openpyxl.reader.excel import load_workbook

REQ_AUTHORIZATION = 'ImY1MTBmM2E0OGI4MDExZWZhNWM1MDI0MmFjMTIwMDAzIg.Zw9ReQ.GjAMjrV9Zyg-QKRLNzinTJvxC8k'
REQ_CONTENT_TYPE = 'application/json;charset=UTF-8'
DIALOG_ID= '734e43928b8711efae200242ac120003' #'8e70f44885e311efb24b0242ac120006'
RESULT_PATH = './result.xlsx'

TEST_LINES = 1000
START_ROW = 0;

# 替换为你的Excel文件路径
def readExcel(file_path='./res/数据.xlsx'):
    df = pd.read_excel(file_path)
    return df.iterrows();


def getRef(cid):
    url = 'http://8.140.49.13:18080/v1/conversation/get'
    params = {"conversation_id": cid}

    # 自定义请求头
    headers = {
        'Authorization': REQ_AUTHORIZATION
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()  # 如果返回的是JSON格式的数据
        try:
            if 'reference' in data['data'] and data['data']['reference']:
                refObjs = [docAggs["doc_aggs"] for docAggs in data['data']['reference']]
                refs = [item['doc_name'] for sub in refObjs for item in sub]
                return refs
        except Exception as e:
            print('ref 获取失败!', data, e)
    else:
        print(f"ref 请求失败: {response}")
        return None;


def genConversationId():
    url = 'http://8.140.49.13:18080/v1/conversation/set'
    payload = {"dialog_id": DIALOG_ID, "name": "你好",
               "message": [{"role": "assistant", "content": "你好"}]}

    # 自定义请求头
    headers = {
        'Content-Type': REQ_CONTENT_TYPE,
        'Authorization': REQ_AUTHORIZATION
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()  # 如果返回的是JSON格式的数据
        if data['data'] and data['data']['id']:
            return data['data']['id']
    else:
        print(f"请求失败: {response}")
        return None;


def req(questionText: str, cId):
    url = 'http://8.140.49.13:18080/v1/conversation/completion'

    payload = {
        "conversation_id": f"{cId}",
        "messages": [
            {"content": "你好！ 我是你的助理，有什么可以帮到你的吗？", "role": "assistant"},
            {
                "content": questionText,
                "role": "user",
                "doc_ids": []
            }
        ]
    }

    # 自定义请求头
    headers = {
        'Content-Type': REQ_CONTENT_TYPE,
        'Authorization': REQ_AUTHORIZATION
    }
    response = requests.post(url, json=payload, headers=headers)
    last_answer = None
    if response.status_code == 200:
        for line in response.iter_lines():
            if line:  # 确保行不为空
                # 处理每一行事件
                line = line.decode('utf-8')[5:]
                try:
                    json_data = json.loads(line)['data']
                    if isinstance(json_data, dict):
                        last_answer = json_data['answer']  # 更新最后一个answer
                except json.JSONDecodeError as e:
                    print("JSON解析错误", e)

    else:
        print(f"请求失败，状态码: {response.status_code}")

    return last_answer


def write2Excel(originRow, rag, refs, ws, dir='./', fileName="result.xlsx"):
    ws.append(
        [originRow.iloc[0], originRow.iloc[1], originRow.iloc[2], originRow.iloc[3], originRow.iloc[4], rag,
         ' '.join([] if refs is None else refs)])





def main():
    rows = readExcel()
    if not os.path.exists(RESULT_PATH):
        df = pd.DataFrame()
        df.to_excel(RESULT_PATH, index=False)

    wb = load_workbook(RESULT_PATH)
    # wb = Workbook()
    ws = wb.active

    df = pd.read_excel(RESULT_PATH)

    # 检查是否有标题
    if df.empty or df.columns.empty:
        columns = ['疾病', '类型', '描述', '病人', '医生', 'RAG回复结果', '参考书籍']
        ws.append(columns)

    ct = 0;

    for index, row in rows:
        cId = genConversationId()

        if index >= START_ROW and ct < TEST_LINES:
            ct += 1
            question = row.iloc[3]
            ans = req(question, cId)
            refs = getRef(cId)
            print(f'############# {index} ###################')
            print(question)
            print('---------------------------')
            print(ans)
            print('---------------------------')
            print(row.iloc[4])
            print('---------------------------')
            print(refs)
            print('################################')

            write2Excel(row, ans, refs, ws)
            wb.save(RESULT_PATH)


if __name__ == '__main__':
    main()
