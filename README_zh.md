# OpenAI Novel Translator


[English](https://github.com/WeeAris/ONT/blob/master/README.md) | 简体中文


这是一个使用OpenAI API翻译epub的脚本，除了图片排版保留得较好之外一切的功能和代码都很烂，在有替代选项的情况下请不要使用本项目。

**已知的缺点**:

	- 不支持异步并发翻译
	- 只支持epub
	- 不支持单个段落长度超过模型上下文窗口的翻译
	- 未完成自定义需要翻译的元素功能
	- 不支持单独翻译TOC中的目录
	- 不支持逐句或逐段翻译
	- 不支持设置备用翻译选项
	- 不支持使用poe bot等其他API
	- 大量使用AI生成的代码
	- 开发者本人从未学习过软件开发，而且没有时间

**已实现的功能**:

	- 自定义翻译语言和风格
	- 自定义术语表
	- 两种缓存记录方式
	- 在开始翻译正文之前先翻译各页的标题，并添加到术语表中
	- 自定义单次请求原文部分的token上限
	- 不进行翻译，只对token消耗进行估算
    - 能自定义缓存文件位置
	- 能全局统计token实际消耗
    - 自定义提示词功能（实验性的）
    - 上下文模式（类似于历史消息）

**使用示例**:

```commandline
python3 ONT/main.py -b 'path/to/your/ebook.epub' -c 'path/to/your/config.json' -t 'Simplified Chinese'
```

**术语表示例**:

支持的术语类型有per（可选的性别设置）, noun, loc, title, phrase，详细信息请阅读源码。

```json
{

"ウィッチ": {

"trans": "魔女",

"class": "noun"

},

"プライド": {

"trans": "普莱德",

"class": "per",
  
"gender": "female"

},

"フリージア王国": {

"trans": "芙利西亚王国",

"class": "loc"

}}
```

**配置文件示例**:

选项较多，请参考仓库中的[template.json](https://github.com/WeeAris/ONT/blob/master/config/template.json)文件