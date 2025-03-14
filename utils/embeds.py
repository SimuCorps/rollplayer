from cfg import EMBED
from reactionmenu import ViewMenu, ViewButton

import discord

from typing import Optional



def embed_template(interaction: discord.Interaction, title: str, description: Optional[str] = None, footer: Optional[str] = None):
    """Creates an Embed with the default color with provided title and description."""
    _embed_template = discord.Embed(
        title=title,
        description=description if description else "",  # no required description
        color=EMBED["COLOR"],
    )
    if footer == None:
        _embed_template.set_footer(text=EMBED["FOOTER"])
    else:
        _embed_template.set_footer(text=f"{EMBED["FOOTER"]} | {footer}")
    return _embed_template.copy()


def error_template(interaction: discord.Interaction, description: str) -> discord.Embed:
    """Creates an Embed with a red color and an "error!" title."""
    _error_template = discord.Embed(
        title=interaction.client.tree.translator.translate_from_interaction("generic_error", interaction),
        description=description,
        color=0xff0000,
    )
    _error_template.set_footer(text=EMBED["FOOTER"])
    return _error_template.copy()


def success_template(interaction: discord.Interaction, description: str) -> discord.Embed:
    _error_template = discord.Embed(
        title=interaction.client.tree.translator.translate_from_interaction("generic_success", interaction),
        description=description,
        color=EMBED["COLOR"],
    )
    _error_template.set_footer(text=EMBED["FOOTER"])
    return _error_template.copy()

async def viewmenu_paginate_entries(self, ctx: discord.Interaction, entries, title="List", amount=20):
    """Creates a paginated viewer of entries. Also automatically handles display."""
    menu = ViewMenu(ctx, menu_type=ViewMenu.TypeText)
    for i in range(0, len(entries), amount):
        group = entries[i:i + amount]
        formatted_group = "\n".join(f"- {item}" for item in group)
        menu.add_page(content=f"## {title}:\n{formatted_group}")

    menu.add_button(ViewButton.back())
    menu.add_button(ViewButton.next())
    await menu.start()
