from discord import utils


async def converted_emojis(emojis, guild):
    all_emojis = []

    for emoji in emojis:
        emoji_name = emoji['name']
        try:
            emoji_id = int(emoji_name)
        except ValueError:
            emoji_id = None

        if emoji_id is not None:
            emoji_obj = await utils.get(guild.emojis, id=emoji_id)
            if emoji_obj is not None:
                all_emojis.append(emoji_obj)
        else:
            all_emojis.append(emoji_name)

    return all_emojis


async def handle_message(bot, message):
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    get_emojis = \
        """SELECT * FROM asemojis WHERE aschannel_id=$1"""

    channel = message.channel
    guild = message.guild
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sasc = await conn.fetchrow(
                check_aschannel, channel.id
            )

    if sasc is None:
        return False

    valid = True
    reason = None
    
    if len(message.content) < sasc['min_chars']:
        valid = False
        reason = f"messages must be at least {sasc['min_chars']} characters"
    elif len(message.attachments) == 0 and sasc['require_image']:
        valid = False
        reason = "messages must have an image attached"

    if sasc['delete_invalid'] and not valid:
        try:
            await message.delete()
            await message.author.send(
                f"Your message in {channel.mention} "
                f"was deleted because {reason}.\n"
                "I saved your message for you though, here it is:\n"
                f"```\n{message.content}\n```"
            )
        except Exception:
            pass
        finally:
            return
    elif not valid:
        return True

    async with bot.db.lock:
        async with conn.transaction():
            s_emojis = await conn.fetch(
                get_emojis, channel.id
            )

    asemojis = await converted_emojis(s_emojis, guild)

    for e in asemojis:
        try:
            await message.add_reaction(e)
        except Exception:
            pass

    return True
