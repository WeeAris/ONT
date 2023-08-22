#!/usr/bin/env python3
import argparse
import logging
import os
import shutil
import time

import ruamel.std.zipfile as zipfile
from bs4 import BeautifulSoup
from ruamel.std.zipfile import delete_from_zip_file

from tools import load_config, extra

load_config.configure_logging()
logger = logging.getLogger(__name__)


class Boo:

    def __init__(self, book_p):
        self.book_path = book_p

    target_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5']
    noise_tags = []

    def read_epub(self):
        # 打开epub文件
        pages = []
        with zipfile.ZipFile(self.book_path, 'r') as epub_file:
            file_names = epub_file.namelist()
            # 读取epub文件中的container.xml文件
            if 'META-INF/container.xml' not in file_names:
                print("No 'META-INF/container.xml' file, invalid epub file.")
                return [], []

            with epub_file.open('META-INF/container.xml', 'r') as container_file:
                soup = BeautifulSoup(container_file.read(), 'lxml-xml')
                content_opf_path = \
                    soup.rootfiles.find('rootfile', attrs={'media-type': "application/oebps-package+xml"})['full-path']
            with epub_file.open(content_opf_path, 'r') as content_opf:
                soup = BeautifulSoup(content_opf.read(), 'lxml-xml')
                items = soup.manifest.find_all('item', attrs={'media-type': "application/xhtml+xml"})
                items_hrefs = [content_opf_path.replace('content.opf', item['href']) for item in items]
            for href in items_hrefs:
                with epub_file.open(href, 'r') as page_file:
                    pages.append(page_file.read())
        return items_hrefs, pages

    # 提取需要翻译的文本

    def extract_text_from_pages(self, pages_data: list) -> list[list[str]]:
        BeautifulSoup(features='lxml')
        all_pages_text = []
        for page_data in pages_data:
            soup = BeautifulSoup(page_data, features='lxml')
            texts: list[str] = [tag.get_text() for tag in soup.find_all(self.target_tags) if tag.get_text().strip()]
            all_pages_text.append(texts)

        return all_pages_text

    @staticmethod
    def extract_titles_from_pages(pages_data: list) -> list[list[str]]:
        BeautifulSoup(features='lxml')
        all_titles = []
        for page_data in pages_data:
            soup = BeautifulSoup(page_data, features='lxml')
            titles = []
            try:
                t1 = soup.title.get_text()
                if len(t1.strip()) > 2:
                    titles.append(t1)
            except AttributeError:
                pass
            for s in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5']):
                t = s.get_text()
                if len(t.strip()) > 2 and t not in titles:
                    titles.append(t)
            for s in soup.find_all(attrs={"epub:type": "title"}):
                t = s.get_text()
                if len(t.strip()) > 2 and t not in titles:
                    titles.append(t)
            filter_titles = [title for title in titles if extra.is_text(title)]
            if filter_titles:
                all_titles.append(filter_titles)

        return all_titles

    @staticmethod
    def modify_indent(a: str, b: str) -> str:
        if b.startswith(' '):
            num_spaces = len(b) - len(b.lstrip())
            return (' ' * num_spaces) + a.lstrip()
        elif b.startswith('\t'):
            num_spaces = len(b) - len(b.lstrip())
            return ('\t' * num_spaces) + a.lstrip()
        else:
            return a

    # 用译文替换原文，并保留排版
    def apply_trans_to_pages(self, pages_data: list[bytes], original_contents: list[list[str]],
                             trans_cts: list[list[str]]) -> list[bytes]:
        translated_pages = []
        BeautifulSoup(features='lxml')
        for idx, page in enumerate(pages_data):
            soup = BeautifulSoup(page, features='lxml')
            para_count = 0
            for node in soup.find_all(self.target_tags):
                para = node.text
                if para and para == original_contents[idx][para_count]:
                    para_trans = trans_cts[idx][para_count]
                    trans_split = para_trans.splitlines()
                    trans_split = [sub for sub in trans_split if sub]
                    # 处理一个标签里有多行内容的问题😅
                    if len(trans_split) > 1 and len(trans_split) == len(
                            [sub.get_text().strip() for sub in node.contents if sub.get_text().strip()]):
                        trans_gen = (sub for sub in trans_split)
                        for sub in node.contents:
                            if sub.get_text().strip():
                                try:
                                    sub_trans = next(trans_gen)
                                    sub.string = sub_trans
                                except StopIteration:
                                    logger.error("Error while applying translation to a tag with multiple lines.")
                                    break
                    else:
                        para_trans = self.modify_indent(para_trans, para)
                        node.string = para_trans
                    para_count += 1
            # logger.debug(f"页面{idx}共有{para_count}段被成功还原.")
            translated_pages.append(str(soup).encode('utf-8'))
        return translated_pages

    @staticmethod
    def add_title_glossary(orig: list[list[str]], trans: list[list[str]], old_glossary: dict) -> dict:
        flattened_trans_titles = [item for sublist in trans for item in sublist]
        flattened_orig_titles = [item for sublist in orig for item in sublist]
        if len(flattened_orig_titles) == len(flattened_trans_titles):
            logger.info("Start adding titles to the glossary")
            for idx, orig_title in enumerate(flattened_orig_titles):
                if orig_title not in old_glossary.keys():
                    old_glossary[orig_title] = {
                        "trans": flattened_trans_titles[idx],
                        "class": "title"
                    }
        return old_glossary

    @staticmethod
    def write_pages(tg_path: str, pg_hrefs: list[str], translated_pages_data: list):
        delete_from_zip_file(tg_path, file_names=pg_hrefs)
        with zipfile.ZipFile(tg_path, 'a') as epub_file:
            for idx, href in enumerate(pg_hrefs):
                epub_file.writestr(href, translated_pages_data[idx])


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
    if args.book and os.path.exists(args.book) and args.book.endswith('.epub'):
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

    oat.max_try = config.get('max_try', 3)
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

    tmp_path = f".{md5}.epub"
    if os.path.exists(tmp_path) and os.path.isfile(tmp_path):
        os.remove(tmp_path)
    shutil.copy2(book_path, tmp_path)
    book = Boo(tmp_path)

    # 读取epub文件
    page_hrefs, all_pages_data = book.read_epub()
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
