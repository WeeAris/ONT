import json
import sqlite3
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
