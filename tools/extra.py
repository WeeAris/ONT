"""
本文件中的代码部分或全部由AI生成，@WeeAris本人不具有著作权。
代码来源：Perplexity AI语言模型。
来源地址：
- https://www.perplexity.ai/search/267e1f15-0940-4521-8db0-afc6083bd537?s=c
- https://www.perplexity.ai/search/a8a77e22-88ef-498b-b9f5-0b0869476bc6?s=c
- https://www.perplexity.ai/search/e7063381-3099-4650-8b77-71e0876ae2ed?s=c
-
"""
import hashlib
import random
import re
import string
import subprocess
from urllib.parse import urlparse


def is_arabic_numeral(s):
    # 判断字符串是否为阿拉伯数字
    return s.isdigit()


def is_roman_numeral(s):
    # 判断字符串是否为合法的罗马数字
    if s is None or not isinstance(s, str):
        return False
    pattern = '^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$'
    return bool(re.match(pattern, s))


def roman_to_arabic(s):
    # 将罗马数字转换为阿拉伯数字
    if not is_roman_numeral(s):
        raise ValueError('Invalid Roman numeral')
    roman_numerals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    arabic_numeral = 0
    for i in range(len(s)):
        if i > 0 and roman_numerals[s[i]] > roman_numerals[s[i - 1]]:
            arabic_numeral += roman_numerals[s[i]] - 2 * roman_numerals[s[i - 1]]
        else:
            arabic_numeral += roman_numerals[s[i]]
    return arabic_numeral


def is_number(s):
    # 判断字符串是否为数字（包括阿拉伯数字和罗马数字）
    if s is None or not isinstance(s, str):
        return False
    try:
        return is_arabic_numeral(s) or (is_roman_numeral(s) and is_arabic_numeral(str(roman_to_arabic(s))))
    except ValueError:
        return False


def is_text(s):
    # 判断字符串是否为普通文本
    return not is_number(s)


def get_file_md5(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
        md5_value = hashlib.md5(data).hexdigest()
    return md5_value


def is_valid_url(uurl):
    try:
        result = urlparse(uurl)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def list2dict(list_fmt: list[str]):
    dict_fmt = {}
    for i, s in enumerate(list_fmt):
        dict_fmt[str(i + 1)] = s
    return dict_fmt


def review_trans(orig: list[str], trans: list[str]):
    print("\n")
    from colorama import init, Fore
    init(autoreset=True)
    for i, s in enumerate(orig):
        print(f'{Fore.GREEN}Orig{Fore.RESET} {i + 1}:\t{s}\n')
        print(f'{Fore.YELLOW}Trans{Fore.RESET} {i + 1}:\t{trans[i]}\n')
    choice = input("Do you accept current translation ver? (y/n, default y) ")
    if not choice or choice == "y":
        return True
    else:
        return False


def edit_trans(orig: list[str], trans: list[str]) -> list[str]:
    tmp_content = []
    for i, s in enumerate(orig):
        tmp_content += [s, trans[i], ""]
    editors = ["gedit", "nano", "vim"]
    editor_found = False
    while not editor_found:
        # 生成随机的文件名
        filename = "." + "".join(random.choices(string.ascii_lowercase, k=8)) + ".txt"
        try:
            # 尝试在当前目录下创建临时文件
            with open(filename, "w") as f:
                f.write("\n".join(tmp_content))
            editor_command = ""
            # 尝试使用编辑器打开临时文件
            for editor in editors:
                try:
                    subprocess.run([editor, filename], check=True)
                    editor_found = True
                    editor_command = editor
                    break
                except FileNotFoundError:
                    continue
            if not editor_found:
                custom_command = input("没有找到可用的编辑器，请输入自定义命令：")
                subprocess.run([custom_command, filename], check=True)
                editor_command = custom_command
            print("请进行编辑并保存。")
            # 读取编辑后的译文
            with open(filename, "r") as f:
                edited_translation = f.readlines()
                edited_translation = [line.rstrip() for line in edited_translation if line.strip()]
            # 检查编辑前后译文行数是否相等
            while len(orig) * 2 != len(edited_translation):
                print("编辑前后译文行数不一致，请重新编辑。")
                subprocess.run([editor_command, filename], check=True)
                with open(filename, "r") as f:
                    edited_translation = f.readlines()
                    edited_translation = [line.rstrip() for line in edited_translation if line.strip()]
            print("译文已保存。")
            # 在此处添加保存译文的代码
            return edited_translation[1::2]
        except IOError:
            # 如果文件名已经存在，则重新生成文件名
            continue
