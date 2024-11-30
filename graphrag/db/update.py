

from concurrent.futures import ThreadPoolExecutor
from functools import cache
from itertools import chain
import pandas as pd
from api.db import LLMType
from api.db.services.llm_service import LLMBundle
from graphrag.db import driver, execute_update,query
from loguru import logger as log

from graphrag.utils import escape, get_filepaths_from_source_id


#只保留数组中每行的第一个实体，其他实体向第一个实体对齐
similar_entity_types = [
    ["DISEASE(疾病)","DISEASE (疾病)","疾病","|>疾病","TYPE-OF-DISEASE(疾病类型)","TYPE-OF-DISEASE (疾病类型)","RELATED-DISEASE(相关疾病)","DISORDER(疾病)","| 疾病","DISEASE"],
    ["LESION(病变)","LESION (病变)"],
    ["SIGN(体征)","SIGN (体征)","体征"],
    ["MEDICATION(药物)","MEDICATION (药物)","药物","DRUG(药物)","DRUG-CLASS(药物类别)","MEDICINE(药物)","MEDICATION-CLASS(药物类别)","DRUG"],
    ["DIAGNOSTIC-TEST (诊断测试)","DIAGNOSTIC-TEST (诊断测试)","诊断测试","DIAGNOSIS-TEST(诊断测试)","|>诊断测试","DIAGNOSIS-TEST (诊断测试)"],
    ["PARASITE(寄生虫)","PARASITE (寄生虫)","寄生虫"],
    ["ANIMAL-BEHAVIOR(动物行为)","ANIMAL-BEHAVIOR (动物行为)","动物行为","BEHAVIOR(动物行为)"],
    ["PREVENTION(预防方法)","PREVENTION (预防方法)","PREVENTIVE(预防方法)","预防措施"],
    ["BREED(品种)","BREED (品种)","宠物品种","|>宠物品种","PET-SPECIES(宠物种类)","SPECIES(物种)","DOG(犬)","犬","犬种","PET-SPECIES (宠物种类)","宠物种类"],
    ["AGE(年龄)","AGE (年龄)","宠物年龄"],
    ["LIVING-ENVIRONMENT(居住环境)","LIVING-ENVIRONMENT (居住环境)","居住环境"],
    ["PROGNOSIS(预后)","PROGNOSIS (预后)","预后","PROGNOSTIC-FACTOR(预后因素)"],
    ["TOXIN(毒素)","TOXIN (毒素)","TOXICANT(毒素)","MYCOTOXIN(真菌毒素)","毒素"],
    ["EPIDEMIOLOGY(流行病学)","EPIDEMIOLOGY (流行病学)"],
    ["RESTRAINT-METHOD(保定法)","RESTRAINT-METHOD (保定法)"],
    ["EXAMINATION-METHOD(检查方法)","EXAMINATION-METHOD (检查方法)"],
    ["COMPLICATION(并发症)","COMPLICATION (并发症)","COMPLICATIONS(并发症)","并发症"],
    ["NUTRITION(营养)","NUTRITION (营养)","NUTRIENT(营养)","NUTRIENT(营养素)","营养","NUTRIENT (营养)","NUTRIENT (营养素)","NUTRIENT(营养物质)","NUTRIENT(营养成分)"],
    ["ENVIRONMENTAL-FACTOR(环境因素)","ENVIRONMENTAL-FACTORS(环境因素)","ENVIRONMENTAL-FACTORS (环境因素)","环境因素"],
    ["FOOD(食物)","FOOD (食物)","食物"],
    ["VIRUS(病毒)","病毒","VIRUS (病毒)"],
    ["VIRUS-CHARACTERISTIC(病毒特性)","VIRUS-CHARACTERISTIC (病毒特性)"],
    ["BACTERIA(细菌)","BACTERIA (细菌)","细菌"],
    ["ORGAN-OR-SYSTEM(器官或系统)","ORGAN-OR-SYSTEM (器官或系统)","器官","ORGAN-OR-SYSTEM (器官-OR-系统)","ORGAN-OR-SYSTEM (器官或 SYSTEM)","ORGAN-OR-SYSTEM(器官-OR-系统)","ORGAN","ORGAN-FUNCTION(器官功能)","TISSUE(组织)","TISSUE (组织)"],
    ["TREATMENT-METHOD(治疗方法)","TREATMENT-METHOD (治疗方法)","治疗方法","|>治疗方法","TREATMENT METHOD"],
    ["SYMPTOM(症状)","SYMPTOM (症状)","症状","|>|>症状","|>症状","SYMPTOM(症状)|","SYMPTOM"],
    ["PROTEIN(蛋白质)","PROTEIN(蛋白)","PROTEIN (蛋白质)","蛋白质","PROTEIN(蛋白)","PROTEIN-SOURCE(蛋白质来源)","蛋白","PROTEIN (蛋白)"],
    ["CAUSE(病因)","CAUSE (病因)","病因","ETIOLOGY(病因)","ETIOLOGIC-FACTOR(病因)","ETIOLOGIES(病因)","ETIOLOGIC-FACTOR (致病因素)","ETIOLOGIC-FACTOR(病因因素)","CAUSAL-FACTOR(病因)","CAUSAL-FACTOR (病因)","ETIOLOGY-AND-PATHOGENESIS(病因及发病机制)","ETIOLOGY (病因)","CAUSATIVE-FACTOR(致病因素)","CAUSE-OF-DISEASE(致病因素)","CAUSE(原因)","CAUSE (原因)"],
    ["VACCINE(疫苗)","VACCINE (疫苗)","疫苗","VACCINATION(疫苗接种)"],
    ["TOXIN(毒素)","毒素","TOXIN (毒素)","TOXICANT(毒素)","MYCOTOXIN(真菌毒素)"],
    ["SURGERY(手术方法)","SURGERY (手术方法)","SURGICAL-PROCEDURE(手术方法)","SURGERY-METHOD (手术方法)","手术方法"],
    ["EQUIPMENT(设备)","EQUIPMENT (设备)","MEDICAL-DEVICE(医疗设备)","MEDICAL-DEVICE (医疗设备)","设备","DEVICE(设备)","EQUIPMENT-SETTING(设备设置)","EQUIPMENT(器材设备)"],
    ["ALLERGEN(过敏源)","ALLERGEN (过敏源)","过敏源"],
    ["ALLERGIC-REACTION(过敏反应)","ALLERGIC-REACTION (过敏反应)","ADVERSE-REACTION (过敏反应)","过敏反应"],
    ["LIFESTYLE(生活习惯)","LIFESTYLE (生活习惯)","生活习惯"],
    ["SIDE-EFFECT(副作用)","SIDE-EFFECT (副作用)","ADVERSE-EFFECT(副作用)","TOXIC-EFFECT(毒副作用)"],
    ["PROCEDURE(程序)","PROCEDURE (程序)"],
    ["SURGICAL-PROCEDURE(手术程序)","SURGICAL-PROCEDURE (手术程序)","SURGERY-PROCEDURE(手术程序)","PROCEDURE(手术程序)"],
    ["PHYSIOLOGICAL-PROCESS(生理过程)","PHYSIOLOGICAL-PROCESS (生理过程)","生理过程","PHYSIOLOGY(生理过程)","PATHOPHYSIOLOGY (病理生理过程)"],
    ["PATHOLOGY(病理过程)","病理过程","PATHOLOGICAL-PROCESS(病理过程)","|>病理过程","PATHOLOGICAL-PROCESS (病理过程)","|>病理过程"],
    ["BIOLOGICAL-PROCESS(生物过程)","BIOLOGICAL-PROCESS (生物过程)"],
    ["METABOLISM(代谢过程)","METABOLIC-PROCESS (代谢过程)"],
    ["VITAMIN(维生素)","VITAMIN (维生素)"],
    ["ANTIBODY(抗体)","ANTIBODY (抗体)","AUTOANTIBODY(自身抗体)"],
    ["TUMOR(肿瘤)","肿瘤","TUMOR (肿瘤)","NEOPLASIA(肿瘤)","NEOPLASM(肿瘤)","TUMOUR-OF-MESENCHYMAL-TISSUE(间叶组织的肿瘤)","NEOPLASTIC-DISEASE(肿瘤性疾病)","NEOPLASIA (肿瘤)","TUMOUR(肿瘤)"],
    ["WATER-INTAKE(饮水情况)","WATER-INTAKE (饮水情况)","饮水情况"],
    ["HORMONE(激素)","HORMONE (激素)","激素","|激素"],
    ["DRUG-INTERACTION(药物相互作用)","DRUG-INTERACTIONS(药物相互作用)","DRUG-INTERACTION (药物相互作用)"],
    ["SUTURE-MATERIAL(缝合材料)","SUTURE-MATERIAL (缝合材料)"],
    ["TRAINING-METHOD(训练方法)","TRAINING-METHOD (训练方法)","TRAINING-METHODS (训练方法)"],
    ["GENDER(性别)","GENDER (性别)","宠物性别"],
    ["INJURY(损伤)","INJURY (损伤)","损伤"],
    ["ADVERSE-REACTION(不良反应)","ADVERSE-EFFECT(不良反应)","ADVERSE-REACTIONS(不良反应)","ADVERSE-REACTION (不良反应)"],
    ["MEDICAL-DEVICE(医疗器械)","SURGICAL-INSTRUMENT(手术器械)","SURGICAL-DEVICE(手术器械)","SURGICAL-INSTRUMENTS(手术器械)","INSTRUMENTATION(器械)","SURGICAL-INSTRUMENTS(外科器械)","INSTRUMENT(器械)","INSTRUMENT (器械)","MEDICAL-DEVICE (医疗器械)","SURGICAL-INSTRUMENTS(外科手术器械)","SURGICAL-INSTRUMENTS (手术器械)","SURGICAL-INSTRUMENT (手术器械)","INSTRUMENT(仪器)","INSTRUMENT (仪器)"],
    ["METABOLITE(代谢物)","METABOLITE (代谢物)"],
    ["PATHOGEN(病原)","|>病原体","PATHOGEN(病原体)","病原体","PATHOGEN (病原体)","病原"],
    ["RISK-FACTOR(风险因素)","RISK-FACTOR (风险因素)"],
    ["PLANT-MEDICINAL(药用植物)","PLANT(植物)"],
    ["WEIGHT(体重)","WEIGHT (体重)"],
    ["ADMINISTRATION-ROUTE(给药途径)","ADMINISTRATION-METHOD(给药途径)","ROUTE-OF-ADMINISTRATION(给药途径)","ADMINISTRATION-ROUTE (给药途径)"],
    ["ACUPOINT(穴位)","ACUPUNCTURE-POINT(穴位)","ACUPUNCTURE-POINTS (针灸穴位)","ACUPUNCTURE-POINT (针灸穴位)","ACUPUNCTURE-POINT (穴位)","ACUPUNCTURE-POINT(针灸穴位)","ACUPUNCTURE-POINTS(针灸穴位)"],
    ["COMPOUND(化合物)","COMPOUND (化合物)","CHEMICAL-COMPOUND(化学化合物)","CHEMICAL-COMPOUND (化学化合物)"],
    ["ENZYME(酶)","ENZYME (酶)","酶"],
    ["CELL-TYPE(细胞类型)","CELL-TYPE (细胞类型)","细胞类型"],
    ["IMMUNE-RESPONSE(免疫反应)","IMMUNE-RESPONSE (免疫反应)"],
    ["DISINFECTANT(消毒剂)","DISINFECTANT (消毒剂)","CHEMICAL-DISINFECTANT (化学消毒剂)"],
    ["CONTRAINDICATION(禁忌症)","CONTRAINDICATION (禁忌症)","CONTRAINDICATIONS(禁忌症)"],
    ["PHARMACOLOGICAL-EFFECT(药理作用)","PHARMACOLOGICAL-EFFECT (药理作用)","PHARMACOLOGICAL-ACTION(药理作用)"],
    ["IMPLANT(植入物)","IMPLANT (植入物)"],
    ["INSECT(昆虫)","昆虫"],
    ["VITAMIN(维生素)","VITAMIN (维生素)"],
    ["TOXIC-SUBSTANCE(有毒物质)","TOXIC-SUBSTANCES(有毒物质)"],
    ["ORGANIZATION(组织)","ORGANIZATION (组织)","组织","ORGANIZATION"],
    ["DIAGNOSTIC-TEST(诊断测试)","DIAGNOSTIC-TEST (诊断测试)","DIAGNOSTIC TEST"],
    ["CONDITION(条件)","CONDITION"],
    ["TOOL(工具)","TOOL (工具)","工具"],
    ["HERBAL-MEDICINE(中药)","HERB","HERBAL-FORMULA(方药)","HERBAL FORMULA","HERB(草药)"],
    ["FUNGI(真菌)","FUNGUS(真菌)","FUNGI (真菌)","真菌"],
    ["BONE(骨骼)","BONE (骨骼)"]
]

def update_similary_entity_types():
    for row in similar_entity_types:
        for entity_type in row[1:]:
            target_type = row[0]
            result = query(f"MATCH (n:`{entity_type}`) REMOVE n:`{entity_type}` SET n:`{target_type}`")
            summary = result.consume()
            log.info(f"{summary.query},{summary.counters.labels_added} labels_added,{summary.counters.labels_removed} labels_removed.")

def update_index():
    top_10_label_query = """
        match(n) 
        with labels(n) as lbl,count(n) as cnt 
        return lbl,cnt 
        order by cnt desc
        limit 10
    """
    with driver.session() as session:
        result = session.run(top_10_label_query)
        for record in result:
            if (labels := record['lbl']):
                id_index_result = session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:`{labels[0]}`) ON (n.id)")
                summary = id_index_result.consume()
                log.info(f"{summary.query} {summary.counters.indexes_added} indexes_added.")
                
                entity_type_index_result = session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:`{labels[0]}`) ON (n.entity_type)")
                summary = entity_type_index_result.consume()
                log.info(f"{summary.query} {summary.counters.indexes_added} indexes_added.")
            
def clean_dirty_nodes():
    clean_cqls = [

        """
        // 将labels为空的节点赋值为 非空的entity_type
        MATCH (n)
        where n.entity_type is not null and n.entity_type <> '' and size(labels(n))=0
        WITH n, n.entity_type AS entityType
        CALL apoc.create.addLabels([n], [entityType]) YIELD node
        RETURN count(*)
        """,
        
        """
        // 将 entity_type为空的节点赋值为非空的label
        MATCH (n)
        where (n.entity_type is null or n.entity_type='') and size(labels(n))>0
        set n.entity_type=labels(n)[0]
        RETURN count(*)
        """,
        
        """
        // 清除掉 entity_type or source_id  or description is null 的节点
        match (n) 
        where n.entity_type is null or n.source_id is null or n.description is null
        detach delete n;
        """,
        
        """
        // 清除数据源 source_id 非文件的节点
        match (n) 
        where not n.source_id contains '.pdf.txt' 
        detach delete n;
        
        """
    ]
        
    for cql in clean_cqls:
        result = query(cql)
        summary = result.consume()
        log.info(f"{summary.counters.nodes_deleted} nodes_deleted,{summary.counters.relationships_deleted } links_deleted,{summary.counters.relationships_created} relationships_created.")
        
def remove_duplicate_ndoes():
    cql = """
    MATCH (n)
    WITH n.id AS name, n.entity_type AS entity_type, n.description AS description, n.source_id AS source_id, COLLECT(n) AS nodes
    WHERE SIZE(nodes) > 1
    UNWIND nodes AS node
    WITH node, name, entity_type, description, source_id, nodes[0] AS keep_node
    // Transfer outgoing relationships from the duplicate nodes to the "keep" node
    MATCH (node)-[outgoing_rel]->(target)  // match all outgoing relationships of the current node
    MERGE (keep_node)-[outgoing_rel2:RELATED_TO]->(target) // create the same outgoing relationship for the "keep" node

    WITH node, name, entity_type, description, source_id, keep_node
    // Transfer incoming relationships from the duplicate nodes to the "keep" node
    MATCH (source)-[incoming_rel]->(node)  // match all incoming relationships to the current node
    MERGE (source)-[incoming_rel2:RELATED_TO]->(keep_node) // create the same incoming relationship for the "keep" node

    // Delete the duplicate node if its ID, entity_type, description, and source_id match the "keep" node
    WITH node, keep_node
    WHERE node <> keep_node
    DETACH DELETE node
    """
    with driver.session() as session:
        results = session.run(cql)
        summary = results.consume()
        log.info(f"{summary.counters.nodes_deleted} nodes_deleted,{summary.counters.relationships_deleted } links_deleted,{summary.counters.relationships_created} relationships_created.")
        
    
    ## 孤立节点删除
    cql = """
    MATCH (n)
    WITH n.id AS name, n.entity_type AS entity_type, n.description AS description, n.source_id AS source_id, COLLECT(n) AS nodes
    WHERE SIZE(nodes) > 1
    UNWIND nodes AS node
    WITH node, nodes[0] AS keep_node
    WHERE node <> keep_node
    DETACH DELETE node
    """
    with driver.session() as session:
        results = session.run(cql)
        summary = results.consume()
        log.info(f"{summary.counters.nodes_deleted} nodes_deleted,{summary.counters.relationships_deleted } links_deleted,{summary.counters.relationships_created} relationships_created.")
        
    
      
        
def export_duplicate_nodes(export_csv_file="duplicate_nodes.csv"):
    cql = """
    MATCH (n)
    WITH n.id AS name, COLLECT(n) AS nodes
    WHERE SIZE(nodes) > 1
    UNWIND nodes AS node
    RETURN id(node) AS id, node.id AS name, node.entity_type AS entity_type, node.description AS description, node.source_id AS source_id
    ORDER BY node.id,node.entity_type;
    """
    with driver.session() as session:
        results = session.run(cql)
        df = pd.DataFrame(results.data())
        # Export DataFrame to CSV
        df.to_csv(export_csv_file, index=False)

@cache
def get_llm(tenant_id:str = "7d19a176807611efb0f80242ac120006",
        llm_id:str="qwen-plus"):
    return LLMBundle(tenant_id, LLMType.CHAT, llm_id)

def merge_group_of_nodes(node_id:str,
                        nodes_dataframe:pd.DataFrame
                        ):
    llm_bdl = get_llm()
    log.info(f"processing {node_id}")
    # 计算每个组的 entity_type count
    entity_type_grouped = nodes_dataframe.groupby('entity_type').size().reset_index(name='count')
    # 找到 count 最大的 entity_type
    entity_type:str = entity_type_grouped['entity_type'][entity_type_grouped['count'].idxmax()]
    
    #找到全部的 entiti_type 去重
    labels:list = nodes_dataframe['entity_type'].unique().tolist()
    
    #找到全部的 description
    description:str = '\n'.join(nodes_dataframe['description'])
    prompt = f"以下是关于{node_id}的描述信息，你是宠物医生，将以下内容润色，去重，综合成有序，容易理解的语句:{description}"
    description_summary = llm_bdl.chat(prompt, [{"role": "user", "content": "输出:"}], {"temperature": 0.5})
    
    
    #找到全部的 source_id,去重
    file_names = chain(*[get_filepaths_from_source_id(sid) for sid in nodes_dataframe['source_id']])
    source_id:str = '\n'.join(set(file_names))
    
    keep_node_id = nodes_dataframe[nodes_dataframe['entity_type'] == entity_type]["id"].iloc[0]
    
    labels_str = ' '.join([f':`{la}`' for la in labels])
    
    #更新保留节点，融合进其他节点的信息
    execute_update(f"""
        match(n) 
        where id(n)={keep_node_id}
        set n{labels_str},
        n.description='{escape(description_summary)}',
        n.source_id='{escape(source_id)}'
    """)
    
    remove_node_ids = ','.join([str(id) for id in nodes_dataframe['id'] if id != keep_node_id])

        #删除其他节点，并将关系（入和出方向）转移到保留节点
    execute_update(f"""
        MATCH (node)
        where id(node) in [{remove_node_ids}]
        MATCH(keep_node)
        where id(keep_node)={keep_node_id}
        WITH node,keep_node
        // Transfer outgoing relationships from the duplicate nodes to the "keep" node
        MATCH (node)-[outgoing_rel]->(target)  // match all outgoing relationships of the current node
        MERGE (keep_node)-[outgoing_rel2:CONNECTED_TO]->(target) // create the same outgoing relationship for the "keep" node

        WITH node,keep_node
        // Transfer incoming relationships from the duplicate nodes to the "keep" node
        MATCH (source)-[incoming_rel]->(node)  // match all incoming relationships to the current node
        MERGE (source)-[incoming_rel2:CONNECTED_TO]->(keep_node) // create the same incoming relationship for the "keep" node

        // Delete the duplicate node if its ID, entity_type, description, and source_id match the "keep" node
        WITH node
        DETACH DELETE node
    """)
    #删除其他节点，并将关系（入和出方向）转移到保留节点
    execute_update(f"""
        MATCH (node)
        where id(node) in [{remove_node_ids}]
        MATCH(keep_node)
        where id(keep_node)={keep_node_id}
        // Delete the duplicate node if its ID, entity_type, description, and source_id match the "keep" node
        WITH node
        DETACH DELETE node
    """)
        
def merge_duplicate_nodes():
    
    cql = """
    MATCH (n)
    WITH n.id AS name, COLLECT(n) AS nodes
    WHERE SIZE(nodes) > 1
    UNWIND nodes AS node
    RETURN id(node) AS id, node.id AS name, node.entity_type AS entity_type, node.description AS description, node.source_id AS source_id
    ORDER BY node.id;
    """
    with driver.session() as session:
        results = session.run(cql)
        df = pd.DataFrame(results.data())
        grouped = df.groupby('name')
        exe = ThreadPoolExecutor(max_workers=10)
        for name,grouped_data in grouped:
            exe.submit(merge_group_of_nodes,name,grouped_data)
        exe.shutdown(wait=True)
            
def merge_similar_nodes():
    """
        需要合并的节点情况，包含：
        1. 左括弧左侧为空格，例如: "ORAL-BLEEDING (口腔出血)" 应该为： "ORAL-BLEEDING(口腔出血)"
        2. 中英文顺序颠倒， 例如：“鼓音(TYMPANIC-SOUND)” 应该是： "TYMPANIC-SOUND(鼓音)"
        3. 纯中文情况，例如："鼓膜 (鼓膜)"
        4. 英文名称一样，中文不一样，例如: "RODENT (啮齿动物)", "RODENT (啮齿类动物)"
        5. 中文名称一样，英文不一样，例如: "SCREW (螺钉)“,"SCREWS (螺钉)"
        
        此函数执行完成后，需要执行：merge_duplicate_nodes
    """
    
    log.info("1. 融合左括弧左侧为空格的情况，重名为标准情况")
    execute_update("""
        MATCH (n)
        where n.id contains ' ('
        set n.id=replace(n.id,' (','(')
    """)
    
    log.info("2. 融合中英文顺序颠倒， 例如：‘鼓音(TYMPANIC-SOUND)’ 应该是:'TYMPANIC-SOUND(鼓音)'")
    execute_update("""
        MATCH (n)
        WHERE n.id =~ '^[\u4e00-\u9fa5].*'  // 确保首字母为中文
        WITH n,
            split(n.id, '(')[0] AS cn_name, 
            split(n.id, '(')[1] AS en_part
        where cn_name is not null and en_part is not null
        WITH n,cn_name, left(en_part,size(en_part) - 1) AS en_name
        set n.id= en_name + '(' + cn_name + ')'
    """)
    
 
    log.info('4.融合英文名称一样，中文不一样，例如: "RODENT (啮齿动物)", "RODENT (啮齿类动物)"')
    execute_update("""
        MATCH (n)
        WITH split(n.id,'(')[0] AS en_name,COLLECT(n) AS nodes
        WHERE SIZE(nodes) > 1 and en_name is not null 
        UNWIND nodes AS node
        with node,en_name,split(nodes[0].id,'(')[1] AS cn_name,nodes
        where node <> nodes[0]
        with node,en_name,cn_name
        set node.id= en_name + '(' + cn_name
    """)
    
    log.info('5. 融合中文名称一样，英文不一样，例如: "SCREW (螺钉)“,"SCREWS (螺钉)"')
    execute_update("""
        MATCH (n)
        WITH split(n.id,'(')[1] AS cn_name,COLLECT(n) AS nodes
        WHERE SIZE(nodes) > 1 and cn_name=~ '^[\u4e00-\u9fa5]+$'
        UNWIND nodes AS node
        with node,cn_name,split(nodes[0].id,'(')[0] AS en_name,nodes
        where node <> nodes[0]
        with node,en_name,cn_name
        set node.id= en_name + '(' + cn_name
    """)

        
def main():
    merge_similar_nodes()
    merge_duplicate_nodes()
    # remove_duplicate_ndoes()
    # export_duplicate_nodes()
    # check_lost_import_file()
    # add_trigger()
    # update_similary_entity_types()
    # update_index()
    # remove_unlabled_entity()


if __name__ == "__main__":
    main()