import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import sqlite3
from discord import app_commands
from Botlogs import log
import overview

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
intends = discord.Intents.default()
intends.message_content = True
intends.members = True

ADMIN_ROLE_ID = 938506759914528838
GUILD_ID = discord.Object(id=938506281080193035)


# sqlite3 init
database = sqlite3.connect("playerData.db")
cursor = database.cursor()
database.execute(
    "CREATE TABLE IF NOT EXISTS Faction(Owner STRING, Grid_Name STRING, Grid_Core STRING, Location STRING, Status STRING, Comments STRING)"
)


# main client and sync check
class Client(commands.Bot):
    async def on_ready(self):
        print(f"Logged, {self.user}")
        try:
            guild = GUILD_ID
            synced = await self.tree.sync(guild=guild)
            print("synced")
        except Exception as e:
            print(f"Error sync, {e}")

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.startswith("Clanker"):
            await message.channel.send("Bot is running")


client = Client(command_prefix="/", intents=intends)


def user_table_name(user_id: int) -> str:
    return f"user_{user_id}"


def is_admin(member: discord.Member) -> bool:
    return any(role.id == ADMIN_ROLE_ID for role in member.roles)


def table_exists(table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None



################################################################################################
# classes


class FleetModal(discord.ui.Modal, title="Fleet Entry"):
    def __init__(self, target_table: str, author: discord.Member):
        super().__init__()
        self.target_table = target_table
        self.author = author
        self.title = "Fleet Entry "

    grid_name = discord.ui.TextInput(label="Grid name", required=True, max_length=100)
    grid_core = discord.ui.TextInput(label="Grid core", required=True, max_length=100)
    location = discord.ui.TextInput(label="Location", required=True, max_length=100)
    status = discord.ui.TextInput(label="Status", required=True, max_length=50)
    comments = discord.ui.TextInput(
        label="Comment", style=discord.TextStyle.paragraph,
        required=False, max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        cursor.execute(f"""
            INSERT INTO "{self.target_table}" (Owner, Grid_Name, Grid_Core, Location, Status, Comments)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(self.author), self.grid_name.value, self.grid_core.value, self.location.value,
              self.status.value, self.comments.value or ""))
        database.commit()

        embed = discord.Embed(title=f"Saved", color=discord.Color.green())
        embed.add_field(name="Player", value=self.target_table, inline=False)
        embed.add_field(name="Grid name", value=self.grid_name.value, inline=True)
        embed.add_field(name="Grid core", value=self.grid_core.value, inline=True)
        embed.add_field(name="Location", value=self.location.value, inline=True)
        embed.add_field(name="Status", value=self.status.value, inline=True)
        embed.add_field(name="comment", value=self.comments.value or "-", inline=False)
        embed.set_footer(text=f"Added by {self.author.display_name}")
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Error on FleetModal: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Error on save: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"Error on save: {error}", ephemeral=True)


class EditModal(discord.ui.Modal, title="Edit Fleet Entry"):
    def __init__(self, target_table: str, rowid: int, current: tuple):
        super().__init__()
        self.target_table = target_table
        self.rowid = rowid

        owner, grid_name, grid_core, location, status, comments = current

        self.grid_name = discord.ui.TextInput(
            label="Grid name", default=grid_name or "", required=True, max_length=100
        )
        self.grid_core = discord.ui.TextInput(
            label="Grid core", default=grid_core or "", required=True, max_length=100
        )
        self.location = discord.ui.TextInput(
            label="Location", default=location or "", required=True, max_length=100
        )
        self.status = discord.ui.TextInput(
            label="Status", default=status or "", required=True, max_length=50
        )
        self.comments = discord.ui.TextInput(
            label="Comment", style=discord.TextStyle.paragraph,
            default=comments or "", required=False, max_length=1000
        )

        for item in (self.grid_name, self.grid_core, self.location, self.status, self.comments):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        cursor.execute(f"""
            UPDATE "{self.target_table}"
            SET Grid_Name = ?, Grid_Core = ?, Location = ?, Status = ?, Comments = ?
            WHERE rowid = ?
        """, (self.grid_name.value, self.grid_core.value, self.location.value,
              self.status.value, self.comments.value or "", self.rowid))
        database.commit()

        embed = discord.Embed(title="Updated", color=discord.Color.orange())
        embed.add_field(name="Grid name", value=self.grid_name.value, inline=True)
        embed.add_field(name="Grid core", value=self.grid_core.value, inline=True)
        embed.add_field(name="Location", value=self.location.value, inline=True)
        embed.add_field(name="Status", value=self.status.value, inline=True)
        embed.add_field(name="Comment", value=self.comments.value or "-", inline=False)
        embed.set_footer(text=f"Edited by {interaction.user.display_name}")
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"EditModal error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Error while saving: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"Error while saving: {error}", ephemeral=True)


class EditSelectView(discord.ui.View):
    """Pick which entry (by rowid) to edit when there's more than one."""
    def __init__(self, target_table: str, rows: list):
        super().__init__(timeout=60)
        options = []
        for rowid, owner, grid_name, grid_core, location, status, comments in rows:
            label = f"{grid_name or '-'} ({location or '-'})"
            options.append(discord.SelectOption(label=label[:100], value=str(rowid)))

        self.rows_by_id = {r[0]: r[1:] for r in rows}
        select = discord.ui.Select(placeholder="Choose entry", options=options[:25])
        select.callback = self.select_callback
        self.target_table = target_table
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        rowid = int(interaction.data["values"][0])
        current = self.rows_by_id[rowid]
        await interaction.response.send_modal(EditModal(self.target_table, rowid, current))


class RemoveSelectView(discord.ui.View):
    """Pick which entry (by rowid) to delete when there's more than one."""
    def __init__(self, target_table: str, rows: list):
        super().__init__(timeout=60)
        options = []
        for rowid, owner, grid_name, grid_core, loaction, status, comments in rows:
            label = f"{grid_name or '-'} ({status or '-'})"
            options.append(discord.SelectOption(label=label[:100], value=str(rowid)))

        self.target_table = target_table
        select = discord.ui.Select(placeholder="Choose entry to delete", options=options[:25])
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        rowid = int(interaction.data["values"][0])
        cursor.execute(f'DELETE FROM "{self.target_table}" WHERE rowid = ?', (rowid,))
        database.commit()
        await interaction.response.edit_message(content="Entry deleted.", view=None)


class PlayerSelectView(discord.ui.View):
    """Admin picks which player's table to work with."""
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Choose Player")
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        target_member = select.values[0]
        target_table = user_table_name(target_member.id)

        if not table_exists(target_table):
            await interaction.response.send_message(
                f"{target_member.mention} not registered.", ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content=f"Menu for {target_member.display_name}:",
            view=SelectCommand(author=self.author, target_table=target_table)
        )


class SelectCommand(discord.ui.View):
    """Add / Edit / Show / Remove menu for a specific table (Faction or a player's)."""
    def __init__(self, author: discord.Member, target_table: str):
        super().__init__(timeout=60)
        self.author = author
        self.target_table = target_table

    @discord.ui.button(label="Add", style=discord.ButtonStyle.primary, emoji="✅")
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FleetModal(self.target_table, self.author))

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="🔧")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not table_exists(self.target_table):
            await interaction.response.send_message(f"No data found for {self.target_table}.", ephemeral=True)
            return

        cursor.execute(f'SELECT rowid, Owner, Grid_Name, Grid_Core, Location, Status, Comments FROM "{self.target_table}"')
        rows = cursor.fetchall()

        if not rows:
            await interaction.response.send_message(f"No entries for {self.target_table}.", ephemeral=True)
            return

        if len(rows) == 1:
            rowid = rows[0][0]
            current = rows[0][1:]
            await interaction.response.send_modal(EditModal(self.target_table, rowid, current))
        else:
            await interaction.response.send_message(
                "Multiple entries found, please pick one:",
                view=EditSelectView(self.target_table, rows),
                ephemeral=True
            )

    @discord.ui.button(label="Show", style=discord.ButtonStyle.primary, emoji="🚀")
    async def show_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_entries(interaction, self.target_table)

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.danger, emoji="❌")
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not table_exists(self.target_table):
            await interaction.response.send_message(f"No data found for {self.target_table}.", ephemeral=True)
            return

        cursor.execute(f'SELECT rowid, Owner, Grid_Name, Grid_Core, Location, Status, Comments FROM "{self.target_table}"')
        rows = cursor.fetchall()

        if not rows:
            await interaction.response.send_message(f"No entries for {self.target_table}.", ephemeral=True)
            return

        if len(rows) == 1:
            rowid = rows[0][0]
            cursor.execute(f'DELETE FROM "{self.target_table}" WHERE rowid = ?', (rowid,))
            database.commit()
            await interaction.response.send_message(f"Deleted entry from {self.target_table}.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Multiple entries found, please pick one to delete:",
                view=RemoveSelectView(self.target_table, rows),
                ephemeral=True
            )


class Target(discord.ui.View):
    """First step from /fleet: choose Faction or Player."""
    def __init__(self, author: discord.Member):
        super().__init__(timeout=200)
        self.author = author

    @discord.ui.button(label="Faction", style=discord.ButtonStyle.primary, emoji="🏰")
    async def faction_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Faction Menu:",
            view=SelectCommand(author=self.author, target_table="Faction")
        )

    @discord.ui.button(label="Player", style=discord.ButtonStyle.secondary, emoji="👤")
    async def spieler_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_admin(self.author):
            await interaction.response.edit_message(
                content="Choose Player:",
                view=PlayerSelectView(self.author)
            )
        else:
            target_table = user_table_name(self.author.id)
            await interaction.response.edit_message(
                content="Player Menu:",
                view=SelectCommand(author=self.author, target_table=target_table)
            )


async def show_entries(interaction: discord.Interaction, target_table: str):
    """Send one embed per instance (dx1-dx9) for the given table."""
    if not table_exists(target_table):
        await interaction.response.send_message(f"No data found for {target_table}.", ephemeral=True)
        return

    cursor.execute(f'''
        SELECT Owner, Grid_Name, Grid_Core, Location, Status, Comments
        FROM "{target_table}"
    ''')
    rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message(f"No entries for {target_table}.", ephemeral=True)
        return

    embeds = []
    for owner, grid_name, grid_core, location, status, comments in rows:
        embed = discord.Embed(title="Fleet", color=discord.Color.blue())
        embed.add_field(name="Player", value=owner or "-", inline=False)
        embed.add_field(name="Grid name", value=grid_name or "-", inline=True)
        embed.add_field(name="Grid core", value=grid_core or "-", inline=True)
        embed.add_field(name="Location", value=location or "-", inline=True)
        embed.add_field(name="Status", value=status or "-", inline=True)
        embed.add_field(name="Comment", value=comments or "-", inline=False)
        embed.set_footer(text=f"Registered as {target_table}")
        embeds.append(embed)

    await interaction.response.send_message(embeds=embeds[:10])


################################################################################################
# /commands

@client.tree.command(name="listusers", description="List all registerd players", guild=GUILD_ID)
async def list_users(interaction: discord.Interaction):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'user_%'")
    tables = cursor.fetchall()

    if not tables:
        await interaction.response.send_message("No player registerd yet.")
        return

    lines = []
    for (table_name,) in tables:
        user_id = table_name.replace("user_", "")
        lines.append(f"<@{user_id}>")

    await interaction.response.send_message(
        "Registerd Players:\n" + "\n".join(lines),
        allowed_mentions=discord.AllowedMentions.none()
    )


@client.tree.command(name="adduser", description="Add a new player", guild=GUILD_ID)
@app_commands.checks.has_role(ADMIN_ROLE_ID)
async def add_user(interaction: discord.Interaction, member: discord.Member):
    table_name = user_table_name(member.id)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            Owner STRING,
            Grid_Name STRING,
            Grid_Core STRING,
            Location STRING,
            Status STRING,
            Comments STRING
        )
    """)
    database.commit()

    await interaction.response.send_message(f"Added {member.mention}")


@client.tree.command(name="removeuser", description="Removes Player", guild=GUILD_ID)
@app_commands.checks.has_role(ADMIN_ROLE_ID)
async def remove_user(interaction: discord.Interaction, member: discord.Member):
    table_name = user_table_name(member.id)

    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    database.commit()

    await interaction.response.send_message(f"Removed {member.mention}.")


@client.tree.command(name="fleet", description="Opens Fleetmanager", guild=GUILD_ID)
async def fleet(interaction: discord.Interaction):
    author = interaction.user

    if not table_exists(user_table_name(author.id)):
        await interaction.response.send_message(
            "Not registerd yet. use /adduser.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Choose:",
        view=Target(author),
        ephemeral=True
    )


@client.tree.command(name="help", description="List all commands", guild=GUILD_ID)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Help", color=discord.Color.green())
    embed.add_field(name="/help", value="list this", inline=False)
    embed.add_field(name="/adduser", value="adds a player to the database (only Shogun role can add)", inline=False)
    embed.add_field(
        name="/fleet",
        value="opens the Fleetmanager menu: choose Faction or Player, then Add / Edit / Show / Remove entries",
        inline=False
    )
    embed.add_field(name="/listusers", value="list all registered players", inline=False)
    embed.add_field(name="/removeuser", value="removes a player from the database (no backup, gone forever)", inline=False)
    embed.set_footer(text="Fo keng to im gut")
    embed.timestamp = discord.utils.utcnow()
    await interaction.response.send_message(embed=embed)


client.run(token, log_handler=handler, log_level=logging.DEBUG)