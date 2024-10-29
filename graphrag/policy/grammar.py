grammar = r"""
    start: exp | not_exp

    exp: and_exp ("or" and_exp)*  // "or" 连接多个 and_exp
    and_exp: term ("and" term)*  // "and" 优先于 "or"
    not_exp: "not" term          // "not" 修饰一个表达式            
    term: item_eq
        | item_contains              
        | item_regexp   
        | "(" exp ")"
    item_eq: ENTITY_TYPE ENTITY_ATTRIBUTE? "=" ENTITY_ATTRIBUTE_VALUE ("," ENTITY_ATTRIBUTE_VALUE)*  // 实体属性值等于，如果多个值，中间用‘，’分开
    item_contains: ENTITY_TYPE ENTITY_ATTRIBUTE? "~" ENTITY_ATTRIBUTE_VALUE  // 实体属性值包含字符, 属性可以为空
    item_regexp: ENTITY_TYPE ENTITY_ATTRIBUTE? "=~" ENTITY_ATTRIBUTE_VALUE  // 实体属性值正则匹配

    ENTITY_TYPE: /[\u4e00-\u9fff\w]+|'([^']*)'/              // 匹配中文汉字和英文标识符， 兼容单引号包裹的情况
    ENTITY_ATTRIBUTE: "." /[\u4e00-\u9fff\w]+|'([^']*)'/     // 匹配中文汉字和英文标识符,属性必须以'.'开头， 兼容单引号包裹的情况
    ENTITY_ATTRIBUTE_VALUE: /[\u4e00-\u9fff\w]+|'([^']*)'/   // 匹配中文汉字和英文标识符， 兼容单引号包裹的情况

    %import common.WS_INLINE
    %ignore WS_INLINE
    """
    