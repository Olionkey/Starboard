import discord
import functions
import bot_config
import checks
import settings
from discord.ext import commands
from typing import Union
from .wizard import SetupWizard
from settings import change_starboard_settings


async def pretty_emoji_string(emojis, guild):
    string = ""
    for emoji in emojis:
        is_custom = emoji['d_id'] is not None
        if is_custom:
            emoji_string = str(discord.utils.get(
                guild.emojis, id=int(emoji['d_id']))
            )
        else:
            emoji_string = emoji['name']
        string += emoji_string + " "
    return string


class Starboard(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.group(
        name='starboards', aliases=['boards', 's', 'sb'],
        description='List and manage starboards',
        brief='List starboards', invoke_without_command=True
    )
    @commands.guild_only()
    async def sb_settings(
        self, ctx, starboard: discord.TextChannel = None
    ):
        get_starboards = """SELECT * FROM starboards WHERE guild_id=$1"""
        get_emojis = """SELECT * FROM sbemojis WHERE starboard_id=$1"""
        get_starboard = """SELECT * FROM starboards WHERE id=$1"""
        p = await functions.get_one_prefix(self.bot, ctx.guild.id)

        if starboard is None:
            async with self.db.lock:
                conn = await self.db.connect()
                async with conn.transaction():
                    _ = await functions.check_or_create_existence(
                        self.db, conn, self.bot, guild_id=ctx.guild.id,
                        user=ctx.message.author, do_member=True
                    )
                    rows = await conn.fetch(get_starboards, ctx.guild.id)

                    if len(rows) == 0:
                        message = "You don't have any starboards"
                        embed = None
                    else:
                        message = None
                        title = f'Starboards: {len(rows)}\n'
                        msg = ''
                        for row in rows:
                            sb_id = row['id']
                            starboard = self.bot.get_channel(int(sb_id))
                            sb_title = starboard.mention if starboard \
                                else f"Deleted Channel {sb_id}"
                            emojis = await conn.fetch(get_emojis, sb_id)
                            emoji_string = await pretty_emoji_string(
                                emojis, ctx.guild
                            )
                            msg += f"{sb_title} {emoji_string}\n"

                        embed = discord.Embed(
                            title=title, description=msg,
                            color=bot_config.COLOR
                        )
                        embed.set_footer(
                            text=f'Do {p}starboards <channel>'
                            '\nto view starboard settings.'
                        )

            if message is not None:
                await ctx.send(message)
            else:
                await ctx.send(embed=embed)
        else:
            async with self.db.lock:
                conn = await self.db.connect()
                async with conn.transaction():
                    await functions.check_or_create_existence(
                        self.db, conn, self.bot, guild_id=ctx.guild.id,
                        user=ctx.message.author, do_member=True
                    )
                    sql_starboard = await conn.fetchrow(
                        get_starboard, starboard.id
                    )
                    if sql_starboard is None:
                        await ctx.send("That is not a starboard!")
                    else:
                        starboard = self.bot.get_channel(starboard.id)
                        emojis = await conn.fetch(get_emojis, starboard.id)
                        pretty_emojis = await pretty_emoji_string(
                            emojis, ctx.guild
                        )
                        title = f"Settings for {starboard.name}:"
                        string = f"**emojis: {pretty_emojis}**"\
                            "\n**requiredStars: "\
                            f"{sql_starboard['required']}**"\
                            f"\n**requiredToLose: {sql_starboard['rtl']}**"\
                            "\n**selfStar: "\
                            f"{bool(sql_starboard['self_star'])}**"\
                            "\n**linkEdits: "\
                            f"{bool(sql_starboard['link_edits'])}**"\
                            "\n**linkDeletes: "\
                            f"{bool(sql_starboard['link_deletes'])}**"\
                            "\n**botsOnStarboard: "\
                            f"{bool(sql_starboard['bots_on_sb'])}**"\
                            f"\n**locked: {bool(sql_starboard['locked'])}**"

                        embed = discord.Embed(
                            title=title, description=string,
                            color=bot_config.COLOR
                        )
                        await ctx.send(embed=embed)

    @sb_settings.command(
        name='add', aliases=['a'],
        description='Add a starboard',
        brief='Add a starboard'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def add_starboard(self, ctx, starboard: discord.TextChannel):
        await settings.add_starboard(self.bot, starboard)
        await ctx.send(f"Created starboard {starboard.mention}")

    @sb_settings.command(
        name='remove', aliases=['r'],
        description='Remove a starboard',
        brief='Remove a starboard'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def remove_starboard(
        self, ctx, starboard: Union[discord.TextChannel, int]
    ):
        starboard_id = starboard.id if isinstance(
            starboard, discord.TextChannel
        ) else int(starboard)
        confirmed = await functions.confirm(
            self.bot, ctx.channel,
            "Are you sure? All starboard messages will be lost forever.",
            ctx.message.author.id
        )

        if not confirmed:
            await ctx.send("Cancelling")
            return

        await settings.remove_starboard(self.bot, starboard_id, ctx.guild.id)
        await ctx.send("Removed starboard")

    @sb_settings.command(
        name='addEmoji', aliases=['ae'],
        description='Add emoji to a starboard',
        brief='Add emoji to starboard'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def add_starboard_emoji(
        self, ctx, starboard: discord.TextChannel,
        emoji: Union[discord.Emoji, str]
    ):
        await settings.add_starboard_emoji(
            self.bot, starboard.id, ctx.guild, emoji
        )
        await ctx.send(f"Added {emoji} to {starboard.mention}")

    @sb_settings.command(
        name='removeEmoji', aliases=['re'],
        description='Removes a starboard emoji',
        brief='Removes a starboard emoji'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def remove_starboard_emoji(
        self, ctx, starboard: discord.TextChannel,
        emoji: Union[discord.Emoji, str]
    ):
        await settings.remove_starboard_emoji(
            self.bot, starboard.id, ctx.guild, emoji
        )
        await ctx.send(f"Remove {emoji} from {starboard.mention}")

    @sb_settings.command(
        name='requiredStars', aliases=['rs', 'required'],
        description='Set\'s how many stars are needed before a message '
        'appears on the starboard',
        brief='Set\'s required stars'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_required_stars(
        self, ctx, starboard: discord.TextChannel, value: int
    ):
        value = 1 if value < 1 else value
        status = await change_starboard_settings(
            self.db, starboard.id, required=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send(
                "RequiredStars cannot be less than or equal to RequiredToLose"
            )
        else:
            await ctx.send(
                f"Set requiredStars to {value} for {starboard.mention}"
            )

    @sb_settings.command(
        name='requiredToLose', aliases=['rtl'],
        description='Set\'s how few stars a message needs before the '
        'messages is removed from the starboard',
        brief='Sets requiredToLose'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_required_to_lose(
        self, ctx, starboard: discord.TextChannel, value: int
    ):
        value = -1 if value < -1 else value
        status = await change_starboard_settings(
            self.db, starboard.id, rtl=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send(
                "RequiredToLose cannot be greater "
                "than or equal to RequiredStars"
            )
        elif status is True:
            await ctx.send(
                f"Set requiredToLose to {value} "
                f"for {starboard.mention}"
            )

    @sb_settings.command(
        name='selfStar', aliases=['ss'],
        description='Set wether or not to allow a user to star '
        'their own message for starboard',
        brief='Set selfStar for starboard'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def starboard_self_star(
        self, ctx, starboard: discord.TextChannel, value: bool
    ):
        status = await change_starboard_settings(
            self.db, starboard.id, self_star=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Value")
        else:
            await ctx.send(f"Set selfStar to {value} for {starboard.mention}")

    @sb_settings.command(
        name='linkEdits', aliases=['le'],
        description='Sets wether or not the bot should edit the starboard '
        'message if the user edits it',
        brief='Sets linkEdits for a starboard'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_link_edits(
        self, ctx, starboard: discord.TextChannel, value: bool
    ):
        status = await change_starboard_settings(
            self.db, starboard.id, link_edits=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(f"Set linkEdits to {value} for {starboard.mention}")

    @sb_settings.command(
        name='linkDeletes', aliases=['ld'],
        description='Sets wether or not the bot should delete the starboard '
        'message if the original is deleted',
        brief='Sets linkDeletes for a starboard'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_link_deletes(
        self, ctx, starboard: discord.TextChannel, value: bool
    ):
        status = await change_starboard_settings(
            self.db, starboard.id, link_deletes=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(
                f"Set linkDeletes to {value} for {starboard.mention}"
            )

    @sb_settings.command(
        name='botsOnStarboard', aliases=['botsOnSb', 'bos'],
        description="Sets wether or not to allow bot messages "
        "to be put on the starboard",
        brief='Sets botsOnStarboards for a starboard'
    )
    @checks.no_wizzard_running()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_bots_on_starboard(
        self, ctx, starboard: discord.TextChannel, value: bool
    ):
        status = await change_starboard_settings(
            self.db, starboard.id, bots_on_sb=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(
                f"Set botsOnStarboard to {value} for {starboard.mention}"
            )


def setup(bot):
    bot.add_cog(Starboard(bot, bot.db))
