# OpenAI Novel Translator


English | [简体中文](https://github.com/WeeAris/ONT/blob/master/README_zh.md)

This is a script that uses the OpenAI API to translate epub files. Other than retaining layouts and images relatively well, everything else about it is crappy, please do not use this project if you have better alternatives. 

**Known Issues**:

	- Does not allow custom prompt engineering
	- Does not support concurrent async translation
	- Only supports epub 
	- Does not handle paragraphs longer than model context window
	- Does not allow selecting custom elements to translate
	- Does not translate TOC independently
	- Does not allow sentence-by-sentence or paragraph-by-paragraph translation
	- Does not allow setting backup translation options
	- Does not support other APIs like poe bot
	- Does not track global token consumption
	- Uses a lot of AI-generated code
	- The developer has never properly learned programming and does not have time

**Implemented Features**:

	- Customizable translation language and style
	- Custom terminology list
	- Two types of cache recording  
	- Translates page titles first before main text, adds to terminology list
	- Allows setting token limit per request
	- Can estimate token cost without actual translation
	- Can custom cache file

**Command Example**:

```commandline
python3 ONT/main.py -b 'path/to/your/ebook.epub' -c 'path/to/your/config.json' -t 'Simplified Chinese'
```

**Terminology Example**:

Supports terms types like per, noun, loc, title, phrase, see source code for details.

```json
{

"ウィッチ": {

"trans": "Witch", 

"class": "noun"

},

"プライド": {

"trans": "Pride",

"class": "per"

},

"フリージア王国": {

"trans": "Kingdom of Frizia",

"class": "loc"

}}
```

**Config Example**:

See [template.json](https://github.com/WeeAris/ONT/blob/master/config/template.json) in repo for a template.