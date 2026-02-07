import sqlite3
from pathlib import Path
from hx_agent.config import settings
from hx_agent.core.logging import setup_logging, get_logger

log = get_logger(__name__)

def foo():
    log.info("hello")
    

def main():
    foo()
# con = sqlite3.connect(settings.KB_DB)
# print("fts count:", con.execute("select count(*) from chunks_fts").fetchone())
# print("fts rowid range:", con.execute("select min(rowid), max(rowid) from chunks_fts").fetchone())
# print("sample fts rowids:", con.execute("select rowid from chunks_fts order by rowid limit 10").fetchall())

# print("chunks count:", con.execute("select count(*) from chunks").fetchone())
# print("chunks id range:", con.execute("select min(id), max(id) from chunks").fetchone())
# print("first 10 ids:", con.execute("select id from chunks order by id limit 10").fetchall())

# print(con.execute("select count(*) from chunks_fts").fetchone())
# print(con.execute("select rowid, length(text), path, heading from chunks_fts limit 3").fetchall())
# print(con.execute("pragma table_info(chunks_fts)").fetchall())

# row = con.execute("select id, file_id, length(text), heading, start_offset, end_offset from chunks where id=23").fetchone()
# print(row)

# row = con.execute("""
# select c.id, f.path, c.heading, substr(c.text,1,120)
# from chunks c join files f on f.id=c.file_id
# where c.id=23
# """).fetchone()
# print(row)