import aiosqlite
from aiosqlite import Error
from asyncio import Lock


class CommonSql:
    def __init__(self):
        self.create_guild = \
            """INSERT INTO guilds (id)
            VALUES(?)
            """
        self.create_user = \
            """INSERT INTO users (id, is_bot)
            VALUES(?, ?)"""
        self.create_patron = \
            """INSERT INTO patrons (user_id, product_id)
            VALUES(?, ?)"""
        self.create_donation = \
            """INSERT INTO donations
            (txn_id, user_id, product_id, role_id, guild_id,
            email, price, currency, recurring, status)
            VALUES(?,?,?,?,?,?,?,?,?,?)"""
        self.create_member = \
            """INSERT INTO members (user_id, guild_id)
            VALUES(?, ?)"""
        self.create_starboard = \
            """INSERT INTO starboards (id, guild_id)
            VALUES(?, ?)"""
        self.create_sbemoji = \
            """INSERT INTO sbemojis (d_id, starboard_id, name, is_downvote)
            VALUES(?, ?, ?, ?)"""
        self.create_message = \
            """INSERT INTO messages (id, guild_id, user_id, orig_message_id, channel_id, is_orig, is_nsfw)
            VALUES(?, ?, ?, ?, ?, ?, ?)"""
        self.create_reaction = \
            """INSERT INTO reactions (d_id, guild_id, user_id, message_id, name)
            VALUES (?, ?, ?, ?, ?)"""

        self.update_starboard = \
            """UPDATE starboards
            SET self_star=?,
            link_edits=?,
            link_deletes=?,
            bots_react=?,
            bots_on_sb=?,
            required=?,
            rtl=?
            WHERE id=?"""


class Database:
    def __init__(self, db_path):
        self.lock = Lock()
        self.q = CommonSql()
        self._db_path = db_path

    async def open(self):
        await self._create_tables()

    async def connect(self):
        conn = None
        try:
            conn = await aiosqlite.connect(self._db_path)
            await conn.execute(
                "PRAGMA foreign_keys=True"
            )
            conn.row_factory = self._dict_factory
        except Error as e:
            print(f"Couldn't connect to database: {e}")
            if conn:
                #await conn.close()
        return conn

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    async def _create_table(self, sql):
        #cursor = self.cursor()
        conn = await self.connect()
        c = await conn.cursor()
        await c.execute(sql)
        await conn.commit()
        #await conn.close()

    async def _create_tables(self):
        guilds_table = \
            """CREATE TABLE IF NOT EXISTS guilds (
                id integer PRIMARY KEY,

                stars_given integer NOT NULL DEFAULT 0,
                stars_recv integer NOT NULL DEFAULT 0,
                on_sb integer NOT NULL DEFAULT 0
            )"""

        users_table = \
            """CREATE TABLE IF NOT EXISTS users (
                id integer PRIMARY KEY,
                is_bot bool NOT NULL
            )"""

        patrons_table = \
            """CREATE TABLE IF NOT EXISTS patrons (
                id integer PRIMARY KEY,
                user_id integer NOT NULL,
                product_id text NOT NULL
            )"""

        donations_table = \
            """CREATE TABLE IF NOT EXISTS donations (
                id integer PRIMARY KEY,
                txn_id integer NOT NULL,
                user_id integer NOT NULL,
                product_id text DEFAULT NULL,
                role_id text DEFAULT NULL,
                guild_id integer NOT NULL,

                email text NOT NULL,
                price integer NOT NULL,
                currency text NOT NULL,

                recurring bool NOT NULL,
                status text NOT NULL
            )"""

        members_table = \
            """CREATE TABLE IF NOT EXISTS members (
                id integer PRIMARY KEY,
                user_id integer NOT NULL,
                guild_id integer NOT NULL,

                given int NOT NULL DEFAULT 0,
                received int NOT NULL DEFAULT 0,
                on_sb int NOT NULL DEFAULT 0,
                on_lb bool NOT NULL DEFAULT 0,

                xp int NOT NULL DEFAULT 0,
                lvl int NOT NULL DEFAULT 0,

                FOREIGN KEY (user_id) REFERENCES users (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        starboards_table = \
            """CREATE TABLE IF NOT EXISTS starboards (
                id integer PRIMARY KEY,
                guild_id integer NOT NULL,

                required int NOT NULL DEFAULT 3,
                rtl int NOT NULL DEFAULT 0,

                self_star bool NOT NULL DEFAULT 0,
                link_edits bool NOT NULL DEFAULT 1,
                link_deletes bool NOT NULL DEFAULT 0,
                bots_react bool NOT NULL DEFAULT 0,
                bots_on_sb bool NOT NULL DEFAULT 1,

                locked bool NOT NULL DEFAULT 0,
                is_archived bool NOT NULL DEFAULT 0,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        sbemoijs_table = \
            """CREATE TABLE IF NOT EXISTS sbemojis (
                id integer PRIMARY KEY,
                d_id integer,
                starboard_id integer NOT NULL,

                name text NOT NULL,
                is_downvote bool NOT NULL DEFAULT 0,

                FOREIGN KEY (starboard_id) REFERENCES starboards (id)
                    ON DELETE CASCADE
            )"""

        messages_table = \
            """CREATE TABLE IF NOT EXISTS messages (
                id integer PRIMARY KEY,
                guild_id integer NOT NULL,
                user_id integer NOT NULL,
                orig_message_id integer DEFAULT NULL,
                channel_id integer NOT NULL,

                is_orig bool NOT NULL,
                is_nsfw bool NOT NULL,
                is_trashed bool NOT NULL DEFAULT 0,
                is_frozen bool NOT NULL DEFAULT 0,
                is_forced bool NOT NULL DEFAULT 0,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (orig_message_id) REFERENCES messages (id)
                    ON DELETE CASCADE
            )"""

        reactions_table = \
            """CREATE TABLE IF NOT EXISTS reactions (
                id integer PRIMARY KEY,
                d_id integer,
                guild_id integer NOT NULL,
                user_id integer NOT NULL,
                message_id integer NOT NULL,

                name text NOT NULL,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages (id)
            )"""

        await self.lock.acquire()
        await self._create_table(guilds_table)
        await self._create_table(users_table)
        await self._create_table(patrons_table)
        await self._create_table(donations_table)
        await self._create_table(members_table)
        await self._create_table(starboards_table)
        await self._create_table(sbemoijs_table)
        await self._create_table(messages_table)
        await self._create_table(reactions_table)
        self.lock.release()