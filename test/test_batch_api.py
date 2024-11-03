
import pytest
from rag.app import knowledge_graph

def test_qwen_batch_api(tenant_id='7d19a176807611efb0f80242ac120006',
                        kb_id='fb7c4312973b11ef88ed0242ac120006',
                        parser_config = {'entity_types': ['pet-species (宠物种类)', 'breed (品种)', ' age (年龄)', ' gender (性别) ', 'weight (体重)', ' temperature (体温)', ' disease (疾病)', ' symptom (症状) ', 'medication (药物)', ' treatment-method (治疗方法)', ' diagnostic-test (诊断测试) ', 'sign (体征)', 'organ-or-system (器官或系统) ', 'vaccine (疫苗)', ' animal-behavior (动物行为) ', 'allergen (过敏源) ', 'prognosis (预后)', ' environmental-factors (环境因素)', ' nutrition (营养) ', 'food (食物)', ' water-intake (饮水情况) ', 'lifestyle (生活习惯) ', 'allergic-reaction (过敏反应)', ' living-environment (居住环境)', ' parasite (寄生虫)', ' restraint-method (保定法) ', 'examination-method (检查方法)', ' epidemiology (流行病学) ', 'lesion (病变)', 'prevention(预防方法)'], 
                                         'chunk_token_num': 8192, 'delimiter': '\\\\n!?;。；！？'},
                        filename = '/home/admin/python_projects/MedicalGPT/data/pretrain/pet_books/宠医临床书籍/【07】（国家重大出版工程项目）《动物营养学（第六版）》.pdf.txt'):
        
    with open(filename, 'rb') as file:
        binary = file.read()

    def callback(*args,**kwargs):
        pass
    knowledge_graph.chunk(filename=filename, binary=binary, from_page=0,
                            to_page=1000, lang='Chinese', callback=callback,
                            kb_id=kb_id, 
                            parser_config=parser_config, 
                            tenant_id=tenant_id)
        


