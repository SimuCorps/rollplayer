import discord
from discord import app_commands
from discord.ext import commands
from rollplayerlib2.parser import VisitError
from utils.logging import log
from utils.embeds import *
from typing import Optional
from utils.translation import JSONTranslator
from utils.data import get_data_manager
from discord.app_commands import locale_str

from rollplayerlib import Format, UnifiedDice, SolveMode, RollException, FormatType
from rollplayerlib2.main import LimitException, RollResult, transformer_default
from utils.rolling.coloring import *

class RollCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.translator: JSONTranslator = client.tree.translator


    # Use @command.Cog.listener() for an event-listener (on_message, on_ready, etc.)
    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: rolling loaded")

    @app_commands.command(name="command_roll", description="command_roll")
    @app_commands.rename(rolls="command_roll_rolls")
    @app_commands.describe(rolls="command_roll_rolls")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def roll(self, interaction: discord.Interaction, rolls: Optional[str]):

        settings = get_data_manager("user", interaction.user.id)

        if not rolls:
            rolls = settings["Rolling: Default roll"]
            assert type(rolls) is str

        rolls.replace("_", "")
        try: 
            result = await transformer_default(rolls)
        except VisitError as e:
            e = e.orig_exc
            if type(e) == LimitException:
                embed = error_template(interaction, str(e))
                await interaction.response.send_message(embed=embed)
                returnrolls
            raise e
        results = result[0]
        if len(results) == 1:
            try:
                if settings["Global: Compact mode"]:
                    message = f"**{rolls}** | {str(results[0])}\n"
                    if len(message) > 2000:
                        raise RollException("Roll result too long.")

                    await interaction.response.send_message(message)
                    return
                else:
                    embed = embed_template(interaction, f"--- {rolls} ---")
                    embed.color = result[1]
                    if len(str(results[0])) > 1022: raise RollException()
                    embed.add_field(name=f"#{i}:", value=f"[{results[0]}]", inline=False)
                    if type(results[0]) == RollResult and results[0].results != results[0].results_original:
                        if len(results[0].str_originalresults()) > 1022: raise RollException()
                        embed.add_field(name=f"(original) #{i}:", value=f"[{results[0].str_originalresults()}]", inline=False)
                    await interaction.response.send_message(embed=embed)
            except RollException:
                embed = error_template(interaction, self.translator.translate_from_interaction("roll_result_too_long", interaction))
            return
        i = 0
        message = f"### --- {rolls} ---\n"
        embed = embed_template(interaction, f"--- {rolls} ---")
        embed.color = result[1]
        for roll in results:
            i += 1
            try:
                if settings["Global: Compact mode"]:
                    message += f"**{i}**: [{str(results[i-1])}], "
                    if len(message) > 2000:
                        raise RollException("Roll result too long.")
                else:
                    if len(str(results[i-1])) > 1022: raise RollException()
                    embed.add_field(name=f"#{i}:", value=f"[{results[i-1]}]", inline=False)
                    if type(results[i-1]) == RollResult and results[i-1].results != results[i-1].results_original:
                        if len(results[i-1].str_originalresults()) > 1022: raise RollException()
                        embed.add_field(name=f"(original) #{i}:", value=f"[{results[i-1].str_originalresults()}]", inline=False)
                    if len(embed.fields) > 25:
                        raise RollException()
            except RollException:
                embed = error_template(interaction, self.translator.translate_from_interaction("roll_result_too_long", interaction))
                break
        if settings["Global: Compact mode"]:
            await interaction.response.send_message(message[:-2])
            return
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="command_calc", description="command_calc")
    @app_commands.rename(equ="command_calc_equ")
    @app_commands.describe(equ="command_calc_equ")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def calc(self, interaction: discord.Interaction, equ: str):
        await self.roll(interaction, equ)

async def setup(client):
    await client.add_cog(RollCog(client))
