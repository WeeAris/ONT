import json
import sqlite3
import time
from sqlite3 import Connection


def reconnect_conn(conn: Connection, cache_path: str):
    conn.close()
    conn = sqlite3.connect(cache_path)
    return conn


def lookup_cache(conn: Connection, target_lang: str, engine: str, model: str, original_content: list[str],
                 table_name: str):
    c = conn.cursor()
    c.execute(f'''SELECT trans FROM {table_name} WHERE target=? AND engine=? AND model=? AND original=?''',
              (target_lang, engine, model, json.dumps(original_content, ensure_ascii=False)))
    result = c.fetchone()
    if result:
        return json.loads(result[0])
    else:
        return result


def write_cache(conn: Connection, target_lang: str, engine: str, model: str, original_content: list[str],
                trans_content: list[str], table_name: str, allow_overwrite=False):
    if not original_content:
        return 
    c = conn.cursor()
    result = lookup_cache(conn, target_lang, engine, model, original_content, table_name)
    if result is not None and not allow_overwrite:
        return
    elif result is not None and allow_overwrite:
        c.execute('''UPDATE ? SET trans=? WHERE target=? AND engine=? AND model=? AND original=?''',
                  (table_name, json.dumps(trans_content, ensure_ascii=False), target_lang, engine, model,
                   json.dumps(original_content, ensure_ascii=False)))
    else:
        c.execute(f'''INSERT INTO {table_name} (target, engine, model, original, trans)
                                VALUES (?, ?, ?, ?, ?)''',
                  (target_lang, engine, model, json.dumps(original_content, ensure_ascii=False),
                   json.dumps(trans_content, ensure_ascii=False)))
    conn.commit()


def write_failed_cache(conn: Connection, target_lang: str, engine: str, model: str, original_content: list[str],
                       trans_content: list | dict):
    c = conn.cursor()
    if isinstance(trans_content, dict):
        trans = list(trans_content.values())
    else:
        trans = trans_content
    saved_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    c.execute(f'''INSERT INTO failed_cache (target, engine, model, original, trans, time)
                                VALUES (?, ?, ?, ?, ?, ?)''',
              (target_lang, engine, model, json.dumps(original_content, ensure_ascii=False),
               json.dumps(trans, ensure_ascii=False), saved_time))
    conn.commit()
