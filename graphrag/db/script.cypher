
// 找到所有 entity_type 属性为空的节点，如果存在和此节点id一样的其他节点，并且entity_type 非空，则删除此entity_type 属性为空的节点
MATCH (n1)
WITH n1
OPTIONAL MATCH (n2 {id: n1.id})
WHERE (n1.entity_type IS NULL OR n1.entity_type = '') AND (n2.entity_type IS NOT NULL AND n2.entity_type <> '')
WITH n1, n2
WHERE n2 IS NOT NULL
DETACH DELETE n1
RETURN count(n1)



