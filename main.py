#!/usr/bin/env python3
import argparse
import os
import shutil
import time

from tools.boo_loader import *

load_config.configure_logging()
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    start_time = time.time()

    parser = argparse.ArgumentParser(description='A script for translating epub books with OpenAI API')
    parser.add_argument('-b', '--book', type=str, default=None, help='The book file path')
    parser.add_argument('-c', '--config-file', type=str, default='./config/default.json',
                        help='The file path to the config file')
    parser.add_argument('-o', '--out-dir', type=str, default='./translated',
                        help='The output directory to save translated books')
    parser.add_argument('-t', '--target-lang', type=str, help='The language and style you want to translate into')
    parser.add_argument('-e', '--estimate', type=bool, default=False,
                        help="If True, estimate how many tokens will be consumed in the prompt part without really "
                             "translating.")
    args = parser.parse_args()

    # 解析命令行参数
    if args.config_file and os.path.exists(args.config_file):
        config = load_config.load_configure(args.config_file)
    else:
        logger.error("config file does not exist")
        raise FileNotFoundError

    output_dir = "."
    cache_method = 'split'
    pre_translate_title = False
    if args.book and os.path.exists(args.book):
        if args.book.endswith('.epub'):
            book_type = 'epub'
        elif args.book.endswith('.txt'):
            book_type = 'txt'
        else:
            logger.error("Unsupported book type.")
            raise TypeError
        book_path = args.book
    else:
        logger.error("You must specify an epub file that exists.")
        raise ValueError
    orig_name = os.path.basename(book_path)
    if args.out_dir and os.path.exists(args.out_dir):
        output_dir = args.out_dir
    if args.target_lang:
        target_lang = args.target_lang
    else:
        logger.error("You must specify the translation language.")
        raise ValueError

    # 解析配置文件
    from engine.openai import OpenAITrans

    oat = OpenAITrans(target_lang)

    if 'api_key' in config['openai'].keys() and config['openai']['api_key']:
        oat.api_key = config['openai']['api_key']
    else:
        logger.error("You must fill in a valid API key in the configuration file.")
        raise UnboundLocalError

    oat.api_base = config['openai'].get('api_base', oat.api_base)
    oat.api_path = config['openai'].get('api_path', oat.api_path)

    if extra.is_valid_url(oat.api_base + oat.api_path):
        oat.api_url = oat.api_base + oat.api_path
    else:
        logger.error("Invalid API URL, please check the API base and API path values.")
        raise ValueError

    oat.use_unofficial_model = config['openai'].get('use_unofficial_model', False)
    oat.custom_model = config['openai'].get('model', oat.default_model)
    oat.enable_stream = config['openai'].get('enable_stream', True)
    oat.enable_dict_fmt = config['openai'].get('enable_dict_fmt', True)
    oat.custom_sys_prompt = config['openai'].get('custom_prompt', '')
    oat.context_num = config['openai'].get('context_num', 0)

    oat.custom_limit_tokens = config['openai'].get('token_limit', 0)
    if oat.use_unofficial_model is True and not oat.custom_limit_tokens:
        logger.error("When you enable unofficial models, you must set a custom token_limit value.")
        raise UnboundLocalError
    else:
        logger.info(f"The token limit has been set to a custom value: {oat.custom_limit_tokens}.\n")

    oat.max_err = config.get('max_err', 3)
    cache_method = config.get('cache_method', 'None')
    oat.use_page_cache = cache_method == 'page'
    oat.use_split_cache = cache_method == 'split'

    raw_glossary = load_config.parse_glossary(config)
    if raw_glossary:
        oat.glossary_dict = oat.formatting_glossary(raw_glossary)

    md5 = extra.get_file_md5(book_path)
    if 'cache_file' in config.keys() and config['cache_file'].endswith('.db'):
        cache_file = config['cache_file']
    else:
        cache_file = f"cache/{md5}.db"
    oat.reconnect_conn(cache_file)

    pre_translate_title = config.get('pre_trans', False)

    tmp_path = f".{md5}.tmp"
    if os.path.exists(tmp_path) and os.path.isfile(tmp_path):
        os.remove(tmp_path)
    shutil.copy2(book_path, tmp_path)

    if book_type == "epub":
        book = EpubBoo(tmp_path)
    elif book_type == "txt":
        book = TxtBoo(tmp_path)
    else:
        raise TypeError("Undefined book type")

    # 读取epub文件
    page_hrefs, all_pages_data = book.read_book()
    orig_titles = book.extract_titles_from_pages(all_pages_data)
    orig_pgs_texts = book.extract_text_from_pages(all_pages_data)

    # 打印元数据
    # logger.info(f"书名：{book.get_metadata('DC', 'title')[0][0]}")
    # logger.info(f"作者：{book.get_metadata('DC', 'creator')[0][0]}")
    # logger.info(f"简介：{book.get_metadata('DC', 'description')[0][0]}")

    if args.estimate:
        oat.estimate_consumption(orig_pgs_texts)
        exit()
    # 准备翻译任务

    if pre_translate_title and orig_titles:
        logger.info("Translate titles before starting to translate content.\n")
        trans_titles = oat.start_task(orig_titles)
        raw_glossary = book.add_title_glossary(orig_titles, trans_titles, raw_glossary)
        oat.glossary_dict = oat.formatting_glossary(raw_glossary)
    logger.info("Begin translation of the main text.\n")
    trans_contents = oat.start_task(orig_pgs_texts)
    logger.info("Completed translation of the main text.\n")
    logger.info(f"Total prompt tokens cost in task: {oat.prompt_token_cost}")
    logger.info(f"Total completion tokens cost in task: {oat.completion_token_cost}")

    # 还原排版
    logger.info("Start saving\n")

    trans_pg_data = book.apply_trans_to_pages(all_pages_data, orig_pgs_texts, trans_contents)
    book.write_pages(tmp_path, page_hrefs, trans_pg_data)

    saved_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    target_path = f"{output_dir}/[{saved_time}]{orig_name}"
    shutil.copy2(tmp_path, target_path)
    os.remove(tmp_path)
    logger.info("Completed Saving\n")

    end_time = time.time()
    logger.info(f"Total running time: {float(end_time - start_time)}")
