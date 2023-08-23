"""
本文件中的代码全部由AI生成，@WeeAris本人不具有著作权。
代码来源：Perplexity AI语言模型。
来源地址：
- https://www.perplexity.ai/search/267e1f15-0940-4521-8db0-afc6083bd537?s=c
- https://www.perplexity.ai/search/a8a77e22-88ef-498b-b9f5-0b0869476bc6?s=c
- https://www.perplexity.ai/search/e7063381-3099-4650-8b77-71e0876ae2ed?s=c
"""
import hashlib
import re
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


# 下面👇的函数是人类写的
def list2dict(list_fmt: list[str]):
    dict_fmt = {}
    for i, s in enumerate(list_fmt):
        dict_fmt[str(i + 1)] = s
    return dict_fmt
