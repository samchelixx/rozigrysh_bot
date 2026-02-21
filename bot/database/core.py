import aiosqlite
import logging
import os

class Database:
    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Giveaways table
            # status: active, finished
            await db.execute("""
                CREATE TABLE IF NOT EXISTS giveaways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_ids TEXT, 
                    description TEXT,
                    media_id TEXT,
                    media_type TEXT,
                    button_text TEXT,
                    publish_channel_id INTEGER,
                    publish_message_id INTEGER,
                    end_time TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Participants table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS participants (
                    user_id INTEGER,
                    giveaway_id INTEGER,
                    is_winner BOOLEAN DEFAULT 0,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, giveaway_id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (giveaway_id) REFERENCES giveaways(id)
                )
            """)
            
            # Admin Channels table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admin_channels (
                    channel_id INTEGER PRIMARY KEY,
                    title TEXT
                )
            """)

            # Migrations (for existing DB)
            try:
                await db.execute("ALTER TABLE giveaways ADD COLUMN publish_channel_id INTEGER")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE giveaways ADD COLUMN publish_message_id INTEGER")
            except Exception: pass
            try:
                await db.execute("ALTER TABLE participants ADD COLUMN is_winner BOOLEAN DEFAULT 0")
            except Exception: pass

            await db.commit()
            logging.info("Tables created successfully.")

    async def create_giveaway(self, description, channel_ids, media_id, media_type, button_text, publish_channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO giveaways (description, channel_ids, media_id, media_type, button_text, publish_channel_id, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (description, channel_ids, media_id, media_type, button_text, publish_channel_id))
            await db.commit()
            return cursor.lastrowid

    async def get_active_giveaways(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM giveaways WHERE status = 'active'") as cursor:
                return await cursor.fetchall()

    async def get_giveaway(self, giveaway_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,)) as cursor:
                return await cursor.fetchone()
    
    async def add_participant(self, user_id, giveaway_id):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO participants (user_id, giveaway_id) VALUES (?, ?)", (user_id, giveaway_id))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False # Already participating

    async def get_participants_count(self, giveaway_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM participants WHERE giveaway_id = ?", (giveaway_id,)) as cursor:
                return (await cursor.fetchone())[0]

    async def get_participants(self, giveaway_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT u.* FROM participants p JOIN users u ON p.user_id = u.id WHERE p.giveaway_id = ?", (giveaway_id,)) as cursor:
                return await cursor.fetchall()
    
    async def get_user_by_username(self, username):
        username = username.lstrip('@')
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)) as cursor:
                return await cursor.fetchone()

    async def finish_giveaway(self, giveaway_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE giveaways SET status = 'finished' WHERE id = ?", (giveaway_id,))
            await db.commit()

    async def set_publish_message_id(self, giveaway_id, message_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE giveaways SET publish_message_id = ? WHERE id = ?", (message_id, giveaway_id))
            await db.commit()

    async def create_user(self, user_id, username, full_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (id, username, full_name)
                VALUES (?, ?, ?)
            """, (user_id, username, full_name))
            await db.execute("""
                UPDATE users SET username = ?, full_name = ? WHERE id = ?
            """, (username, full_name, user_id))
            await db.commit()

    async def get_user(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()

    async def get_winners(self, giveaway_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT u.* FROM participants p JOIN users u ON p.user_id = u.id WHERE p.giveaway_id = ? AND p.is_winner = 1", (giveaway_id,)) as cursor:
                return await cursor.fetchall()
            
    async def set_winner(self, user_id, giveaway_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE participants SET is_winner = 1 WHERE user_id = ? AND giveaway_id = ?", (user_id, giveaway_id))
            await db.commit()

    async def delete_giveaway(self, giveaway_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM participants WHERE giveaway_id = ?", (giveaway_id,))
            await db.execute("DELETE FROM giveaways WHERE id = ?", (giveaway_id,))
            await db.commit()

    async def update_giveaway_description(self, giveaway_id, description):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE giveaways SET description = ? WHERE id = ?", (description, giveaway_id))
            await db.commit()

    async def add_admin_channel(self, channel_id, title):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO admin_channels (channel_id, title) VALUES (?, ?)", (channel_id, title))
            await db.commit()

    async def remove_admin_channel(self, channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM admin_channels WHERE channel_id = ?", (channel_id,))
            await db.commit()

    async def get_admin_channels(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM admin_channels") as cursor:
                return await cursor.fetchall()

db = Database()
