import discord
from discord import app_commands
from discord.ext import commands
from utils.logging import log
from utils.embeds import *
from typing import Optional
from utils.translation import JSONTranslator
from utils.data import get_data_manager
from discord.app_commands import locale_str


from reactionmenu import ViewMenu, ViewButton

# TODO: when gamemaster comes out, update the help to reference the increased limits.

class RollHelpCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.translator: JSONTranslator = client.tree.translator


    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: roll help loaded")

    @app_commands.command(name="roll_help", description="Help with /roll's syntax.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def roll_help(self, interaction: discord.Interaction):
        menu = ViewMenu(interaction, menu_type=ViewMenu.TypeEmbed)
        menu.add_page(embed_template(interaction, "Basics", """You can roll a dice by just inputting a number with a "d" before it, e.g. `d100`, which will roll a dice with that many sides.

However, you may also specify the amount of dice being rolled, like `3d100`.
You can also roll multiple different sets of dice in the same command (like `2d10 3d20`), up to a maximum of 5. This is effectively the same as doing two seperate commands for each. They will be shown in the order they are ran 

Ranges are also supported. For example, you could do something like `d10:100`. Both extremes are also included, so you could roll a 10 or 100.

You can also use underscores, which will get completely removed. (e.g. `1d10_000_000` = `1d10000000`). This is especially useful for large numbers."""))

        menu.add_page(embed_template(interaction, "Modifiers", """You can also add modifiers! These allow you to add to rolls, multiply, etc. Note that modifiers add to the result, so `2d10+5` would add 5 total.

The most basic type is math operations, like +, -, \\*, and /. You can tack them to a roll (like `2d20+2`) and they will modify the result of the roll.

There are a lot of more advanced modifiers, on the next few pages.

-# Advanced Note: Using math operations will clear the history [so it will not show you an "original" result] for technical reasons. Every other type of modifier will, however."""))
        
        menu.add_page(embed_template(interaction, "Keeps", """You can decide to keep the highest and/or lowest rolls, if you want to simulate something like DnD's advantage system. This modifier, and all modifiers after it, must be at the end of a dice string.
                                     
For example, `2d20kh` would simulate an advantage roll, keeping the highest roll. Note that in this example, the *kh* stands for "keep higher".

You can also put a number after it, like `5d20kh3`. In this case, it'll keep the highest three rolls.

You can keep lower with *kl* in the same way, e.g. `2d20kl` would be a disadvantage roll.

You can use both at the same time, in which case it'll keep both, so `5d20khkl` would keep the lowest and highest roll."""))
        
        menu.add_page(embed_template(interaction, "Explosions", """Explosions are relatively simple. They use an exclamation mark (*!*) as their syntax. By default, dice explode if they hit the highest rollable value.
                                     
For example, if you rolled a `1d20!` and got a 20, it would roll again. By default, this goes up to 5 times, but you can cap it at a lower value by using a colon then the limit (e.g. `1d20!:3` would limit it to three explosions).

You can also change the criteria by putting a list of conditions in curly quotes. For example, a `1d20!{<5, >15}` would only explode if the rolled value is below 5 OR greater than 15. You can also use a number to define a specific number (e.g. *{12}* would explode on a 12) or use a range (e.g. *{10:13}* would explode on a 10, 11, 12, or 13).

Both a limit and custom conditions can be used in combination, e.g. `1d20!{2,3,5,7,11:13}:4` would explode up to 4 times on a 2, 3, 5, 7, 11, 12, or 13.

-# Advanced Note: If you do an explosion like `1d20!`, a 20 would not be rollable, since an explosion will always add at least one to the roll if it's triggered."""))
        
        menu.add_page(embed_template(interaction, "Conditional Drops", """In addition to simply keeping the best dice or worst dice, you can keep dice based on a condition list [described in the Explosions section].

For example, `5d20drop{<10}` would drop all rolls below 10. They wouldn't be counted in math operations or shown [except in the "original" section].

-# Advanced Note: If the roll ends up having 0 dice, it'll be treated as a 0 for math operations. It's therefore not recommended to do division by a dice with conditional drops [unless you add one first, like `5/(5d20drop{<18}+1)`]."""))
        
        menu.add_page(embed_template(interaction, "Conditional Rerolls", """You can also do conditional rerolls in a similar way to conditional drops.

For example, `5d20rr{<12}` will reroll any rolls below a 12. By default, it only rerolls them once, so it may still end up with a roll less than 12.

However, you can change the limit by putting a colon after, just like explosions. The limit is 5. For example, `1d20rr{>10}:5` would reroll until either it's tried 5 times already or the value is less than 10."""))
        
        menu.add_page(embed_template(interaction, "Targeted Modifiers", """Then you have the *i* modifier, the most complex one. It lets you choose which rolls will be affected by modifiers. This can best be explained with three examples:
- `3d100i1,3:+20` will roll 3 dice and then add 20 to the first and third.
- `3d100i1,3:+20:/5` will do the same, and then divide by 5 [to the first and third]. Note that this is not in PEMDAS order.
- `3d100i*:+20` will add +20 to ALL dice (the asterisk is a wildcard). Note that this will add 60 total, since it's adding 20 to each dice individually.
To put it into actual words, though, the part before the colon is what rolls are selected, and the part after is the list of modifiers. You can do multiple, e.g. *+20:\\*3*."""))
        
        menu.add_page(embed_template(interaction, "Shorthands", """There are also some shorthands available [typing the full word "drop" is going to get annoying when you do it a hundred times]. They are below:
                                     
- `drop`: you can also do `dr` or `D` [must be capitalized].
- `rr`: you can also do `R` [must be capitalized].
- `d100`: if you're looking to roll a percentage dice, you can also just do `d%` as a shorthand."""))
        menu.add_button(ViewButton.back())
        menu.add_button(ViewButton.next())
        await menu.start()

async def setup(client):
    await client.add_cog(RollHelpCog(client))
