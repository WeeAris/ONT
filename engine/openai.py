import json
import logging
import sqlite3
import time
from string import Template

import requests
import sseclient
import tiktoken
from requests import Response

from tools import load_config, cache_base, extra


class OpenAITrans:
    def __init__(self, model, target_lang):
        load_config.configure_logging()
        self.logger = logging.getLogger(__name__)
        self.enc = tiktoken.get_encoding("cl100k_base")
        self.target_lang = target_lang
        self.api_key = ''
        self.api_base = "https://api.openai.com"
        self.default_model = 'gpt-3.5-turbo'
        self.custom_model = model
        self.default_sys_prompt = (
            "You need to translate the text provided in JSON format to $target_lang. The JSON text consists of multiple key-value pairs, where each key represents a paragraph number and the corresponding value represents the content of a paragraph in the original text. \n"
            "$fmt \n"
            "You need to use your language skills and understanding of the context to ensure that the translated version retains the information and structure of the original text. The translation should read naturally with $target_lang and take into account important cultural and linguistic nuances, and maintain typography as much as possible. \n"
            "You should retain Roman numerals, Arabic numerals and special characters in the original text to ensure a consistent translation style and typography. \n"
            "If the original text is inherently incomplete, you should maintain that incompleteness in the translation in order to ensure accurate meaning and correct style. \n"
            "You will also need to construct a lexical database using terms primarily from the original content to help accurately translate specific sentences, nouns, places and persons. \n"
            "For specified sentences, titles, personal and place names, you should prioritize the use of translations from the glossary below, or if not in the glossary, use an agreed-upon translation based on the characteristics and context of the person or place name, and if none of these methods are appropriate, then finally consider the use of a harmonic translation. Unless it's a conversation between characters or the style of the essay requires it, you should use written language whenever possible. \n"
            "$glossary \n"
            "Your ultimate goal is to provide accurate, creative translations that are clear and easy to read, but also fit the spirit and flavor of the original. \n"
            "Once the translation is complete, take the time to check the translation for readability and accuracy. Translated text needs to be provided in the same JSON structure as received and maintain the original structure of the key-value pairs in the original JSON text. You should especially pay attention to escaping and completeness of symbols.\n"
            "Please do not worry about your translation being interrupted, and try to output your translation as much as possible. \n"
        )
        self.default_sys_prompt_stream = (
            "## Role: Translation Specialist\n"
            "\n"
            "## Profile:\n"
            "- author: WeeAris\n"
            "- version: 0.8\n"
            "- language: $target_lang\n"
            "- description: I'm an excellent and meticulous translator who can translate anything the user types into $target_lang.\n"
            "\n"
            "## Skills:\n"
            "- Proficient in $target_lang, proficient in various languages, understand the culture and allusions of various languages, and good at dealing with the nuances of various languages.\n"
            "- Experienced in translating a wide range of genres, good at understanding the meaning of the text and reasoning about the plot.\n"
            "- Good use of glossaries to ensure consistency and completeness of translations.\n"
            "- Very sensitive to the self-references and emotions of characters in dialogues, and good at distinguishing character relationships in complex dialogues.\n"
            "\n"
            "## Goals:\n"
            "- Translate anything the user types into $target_lang. \n"
            "- Take time to ensure that the translations both read naturally and are in keeping with the spirit and flavor of the original.\n"
            "- Provide accurate and creative translations to user finally.\n"
            "\n"
            "## Constrains:\n"
            "- Do not provide any additional explanations or add content that is not in the original text. \n"
            "- Do not modify typography or convert punctuation if it is not necessary.\n"
            "- Whenever possible, use the translation in the glossary, and if it is not in the glossary, then consider an agreed-upon translation, and finally consider the use of a harmonic translation.\n"
            "- Neither repeat what has already been translated nor omit what has not yet been translated, including which in notes and brackets.\n"
            "- Arabic numerals, Roman numerals and special characters that cannot be translated remain unchanged.\n"
            "\n"
            "$glossary \n"
            "\n"
            "$fmt"
            "## Reminder:\n"
            "Before outputting translation results to users, you will always remind yourself of your role settings, goals and constraints.\n"
            "\n"
            "## Initialization:\n"
            "Directly output $target_lang translation results as much as possible with the same structure and format as received."
        )
        self.default_user_prompt = ("<!--start-input-->\n"
                                    "$origin_text\n"
                                    "<!--end-input-->")
        self.enable_dict_fmt = True
        self.enable_repeat_check = True
        self.glossary_dict = {}
        self.max_try = 3
        self.failed = 0
        self.enable_stream = True
        self.use_split_cache = True
        self.use_page_cache = False
        self.default_cache_path: str = './cache/translation.db'
        self.conn = sqlite3.connect(self.default_cache_path)
        self.prompt_token_cost = 0
        self.completion_token_cost = 0

    fallback = False
    custom_limit_tokens = 0
    custom_sys_prompt = ""
    custom_user_prompt = ""

    def reconnect_conn(self, cache_path):
        self.conn = cache_base.reconnect_conn(self.conn, cache_path)
        c = self.conn.cursor()
        c.execute(f'''CREATE TABLE IF NOT EXISTS split_cache
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT,
                    engine TEXT,
                    model TEXT,
                    original TEXT,
                    trans TEXT)''')
        c.execute(f'''CREATE TABLE IF NOT EXISTS page_cache
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT,
                    engine TEXT,
                    model TEXT,
                    original TEXT,
                    trans TEXT)''')
        c.execute(f'''CREATE TABLE IF NOT EXISTS failed_cache
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            target TEXT,
                            engine TEXT,
                            model TEXT,
                            original TEXT,
                            trans TEXT,
                            time TEXT)''')
        self.conn.commit()

    def lookup_split_cache(self, original_content):
        result = cache_base.lookup_cache(self.conn, self.target_lang, 'openai', self.custom_model, original_content,
                                         'split_cache')
        return result

    def lookup_page_cache(self, original_content):
        result = cache_base.lookup_cache(self.conn, self.target_lang, 'openai', self.custom_model, original_content,
                                         'page_cache')
        return result

    def write_split_cache(self, original_content, trans_content, allow_overwrite=False):
        cache_base.write_cache(self.conn, self.target_lang, 'openai', self.custom_model, original_content,
                               trans_content, 'split_cache', allow_overwrite)

    def write_page_cache(self, original_content, trans_content, allow_overwrite=False):
        cache_base.write_cache(self.conn, self.target_lang, 'openai', self.custom_model, original_content,
                               trans_content, 'page_cache', allow_overwrite)

    def write_failed_cache(self, original_content, trans_content):
        cache_base.write_failed_cache(self.conn, self.target_lang, 'openai', self.custom_model, original_content,
                                      trans_content)

    def judge_model(self, model: str):
        g35_4k = ['gpt-3.5-turbo', 'gpt-3.5-turbo-0613', 'gpt-3.5-turbo-0301']
        g35_16k = ['gpt-3.5-turbo-16k', 'gpt-3.5-turbo-16k-0613', 'gpt-3.5-turbo-16k-0301']
        g4_8k = ['gpt-4', 'gpt-4-0613', 'gpt-4-0314']
        g4_32k = ['gpt-4-32k', 'gpt-4-32k-0613', 'gpt-4-32k-0314']

        if model in g35_4k:
            limit_tokens = 4096
            time_out = 120
        elif model in g35_16k:
            limit_tokens = 16384
            time_out = 240
        elif model in g4_8k:
            limit_tokens = 8192
            time_out = 300
        elif model in g4_32k:
            limit_tokens = 32768
            time_out = 750
        else:
            self.logger.warning(f"Invalid model \"{model}\", fallback to {self.default_model}")
            model = self.default_model
            model, limit_tokens, time_out = self.judge_model(model)

        return model, limit_tokens, time_out

    def split_task(self, original_pages: list[list[str]], limit_token: int) -> list[list[str]]:
        sys_prompt = self.gen_sys_prompt()
        user_prompt = self.gen_user_message(["This is a user message"])
        prompt_tokens = len(self.enc.encode(sys_prompt)) + len(self.enc.encode(user_prompt))
        limit_token = (limit_token * 0.75 - prompt_tokens) / 2

        if self.custom_limit_tokens == 0:
            self.logger.info(f'The value of limit_tokens has been set to default: {limit_token}')
        elif 0 < self.custom_limit_tokens <= limit_token:
            limit_token = self.custom_limit_tokens
        elif self.custom_limit_tokens > limit_token:
            self.logger.warning('The value of custom_limit_tokens exceeds the default value.')
            limit_token = self.custom_limit_tokens

        result = []
        tmp_lst = []
        for page in original_pages:
            for para in page:
                para_token = len(self.enc.encode(para))
                if para_token <= limit_token:
                    if len(self.enc.encode("\n".join(tmp_lst + [para]))) <= limit_token:
                        tmp_lst.append(para)
                    else:
                        result.append(tmp_lst)
                        tmp_lst = [para]
                else:
                    self.logger.error(f"One paragraph is too long, set a token limit greater than {para_token} or "
                                      f"choose to use a model that supports longer context windows.")
                    raise ValueError

            if len(self.enc.encode(str(tmp_lst))) > limit_token / 3:
                result.append(tmp_lst)
                tmp_lst = []
        # If tmp_lst not empty
        if len(tmp_lst) > 0:
            result.append(tmp_lst)
        self.logger.info(f"{len(original_pages)} pages were entered, which were split into {len(result)} translation "
                         f"requests.")
        return result

    def restore_task(self, origin_contents: list[list[str]], translated_contents: list[list[str]]) -> list[list[str]]:
        restored_contents = []
        tmp_page = []
        para_miss = 0
        split_trans_pgs = iter([translated_page for translated_page in translated_contents])
        for page_index, page in enumerate(origin_contents):
            while len(tmp_page) < len(page):
                try:
                    translated_page = next(split_trans_pgs)
                except StopIteration:
                    para_miss += (len(page) - len(tmp_page))
                    self.logger.error(f"Not enough translated content for page {page_index}.")
                    translated_page = [f"Not enough translated content for page {page_index}."] * (
                            len(page) - len(tmp_page))
                tmp_page += translated_page
            restored_contents.append(tmp_page[:len(page)])
            tmp_page = tmp_page[len(page):]
            # 写入整页缓存
            if para_miss == 0:
                same_para = 0
                for i in range(len(page)):
                    if page[i] == restored_contents[-1][i] and extra.is_text(page[i]):
                        same_para += 1
                        break
                if same_para == 0:
                    self.write_page_cache(page, restored_contents[-1])

        # Handle the last page if tmp_paras is not empty
        if tmp_page:
            self.logger.warning(f"Extra translations that shouldn't exist: \n{tmp_page}")
        self.logger.info(f"There were {len(origin_contents)} original pages, {len(translated_contents)} translations "
                         f"were recovered, and {len(restored_contents)} pages were restored.")
        if para_miss > 0:
            self.logger.warning(f"Lost {para_miss} paragraphs after restore.")
        return restored_contents

    @staticmethod
    def formatting_glossary(raw_glossary: dict) -> dict:
        formatted = {}
        formatted_template = Template('- the $td "$original" translates to "$trans"')
        for term in raw_glossary.keys():
            term_dict = raw_glossary[term]
            term_class = term_dict['class']
            term_trans = term_dict['trans']
            if term_class == 'noun':
                term_des = 'noun'
            elif term_class == 'per':
                if term_dict['gender']:
                    term_des = f'{term_dict["gender"]} personal name or calling'
                else:
                    term_des = 'personal name or calling'
            elif term_class == 'loc':
                term_des = 'location'
            elif term_class == 'title':
                term_des = 'chapter title'
            elif term_class == 'phrase':
                term_des = 'established phrase'
            else:
                term_des = 'term'
            term_str = formatted_template.substitute(td=term_des, original=term, trans=term_trans)
            formatted[term] = term_str
        return formatted

    def select_glossary(self, formatted_glossary: dict, origin_content: list[str]):
        if (not self.custom_sys_prompt or "## " not in self.custom_sys_prompt) and (
                self.custom_sys_prompt or not self.enable_stream):
            fin_glossary = ["The glossary includes:"]
        else:
            fin_glossary = ["## Glossary:"]
        content = str(origin_content)
        for term, trans in formatted_glossary.items():
            if term in content:
                fin_glossary.append(trans)
        if len(fin_glossary) > 1:
            return "\n".join(fin_glossary)
        else:
            return ""

    def gen_sys_prompt(self, glossary=""):
        if self.custom_sys_prompt != "":
            prompt_tp = self.custom_sys_prompt
        elif self.enable_stream:
            prompt_tp = self.default_sys_prompt_stream
        else:
            prompt_tp = self.default_sys_prompt
        template = Template(prompt_tp)

        if self.enable_dict_fmt and "$fmt" in prompt_tp:
            schema = r'''{"type": "object", "patternProperties": {"^[0-9]+$": {"type": "string", "title": "Text content of each line", "description": "The key represents line number, value represents text content of that line"}}, "additionalProperties": false}'''
            if "##" in prompt_tp:
                schema_template = Template('## Format: \n$schema \n\n')
            else:
                schema_template = Template('The json schema is: $schema \n\n')
            json_schema = schema_template.substitute(schema=schema)
            prompt = template.substitute(target_lang=self.target_lang, glossary=glossary, fmt=json_schema)
        else:
            prompt = template.substitute(target_lang=self.target_lang, glossary=glossary, fmt="")

        return prompt

    def gen_user_message(self, origin_content: list[str]):
        template = Template(self.default_user_prompt)
        if self.enable_dict_fmt:
            origin_text_dict = {}
            for i, para in enumerate(origin_content):
                origin_text_dict[str(i + 1)] = para
            msg = template.substitute(origin_text=origin_text_dict)
        else:
            origin_text = "\n".join(origin_content)
            msg = template.substitute(origin_text=origin_text)
        return msg

    def parse_result_msg(self, result_msg: str) -> dict:
        result = {}
        result_msg = result_msg.strip()
        result_msg = result_msg.strip("<!--start-output-->")
        result_msg = result_msg.strip("<!--end-output-->")
        result_msg = result_msg.strip()
        if self.enable_dict_fmt:
            try:
                result_dict: dict = json.loads(result_msg)
            except json.decoder.JSONDecodeError as e:
                if "Expecting property name enclosed in double quotes" in e.msg:
                    self.logger.warning('A quote error was detected and will attempt to fix it.')
                    try:
                        result_dict: dict = json.loads(result_msg.replace("'", "\""))
                    except json.decoder.JSONDecodeError as e:
                        self.logger.error(f'Attempts to fix failed, translation message: \n{result_msg}\n')
                        raise e
                else:
                    self.logger.error("Format error, translation result is not in valid JSON format.")
                    raise e

            if isinstance(result_dict, dict):
                result = result_dict
            else:
                self.logger.error(f"The translation result message cannot be converted to a dict type.")
                raise TypeError
        else:
            result_list = result_msg.splitlines()
            result_list = [para.rstrip() for para in result_list if para.rstrip()]
            for idx, para in enumerate(result_list):
                result[str(idx + 1)] = para

        return result

    def check_translation(self, origin_content: list[str], translated_content: dict):
        # 检查译文
        # 检查译文中是否出现了不必要的复读机行为😓
        if self.enable_repeat_check:
            source_set = set(origin_content)
            source_rp = len(origin_content) - len(source_set)
            trans_set = set(translated_content.values())
            trans_rp = len(translated_content.values()) - len(trans_set)
            if source_rp != trans_rp:
                self.logger.error(
                    f"There may be unnecessary repeat or missing in the translation: {source_rp} - {trans_rp}")
                raise ValueError
        # 检查译文是否有缺失
        miss_count = []
        for i, para in enumerate(origin_content):
            idx = str(i + 1)
            if idx not in translated_content.keys():
                translated_content[idx] = para
                miss_count.append(idx)
        if miss_count and len(miss_count) > 1:
            self.logger.error(
                "The number of missing content exceeds the tolerance value, and the missing rows are: " + ", ".join(
                    miss_count))
            raise ValueError
        elif len(miss_count) == 1:
            self.logger.warning(f"The translation on line {miss_count[0]} is missing, filled with its original.")

        # 检查译文是否比原文行数多了
        if len(translated_content.values()) > len(origin_content):
            self.logger.error("The translation may contain content that was not in the original.")
            raise ValueError

        return translated_content

    def translate(self, origin_content: list[str], url: str, key: str, model: str, time_out: int,
                  max_try: int = 5) -> list[str]:
        if origin_content:
            pass
        else:
            return []
        if self.use_split_cache:
            cache_translated = self.lookup_split_cache(origin_content)
            if cache_translated:
                self.logger.info("Hit translation cache, use cache as result.")
                return cache_translated

        self.logger.info("Do not allow use cached results or no cache hit, start the translation request.")
        fin_glossary = self.select_glossary(self.glossary_dict, origin_content)
        if fin_glossary:
            self.logger.info(f'Glossary: \n{fin_glossary}')
        sys_prompt = self.gen_sys_prompt(fin_glossary)
        user_msg = self.gen_user_message(origin_content)
        self.logger.info(f"The original totals {len(origin_content)} lines.")

        if self.enable_stream and not self.enable_dict_fmt:
            presence_penalty = 0.2
            frequency_penalty = 0.4
        else:
            presence_penalty = 0.1
            frequency_penalty = 0.2
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg}],
            "top_p": 1,
            "temperature": 0.6,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "stream": self.enable_stream
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f'Bearer {key}'
        }
        retry_count = 0
        while retry_count < max_try:
            try:
                finish_reason = ''
                if self.enable_stream:
                    self.logger.info("Start to stream requesst.")
                    collected_messages = []
                    response: Response = requests.post(url, data=json.dumps(payload), headers=headers, stream=True)
                    client = sseclient.SSEClient(response)
                    for event in client.events():
                        if event.data != '[DONE]':
                            chunk_data = json.loads(event.data)
                            chunk_message = chunk_data['choices'][0]['delta']
                            collected_messages.append(chunk_message)
                            if chunk_data['choices'][0]['finish_reason'] is not None:
                                finish_reason = chunk_data['choices'][0]['finish_reason']
                    full_content = ''.join([m.get('content', '') for m in collected_messages])
                    prompt_num = len(self.enc.encode(sys_prompt + user_msg))
                    completion_num = len(self.enc.encode(full_content))
                    total_num = prompt_num + completion_num
                else:
                    response: Response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=time_out)
                    res = response.json()
                    finish_reason = res['choices'][0]['finish_reason']
                    full_content: str | dict = res['choices'][0]['message']['content']
                    total_num = res['usage']['total_tokens']
                    prompt_num = res['usage']['prompt_tokens']
                    completion_num = res['usage']['completion_tokens']

                if finish_reason == "stop":
                    pass
                elif finish_reason == "length":
                    self.logger.error(
                        f"The max_tokens limit has been reached, please set a smaller limit_tokens value.")
                    return origin_content
                if total_num:
                    self.logger.info(f"Total tokens cost: {total_num}")
                    self.prompt_token_cost += prompt_num
                    self.completion_token_cost += completion_num
                if isinstance(full_content, str):
                    translated_content = self.parse_result_msg(full_content)
                elif isinstance(full_content, dict):
                    translated_content = full_content
                else:
                    self.logger.error(f"Can not parse type of content: \n{full_content}")
                    raise TypeError

                translated_content = self.check_translation(origin_content, translated_content)
                translated = list(translated_content.values())
                self.logger.info(f"The translation totals {len(translated)} lines.")
                # 成功翻译，缓存后返回结果
                self.write_split_cache(origin_content, translated)
                self.logger.info(f"The translation was successful with retried {retry_count} times.\n")
                return translated
            except requests.exceptions.Timeout:
                self.logger.error(f"Translate request to f{url} timeout\n")
            except requests.exceptions.JSONDecodeError:
                self.logger.error(f'Failed to decode response, status code: {response.status_code}')
                self.logger.debug(f'Response: \n{response.text}\n')
                if response.status_code == 429:
                    sleep_time = (retry_count + 1) ** 2 * 60.0
                    self.logger.warning(f"Reached rate limit, try sleep {sleep_time} seconds\n")
                    time.sleep(sleep_time)
                elif response.status_code == 403:
                    self.logger.error("You seem to be blocked from accessing this API address\n")
                    raise requests.exceptions.HTTPError
                elif response.status_code == 502 or 500 or 524:
                    self.logger.error("The server seems to have encountered an error internally, wait 30s\n")
                    time.sleep(30.0)
                elif response.status_code == 401:
                    self.logger.error("Authentication failed, you may be using an invalid API key.")
                    raise requests.exceptions.HTTPError
            except ValueError as e:
                self.logger.error(f"Translation check failed: {e}")
                try:
                    self.write_failed_cache(origin_content, translated_content)
                except UnboundLocalError:
                    pass
            except Exception as e:
                self.logger.error(f"Other error: {e}")
                continue

            retry_count += 1

        self.logger.error("Exceeded max retry count, giving up. \n")
        self.failed += 1
        self.logger.debug(f"Original: {origin_content}")
        return origin_content

    def start_task(self, origin_contents: list[list[str]]):
        model, limit_tokens, time_out = self.judge_model(self.custom_model)
        self.logger.info(f"Selected model: {model}")
        url = f"{self.api_base}/v1/chat/completions"
        key = self.api_key

        cached_pgs_idx = []
        cached_pgs_trans = []
        no_cache_pgs_idx = []
        no_cache_pgs_orig = []
        for idx, pg in enumerate(origin_contents):
            lk = self.lookup_page_cache(pg)
            if self.use_page_cache and lk:
                cached_pgs_idx.append(idx)
                cached_pgs_trans.append(lk)
            else:
                no_cache_pgs_idx.append(idx)
                no_cache_pgs_orig.append(pg)
        if self.use_page_cache:
            self.logger.info(f"{len(cached_pgs_idx)} pages hit cache")

        spilt_contents = self.split_task(no_cache_pgs_orig, limit_tokens)
        translated_contents = []
        task_num = len(spilt_contents)
        for content in spilt_contents:
            start_time = time.time()
            self.logger.info(f"Total split tasks left: {task_num}/{len(spilt_contents)}")
            translated = self.translate(content, url, key, model, time_out, max_try=self.max_try)
            if isinstance(translated, list):
                translated_contents.append(translated)
            else:
                self.logger.error("Unknown type error")
                translated_contents.append(content)
            task_num -= 1
            end_time = time.time()
            self.logger.info(f"A split task took time: {float(end_time - start_time)}")

        if self.failed > 0:
            self.logger.warning(f"Failed tasks num: {self.failed}/{len(spilt_contents)}\n")

        no_cache_pgs_trans = self.restore_task(no_cache_pgs_orig, translated_contents)
        # 还原索引
        finished_trans = []
        finished_trans += origin_contents
        for idx, pg in enumerate(origin_contents):
            if idx in no_cache_pgs_idx:
                idy = no_cache_pgs_idx.index(idx)
                finished_trans[idx] = no_cache_pgs_trans[idy]
            elif idx in cached_pgs_idx:
                idy = cached_pgs_idx.index(idx)
                finished_trans[idx] = cached_pgs_trans[idy]
            else:
                self.logger.error("Unknown page when apply cache")

        return finished_trans

    def estimate_consumption(self, origin_contents: list[list[str]]):
        model, limit_tokens, time_out = self.judge_model(self.custom_model)
        self.logger.info(f"Selected model: {model}")
        spilt_contents = self.split_task(origin_contents, limit_tokens)
        total_tokens = 0
        for content in spilt_contents:
            fin_glossary = self.select_glossary(self.glossary_dict, content)
            sys_prompt = self.gen_sys_prompt(fin_glossary)
            user_msg = self.gen_user_message(content)
            tokens = len(self.enc.encode(sys_prompt)) + len(self.enc.encode(user_msg))
            total_tokens += tokens
        self.logger.info(f"It is estimated that the prompt part needs to consume {total_tokens} tokens in total.")
