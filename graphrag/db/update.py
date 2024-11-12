
from graphrag.db import driver,query
from loguru import logger as log


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
            

def add_trigger():
    add_trigger_cql = """
    CALL apoc.trigger.add(
        'sendAllChangesToApi',  // 触发器名称
        "
        CALL apoc.load.jsonParams(
            'http://8.140.49.13:18080/knowledge_graph/trigger?tenant_id=7d19a176807611efb0f80242ac120006&kb_id=fb7c4312973b11ef88ed0242ac120006',  // 外部 API 的 URL
            {method: 'POST'},  // 使用 POST 方法
            {
                createdNodes: $createdNodes,
                deletedNodes: $deletedNodes,
                createdRelationships: $createdRelationships,
                deletedRelationships: $deletedRelationships,
                assignedNodeProperties: $assignedNodeProperties,
                assignedRelationshipProperties: $assignedRelationshipProperties
            }
        ) YIELD value
        RETURN count(*)
        ",
        {phase: 'after'}
    )
    """
    result = query(add_trigger_cql)
    summary = result.consume()
    log.info(f"{summary.query},{summary.counters.system_updates} system_updates.")
    
def remove_unlabled_entity():
    # 找到所有 entity_type属性为空（label为空）的节点，如果存在和此节点id一样的其他节点，并且entity_type 非空，则删除此entity_type 属性为空的节点
    while True:
        remove_unlabled_entity = """
            // Step 1: 找出无标签的节点
            MATCH (n1)
            WHERE size(labels(n1))=0
            limit 100

            // Step 2: 在有标签的节点中匹配同 id 节点
            WITH n1
            MATCH (n2)
            WHERE n2.id = n1.id AND size(labels(n2))>0
            LIMIT 100

            // Step 1: Transfer outgoing relationships from n1 , only if m exists
            WITH n1, n2
            MATCH (n1)-[r1]->(m)
            WHERE m IS NOT NULL  // Ensure m exists before proceeding
            WITH n1, n2, r1, m
            CREATE (n2)-[r2:CONNECTED_TO]->(m)
            SET r2 = r1
            DELETE r1

            // Step 2: Transfer incoming relationships to n1, only if m exists
            WITH n1, n2
            MATCH (m)-[r3]->(n1)
            WHERE m IS NOT NULL  // Ensure m exists before proceeding
            WITH n1, n2, r3, m
            CREATE (m)-[r4:CONNECTED_TO]->(n2)
            SET r4 = r3
            DELETE r3

            // Step 3: Delete n1
            DETACH DELETE n1

            // Return the count of nodes processed
            RETURN count(n2)

        """
        
        
        remove_unlabled_entity_sub_query = """
        // Step 1: 查找前 100 个无标签的节点
        MATCH (n1)
        WHERE size(labels(n1)) = 0
        WITH n1
        LIMIT 100

        // Step 2: 使用子查询处理每个无标签节点的关系转移和删除
        CALL (n1) {
            // 在有标签的节点中匹配相同 id 的 n2 节点
            MATCH (n2)
            WHERE n2.id = n1.id AND size(labels(n2)) > 0
            LIMIT 1  // 每个 n1 只匹配一个 n2
            
            // Step 3: 转移 n1 的出边关系到 n2
            CALL(n1,n2) {
                MATCH (n1)-[r1]->(m)
                WHERE m IS NOT NULL  // 确保目标节点 m 存在
                CREATE (n2)-[r2:CONNECTED_TO]->(m)
                SET r2 = r1
                DELETE r1
            }

            // Step 4: 转移 n1 的入边关系到 n2
            CALL(n1,n2) {
                MATCH (m)-[r3]->(n1)
                WHERE m IS NOT NULL  // 确保起始节点 m 存在
                CREATE (m)-[r4:CONNECTED_TO]->(n2)
                SET r4 = r3
                DELETE r3
            }

            // Step 5: 删除 n1 节点
            DETACH DELETE n1

            RETURN n2.id AS transferred_to_id  // 返回每个 n2 的 id
        }
        RETURN count(*) AS nodes_processed

        """
        
        # 以上脚本可能会导致 neo4j 异常退出！！！！！，调试好再发布。
        result = query(remove_unlabled_entity)
        summary = result.consume()
        log.info(f"{summary.counters.nodes_deleted} nodes_deleted,{summary.counters.relationships_deleted } links_deleted,{summary.counters.relationships_created} relationships_created.")
        
        if not summary.counters.nodes_deleted:
            break

def main():
    update_similary_entity_types()
    update_index()
    # remove_unlabled_entity()


if __name__ == "__main__":
    main()