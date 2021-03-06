from errors import DoesNotExist
import functions
import errors
import discord
from discord.ext import commands
from typing import Union


async def change_starboard_settings(
    db, starboard_id, self_star=None, link_edits=None,
    link_deletes=None, bots_on_sb=None,
    required=None, rtl=None
):
    get_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    update_starboard = \
        """UPDATE starboards
        SET self_star=$1,
        link_edits=$2,
        link_deletes=$3,
        bots_on_sb=$4,
        required=$5,
        rtl=$6
        WHERE id=$7"""

    if required is not None:
        if required > 100:
            required = 100
        elif required < 1:
            required = 1
    if rtl is not None:
        if rtl > 95:
            rtl = 95
        elif rtl < -1:
            rtl = -1

    async with db.lock:
        conn = await db.connect()
        status = True
        async with conn.transaction():
            rows = await conn.fetch(get_starboard, starboard_id)
            if len(rows) == 0:
                status = None
            else:
                ssb = rows[0]

                s = {}
                s['ss'] = self_star if self_star is not None \
                    else ssb['self_star']
                s['le'] = link_edits if link_edits is not None \
                    else ssb['link_edits']
                s['ld'] = link_deletes if link_deletes is not None \
                    else ssb['link_deletes']
                s['bos'] = bots_on_sb if bots_on_sb is not None \
                    else ssb['bots_on_sb']
                s['r'] = required if required is not None \
                    else ssb['required']
                s['rtl'] = rtl if rtl is not None \
                    else ssb['rtl']

                if s['r'] <= s['rtl']:
                    status = False
                else:
                    try:
                        await conn.execute(
                            update_starboard,
                            s['ss'], s['le'], s['ld'], s['bos'], s['r'],
                            s['rtl'], starboard_id
                        )
                    except Exception as e:
                        print(e)
                        status = False
    return status


async def change_aschannel_settings(
    db, aschannel_id, min_chars=None, require_image=None,
    delete_invalid=None
):
    get_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    update_aschannel = \
        """UPDATE aschannels
        SET min_chars=$1,
        require_image=$2,
        delete_invalid=$3
        WHERE id=$4"""

    conn = db.conn
    async with db.lock:
        async with conn.transaction():
            sasc = await conn.fetchrow(
                get_aschannel, aschannel_id
            )
            if sasc is None:
                raise errors.DoesNotExist("That is not an AutoStar Channel!")

            s = {}
            s['mc'] = min_chars if min_chars is not None else sasc['min_chars']
            s['ri'] = require_image if require_image is not None\
                else sasc['require_image']
            s['di'] = delete_invalid if delete_invalid is not None\
                else sasc['delete_invalid']

            if s['mc'] < 0:
                s['mc'] = 0
            elif s['mc'] > 1024:
                s['mc'] = 1024

            await conn.execute(
                update_aschannel, s['mc'], s['ri'], s['di'],
                aschannel_id
            )


async def add_aschannel(bot: commands.Bot, channel: discord.TextChannel):
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    get_aschannels = \
        """SELECT * FROM aschannels WHERE guild_id=$1"""

    guild = channel.guild
    perms = channel.permissions_for(guild.me)
    limit = await functions.get_limit(
        bot.db, 'aschannels', guild
    )
    conn = bot.db.conn

    if not perms.read_messages:
        raise errors.BotNeedsPerms(
            "I need the 'READ MESSAGES' permission in that channel."
        )
    elif not perms.manage_messages:
        raise errors.BotNeedsPerms(
            "I need the `MANAGE MESSAGES` permission in that channel."
        )
    elif not perms.add_reactions:
        raise errors.BotNeedsPerms(
            "I need the `ADD REACTIONS` permission in that channel."
        )

    async with bot.db.lock:
        async with conn.transaction():
            await functions.check_or_create_existence(
                bot.db, conn, bot, guild_id=guild.id
            )

            all_aschannels = await conn.fetch(
                get_aschannels, guild.id
            )

            if len(all_aschannels) >= limit:
                raise errors.NoPremiumError(
                    "You have reached your limit for AutoStar Channels"
                    " in this server.\nTo add more AutoStar channels, "
                    "the server owner must become a patron."
                )

            sql_aschannel = await conn.fetchrow(
                check_aschannel, channel.id
            )

            if sql_aschannel is not None:
                raise errors.AlreadyExists(
                    "That is already an AutoStar Channel!"
                )

            sql_starboard = await conn.fetchrow(
                check_starboard, channel.id
            )

            if sql_starboard is not None:
                raise errors.AlreadyExists(
                    "That channel is already a starboard!\n"
                    "A channel can't be both a starboard and an "
                    "AutoStar channel."
                )

            await bot.db.q.create_aschannel.fetch(
                channel.id, guild.id
            )


async def remove_aschannel(bot: commands.Bot, channel_id: int, guild_id: int):
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1 AND guild_id=$2"""
    del_aschannel = \
        """DELETE FROM aschannels WHERE id=$1"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_aschannel = await conn.fetchrow(
                check_aschannel, channel_id, guild_id
            )

            if sql_aschannel is None:
                raise errors.DoesNotExist("That is not an AutoStar Channel!")

            await conn.execute(del_aschannel, channel_id)


async def add_asemoji(
    bot: commands.Bot, aschannel: discord.TextChannel, name: str
):
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    check_asemoji = \
        """SELECT * FROM asemojis WHERE name=$1 and aschannel_id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sasc = await conn.fetchrow(
                check_aschannel, aschannel.id
            )
            if sasc is None:
                raise errors.DoesNotExist("That is not an AutoStar Channel!")

            se = await conn.fetchrow(
                check_asemoji, name, aschannel.id
            )
            if se is not None:
                raise errors.AlreadyExists(
                    "That emoji is already on this AutoStar Channel!"
                )

            await bot.db.q.create_asemoji.fetch(
                aschannel.id, name
            )


async def remove_asemoji(
    bot: commands.Bot, aschannel: discord.TextChannel, name: str
):
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    check_asemoji = \
        """SELECT * FROM asemojis WHERE name=$1 AND aschannel_id=$2"""
    del_asemojis = \
        """DELETE FROM asemojis WHERE id=$1"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sasc = await conn.fetchrow(
                check_aschannel, aschannel.id
            )
            if sasc is None:
                raise errors.DoesNotExist("That is not an AutoStar Channel!")

            se = await conn.fetchrow(
                check_asemoji, name, aschannel.id
            )
            if se is None:
                raise errors.DoesNotExist(
                    "That emoji is not on that AutoStar Channel!"
                )

            await conn.execute(
                del_asemojis, se['id']
            )


async def add_starboard(bot: commands.Bot, channel: discord.TextChannel):
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    get_starboards = \
        """SELECT * FROM starboards WHERE guild_id=$1"""

    guild = channel.guild
    perms = channel.permissions_for(guild.me)

    if not perms.read_messages:
        raise errors.BotNeedsPerms(
            "I need the `READ MESSAGES` permission in that channel."
        )
    elif not perms.read_message_history:
        raise errors.BotNeedsPerms(
            "I need the `READ MESSAGE HISTORY` permission in that channel."
        )
    elif not perms.send_messages:
        raise errors.BotNeedsPerms(
            "I need the `SEND MESSAGES` permission in that channel."
        )
    elif not perms.embed_links:
        raise errors.BotNeedsPerms(
            "I need the `EMBED LINKS` permission in that channel."
        )
    elif not perms.add_reactions:
        raise errors.BotNeedsPerms(
            "I need the `ADD REACTIONS` permission in that channel."
        )

    limit = await functions.get_limit(
        bot.db, 'starboards', guild
    )
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            await functions.check_or_create_existence(
                bot.db, conn, bot, channel.guild.id
            )

            all_starboards = await conn.fetch(
                get_starboards, guild.id
            )

            if len(all_starboards) + 1 > limit:
                raise errors.NoPremiumError(
                    "You have reached your limit for starboards on this server"
                    "\nTo add more starboards, the owner of this server must "
                    "become a patron."
                )

            sql_starboard = await conn.fetchrow(
                check_starboard, channel.id
            )

            if sql_starboard is not None:
                raise errors.AlreadyExists(
                    "That is already a starboard!"
                )

            sql_aschannel = await conn.fetchrow(
                check_aschannel, channel.id
            )

            if sql_aschannel is not None:
                raise errors.AlreadyExists(
                    "That channel is already an AutoStar channel!\n"
                    "A channel can't be both an AutoStar channel "
                    "and a starboard."
                )

            await bot.db.q.create_starboard.fetch(channel.id, guild.id)

    await add_starboard_emoji(bot, channel.id, channel.guild, '⭐')


async def remove_starboard(bot: commands.Bot, channel_id: int, guild_id: int):
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1 AND guild_id=$2"""
    del_starboard = \
        """DELETE FROM starboards WHERE id=$1"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_starboard = await conn.fetchrow(
                check_starboard, channel_id, guild_id
            )

            if sql_starboard is None:
                raise errors.DoesNotExist(
                    "That is not a starboard!"
                )

            await conn.execute(
                del_starboard, channel_id
            )


async def add_starboard_emoji(
    bot: commands.Bot, starboard_id: int, guild: discord.Guild,
    emoji: Union[discord.Emoji, str]
):
    check_sbemoji = \
        """SELECT * FROM sbemojis WHERE name=$1 AND starboard_id=$2"""
    get_all_sbemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=$1"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""

    if not isinstance(emoji, discord.Emoji):
        if not functions.is_emoji(emoji):
            raise errors.InvalidArgument(
                "I don't recognize that emoji. If it is a custom "
                "emoji, it has to be in this server."
            )

    emoji_name = str(emoji.id) if isinstance(
        emoji, discord.Emoji) else str(emoji)
    emoji_id = emoji.id if isinstance(
        emoji, discord.Emoji) else None

    limit = await functions.get_limit(bot.db, 'emojis', guild)
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_starboard = await conn.fetchrow(
                check_starboard, starboard_id
            )

            if sql_starboard is None:
                raise errors.DoesNotExist("That is not a starboard!")

            all_sbemojis = await conn.fetch(
                get_all_sbemojis, starboard_id
            )

            if len(all_sbemojis) + 1 > limit:
                raise errors.NoPremiumError(
                    "You have reached your limit for emojis "
                    "on this starboard.\nTo add more emojis, "
                    "the server owner must become a patron."
                )

            sbemoji = await conn.fetchrow(
                check_sbemoji, emoji_name, starboard_id
            )

            if sbemoji is not None:
                raise errors.AlreadyExists(
                    "That is already a starboard emoji!"
                )

            await bot.db.q.create_sbemoji.fetch(
                emoji_id, starboard_id, emoji_name, False
            )


async def remove_starboard_emoji(
    bot: commands.Bot, starboard_id: int, guild: discord.Guild,
    emoji: Union[discord.Emoji, str]
):
    check_sbemoji = \
        """SELECT * FROM sbemojis WHERE name=$1 AND starboard_id=$2"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    del_sbemoji = \
        """DELETE FROM sbemojis WHERE name=$1 AND starboard_id=$2"""

    emoji_name = str(emoji.id) if isinstance(emoji, discord.Emoji) else emoji
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_starboard = await conn.fetchrow(
                check_starboard, starboard_id
            )

            if sql_starboard is None:
                raise DoesNotExist(
                    "That is not a starboard!"
                )

            sbemoji = await conn.fetchrow(
                check_sbemoji, emoji_name, starboard_id
            )

            if sbemoji is None:
                raise DoesNotExist(
                    "That is not a starboard emoji!"
                )

            await conn.execute(
                del_sbemoji, emoji_name, starboard_id
            )
