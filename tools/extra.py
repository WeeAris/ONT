"""
本文件中的代码全部由AI生成，软件开发者本人不具有著作权。
代码来源：Perplexity AI语言模型。
来源地址：https://www.perplexity.ai/search/267e1f15-0940-4521-8db0-afc6083bd537?s=c
"""

import re


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
