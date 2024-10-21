from graphrag.graph_prompt import GRAPH_EXTRACTION_PROMPT
from graphrag.utils import perform_variable_replacements


def sss(chunks, left_token_count, ext, entity_types, callback):
    BATCH_SIZE = 4
    texts, sub_texts, graphs = [], [], []

    cnt = 0
    for i in range(len(chunks)):
        tkn_cnt = num_tokens_from_string(chunks[i])
        if cnt + tkn_cnt >= left_token_count and texts:
            for b in range(0, len(texts), BATCH_SIZE):
                sub_texts.append(texts[b:b + BATCH_SIZE])
            texts = []
            cnt = 0
        texts.append(chunks[i])
        cnt += tkn_cnt
    if texts:
        for b in range(0, len(texts), BATCH_SIZE):
            sub_texts.append(texts[b:b + BATCH_SIZE])


def num_tokens_from_string(string: str) -> int:
    1


DEFAULT_TUPLE_DELIMITER = "<|>"
DEFAULT_RECORD_DELIMITER = "##"
DEFAULT_COMPLETION_DELIMITER = "<|COMPLETE|>"
DEFAULT_ENTITY_TYPES = ["organization", "person", "location", "event", "time"]
ENTITY_EXTRACTION_MAX_GLEANINGS = 1

DEFAULT_TUPLE_DELIMITER_KEY='tuple_delimiter',
DEFAULT_RECORD_DELIMITER_KEY='record_delimiter',
DEFAULT_COMPLETION_DELIMITER_KEY='completion_delimiter',
DEFAULT_ENTITY_TYPES_KEY='entity_types',
DEFAULT_INPUT_TEXT_KEY='input_text',


def create_prompt_variables( prompt_variables,
                             _tuple_delimiter_key=DEFAULT_TUPLE_DELIMITER_KEY,
                             _record_delimiter_key=DEFAULT_RECORD_DELIMITER_KEY,
                             _completion_delimiter_key=DEFAULT_COMPLETION_DELIMITER_KEY,
                             _entity_types_key=DEFAULT_ENTITY_TYPES_KEY,
                             _input_text_key=DEFAULT_INPUT_TEXT_KEY,
                             _extraction_prompt=GRAPH_EXTRACTION_PROMPT):
    if prompt_variables is None:
        prompt_variables = {}
    # Wire defaults into the prompt variables
    prompt_variables = {
        **prompt_variables,
        _tuple_delimiter_key: prompt_variables.get(_tuple_delimiter_key)
                              or DEFAULT_TUPLE_DELIMITER,
        _record_delimiter_key: prompt_variables.get(_record_delimiter_key)
                               or DEFAULT_RECORD_DELIMITER,
        _completion_delimiter_key: prompt_variables.get(_completion_delimiter_key)
                                   or DEFAULT_COMPLETION_DELIMITER,

        _entity_types_key: ",".join(
            prompt_variables.get(_entity_types_key) or DEFAULT_ENTITY_TYPES
        ),
    }

    return prompt_variables

def process(
        text,
        prompt_variables,
        _input_text_key='input_text',
        _extraction_prompt=GRAPH_EXTRACTION_PROMPT
):
    variables = {
        **prompt_variables,
        _input_text_key: text,
    }
    text = perform_variable_replacements(_extraction_prompt, variables=variables)
    gen_conf = {"temperature": 0.3}
    messages = chat_1(text, [{"role": "user", "content": "Output:"}])
    return messages

def chat_1(text, history):
    if text:
        history.insert(0, {"role": "system", "content": text})

    return history;


messages = process('abc', create_prompt_variables({"entity_types": "person"}))
print(messages)