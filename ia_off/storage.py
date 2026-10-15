import sqlite3, time

class Storage:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS conv(id INTEGER PRIMARY KEY, title TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS msg(id INTEGER PRIMARY KEY, conv INTEGER, role TEXT, content TEXT, ts REAL);
        """)

    def new_conv(self, title="Nova conversa"):
        c = self.db.execute("INSERT INTO conv(title,created) VALUES(?,?)", (title, time.time()))
        self.db.commit()
        return c.lastrowid

    def list_convs(self):
        return self.db.execute("SELECT id,title FROM conv ORDER BY created DESC").fetchall()

    def rename(self, cid, title):
        self.db.execute("UPDATE conv SET title=? WHERE id=?", (title, cid)); self.db.commit()

    def delete(self, cid):
        self.db.execute("DELETE FROM msg WHERE conv=?", (cid,))
        self.db.execute("DELETE FROM conv WHERE id=?", (cid,)); self.db.commit()

    def add_msg(self, cid, role, content):
        self.db.execute("INSERT INTO msg(conv,role,content,ts) VALUES(?,?,?,?)", (cid, role, content, time.time()))
        self.db.commit()

    def messages(self, cid):
        return [{"role": r, "content": c} for r, c in
                self.db.execute("SELECT role,content FROM msg WHERE conv=? ORDER BY id", (cid,))]
