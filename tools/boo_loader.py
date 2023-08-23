import logging
import re
import ruamel.std.zipfile as zipfile
from bs4 import BeautifulSoup
from ruamel.std.zipfile import delete_from_zip_file

from tools import load_config, extra


class EpubBoo:

    def __init__(self, book_p):
        self.book_path = book_p
        load_config.configure_logging()
        self.logger = logging.getLogger(__name__)

    target_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5']
    noise_tags = []

    def read_book(self):
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
    def fix_indent(a: str, b: str) -> str:
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
                                    self.logger.error("Error while applying translation to a tag with multiple lines.")
                                    break
                    else:
                        para_trans = self.fix_indent(para_trans, para)
                        node.string = para_trans
                    para_count += 1
            # logger.debug(f"页面{idx}共有{para_count}段被成功还原.")
            translated_pages.append(str(soup).encode('utf-8'))
        return translated_pages

    def add_title_glossary(self, orig: list[list[str]], trans: list[list[str]], old_glossary: dict) -> dict:
        flattened_trans_titles = [item for sublist in trans for item in sublist]
        flattened_orig_titles = [item for sublist in orig for item in sublist]
        if len(flattened_orig_titles) == len(flattened_trans_titles):
            self.logger.info("Start adding titles to the glossary")
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


class TxtBoo(EpubBoo):
    def __init__(self, book_p):
        super().__init__(book_p)
        self.page_marks: list[str] = ["=" * 4, '-' * 4]
        self.title_patterns = [
            r"Chapter \d+: (.+)",
            r"Ch\. \d+: (.+)",
            r"Section \d+\.\d+: (.+)"
        ]

    def read_book(self):
        with open(self.book_path, "r") as boo:
            lines = boo.readlines()
            lines = [line.rstrip() for line in lines]
        pg_mk_line_nums = []
        pgs = []
        for idx, line in enumerate(lines):
            for mark in self.page_marks:
                if mark in line:
                    pg_mk_line_nums.append(idx)
                    if len(pg_mk_line_nums) > 1:
                        pgs.append(lines[pg_mk_line_nums[-2]:idx])
                    else:
                        pgs.append(lines[:idx])
        pgs.append(lines[pg_mk_line_nums[-1]:])
        return pg_mk_line_nums, pgs

    def extract_text_from_pages(self, pgs: list[list[str]]) -> list[list[str]]:
        return [list(filter(lambda x: x.strip(), sublist)) for sublist in pgs if any(x.strip() for x in sublist)]

    def extract_titles_from_pages(self, pgs: list) -> list[list[str]]:
        all_title_lines = []
        for pg in pgs:
            pg_title_lines = []
            for line in pg:
                for pattern in self.title_patterns:
                    match = re.match(pattern, line)
                    if match:
                        pg_title_lines.append(line)
                        break
            if pg_title_lines:
                all_title_lines.append(pg_title_lines)
        return all_title_lines

    def apply_trans_to_pages(self, pages_data: list[list[str]], original_contents: list[list[str]],
                             trans_cts: list[list[str]]) -> list[list[str]]:
        trans_pgs = []
        for pg_idx, page in enumerate(pages_data):
            orig_content = original_contents[pg_idx]
            orig_generator = (line for line in orig_content)
            one_orig_line = next(orig_generator)
            trans_content = trans_cts[pg_idx]
            trans_generator = (line for line in trans_content)
            one_trans_line = next(trans_generator)
            trans_page = []
            for line in page:
                if line != one_orig_line or one_orig_line == "":
                    trans_page.append(line)
                else:
                    trans_page.append(one_trans_line)
                    try:
                        one_orig_line = next(orig_generator)
                    except StopIteration:
                        one_orig_line = ""
                    try:
                        one_trans_line = next(trans_generator)
                    except StopIteration:
                        one_trans_line = ""
            trans_pgs.append(trans_page)

        return trans_pgs

    @staticmethod
    def write_pages(tg_path: str, pg_hrefs: list[str], translated_pages_data: list[list[str]]):
        with open(tg_path, "w") as boo:
            for pg in translated_pages_data:
                boo.write("\n".join(pg))
                boo.write("\n")
