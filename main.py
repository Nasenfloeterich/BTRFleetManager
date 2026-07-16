import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import sqlite3
from discord import app_commands

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
handler = logging.FileHandler(filename="discord.log", encoding="utf-8",mode="w")
intends = discord.Intents.default()
intends.message_content = True
intends.members = True

ADMIN_ROLE_ID = 1197954976186642502

database = sqlite3.connect("playerData.db")
cursor = database.cursor()
database.execute("CREATE TABLE IF NOT EXISTS Faction(Owner STRING, Grid_Name STRING, Grid_Core STRING, GPS STRING, Status STRING, Comments STRING)")

class Client(commands.Bot):
    async def on_ready(self):
        print(f"Logged, {self.user}")
        try:
            guild = discord.Object(id=1197302791929081997)
            synced = await self.tree.sync(guild=guild)
            print("synced")
            
        except Exception as e:
            print(f"Error sync, {e}")

        
    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.startswith("Clanker"):
            await message.channel.send(f"Bot is running")
    
    async def on_reaction_add(self, reaction, user):
        await reaction.message.channel.send("reacted")


client = Client(command_prefix="/", intents=intends)

        
GUILD_ID = discord.Object(id=1197302791929081997)


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

@client.tree.command(name="adduser", description="Add a new player", guild=GUILD_ID)
@app_commands.checks.has_role(ADMIN_ROLE_ID)
async def add_user(interaction: discord.Interaction, member: discord.Member):
    table_name = user_table_name(member.id)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            Owner STRING,
            Grid_Name STRING,
            Grid_Core STRING,
            GPS STRING,
            Status STRING,
            Comments STRING
        )
    """)
    database.commit()
    ensure_instance_column(table_name)   # <-- NEU

    await interaction.response.send_message(f"Added {member.mention}")
    
    
    
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

    await interaction.response.send_message("Registerd Players:\n" + "\n".join(lines), allowed_mentions=discord.AllowedMentions.none())

def migrate_all_tables():
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = cursor.fetchall()
    for (table_name,) in all_tables:
        ensure_instance_column(table_name)

def ensure_instance_column(table_name: str):
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    columns = [row[1] for row in cursor.fetchall()]
    if "Instance" not in columns:
        cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN Instance STRING')
        database.commit()

def migrate_all_tables():
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = cursor.fetchall()
    for (table_name,) in all_tables:
        ensure_instance_column(table_name)

migrate_all_tables() 
@client.tree.command(name="removeuser", description="Removes Player", guild=GUILD_ID)
async def remove_user(interaction: discord.Interaction, member: discord.Member):
    table_name = user_table_name(member.id)

    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    database.commit()

    await interaction.response.send_message(f"Removed {member.mention}.")

INSTANCE_IDS = [f"dx{i}" for i in range(1, 10)]

def ensure_instance_column(table_name: str):
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    columns = [row[1] for row in cursor.fetchall()]
    if "Instance" not in columns:
        cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN Instance STRING')
        database.commit()

ensure_instance_column("Faction")
class InstanceSelectView(discord.ui.View):
    def __init__(self, target_table: str, author: discord.Member):
        super().__init__(timeout=60)
        self.target_table = target_table
        self.author = author

        options = [discord.SelectOption(label=dx, value=dx) for dx in INSTANCE_IDS]
        select = discord.ui.Select(placeholder="Choose instance(dx1-dx9)", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        instance = interaction.data["values"][0]
        await interaction.response.send_modal(
            FleetModal(self.target_table, self.author, instance)
        )
        
        
class FleetModal(discord.ui.Modal, title="Fleet-Entry"):
    def __init__(self, target_table: str, author: discord.Member, instance: str):
        super().__init__()
        self.target_table = target_table
        self.author = author
        self.instance = instance
        self.title = f"Fleet-Entry ({instance})"

    grid_name = discord.ui.TextInput(label="Grid name", required=True, max_length=100)
    grid_core = discord.ui.TextInput(label="Grid core", required=True, max_length=100)
    gps = discord.ui.TextInput(label="GPS", required=True, max_length=100)
    status = discord.ui.TextInput(label="Status", required=True, max_length=50)
    comments = discord.ui.TextInput(
        label="Comment", style=discord.TextStyle.paragraph,
        required=False, max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        cursor.execute(f"""
            INSERT INTO "{self.target_table}" (Owner, Grid_Name, Grid_Core, GPS, Status, Comments, Instance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(self.author), self.grid_name.value, self.grid_core.value, self.gps.value,
              self.status.value, self.comments.value or "", self.instance))
        database.commit()

        embed = discord.Embed(title=f"Saved ({self.instance})", color=discord.Color.green())
        embed.add_field(name="Player", value=self.target_table, inline=False)
        embed.add_field(name="Grid name", value=self.grid_name.value, inline=True)
        embed.add_field(name="Grid core", value=self.grid_core.value, inline=True)
        embed.add_field(name="GPS", value=self.gps.value, inline=True)
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

    
class Target(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.button(label="Faction", style=discord.ButtonStyle.primary, emoji="🏰")
    async def faction_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Choose Instance:",
            view=InstanceSelectView("Faction", self.author)
        )

    @discord.ui.button(label="Player", style=discord.ButtonStyle.secondary, emoji="👤")
    async def spieler_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_admin(self.author):
            await interaction.response.edit_message(
                content="Choose Player:",
                view=Player(self.author)
            )
        else:
            target_table = user_table_name(self.author.id)
            await interaction.response.edit_message(
                content="Choose Instance:",
                view=InstanceSelectView(target_table, self.author)
            )


class Player(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Choose Player")
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        spieler = select.values[0]
        target_table = user_table_name(spieler.id)

        if not table_exists(target_table):
            await interaction.response.send_message(
                f"{spieler.mention} not registerd.", ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="Choose Instance:",
            view=InstanceSelectView(target_table, self.author)
        )
        

    
@client.tree.command(name="fleet", description="Opens Fleetmanager", guild=GUILD_ID)
async def fleet(
    interaction: discord.Interaction):
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
async def embed(interaction: discord.Interaction):
    embed = discord.Embed(title="Help", color=discord.Color.green())
    embed.add_field(name="/help", value="list this", inline=False)
    embed.add_field(name="/adduser", value="adds a player to the database (only Shogun role can add)", inline=False)
    embed.add_field(name="/fleet", value="make a new entry in the database, choosable between faction assets or player assets", inline=False)
    embed.add_field(name="/listusers", value="list all registered players ", inline=False)
    embed.add_field(name="/show", value="shows all assets from players or faction across instances ", inline=False)
    embed.add_field(name="/removeuser", value="removes a player from the databse(no backup, gone forvever)", inline=False)
    embed.set_footer(text="	Fo keng to im gut")
    embed.timestamp = discord.utils.utcnow()
    await interaction.response.send_message(embed=embed)
    

@client.tree.command(name="show", description="Show saved fleet entries", guild=GUILD_ID)
@app_commands.choices(category=[
    app_commands.Choice(name="Faction", value="Faction"),
    app_commands.Choice(name="Player", value="Player"),
])
async def show(
    interaction: discord.Interaction,
    category: app_commands.Choice[str],
    member: discord.Member = None
):
    if category.value == "Faction":
        target_table = "Faction"
    else:
        if member is None:
            await interaction.response.send_message(
                "Please specify a player for the Player category.", ephemeral=True
            )
            return
        target_table = user_table_name(member.id)

    if not table_exists(target_table):
        await interaction.response.send_message(f"No data found for {target_table}.", ephemeral=True)
        return

    cursor.execute(f'''
        SELECT Instance, Owner, Grid_Name, Grid_Core, GPS, Status, Comments 
        FROM "{target_table}"
        ORDER BY Instance
    ''')
    rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message(f"No entries for {target_table}.", ephemeral=True)
        return

    embeds = []
    for instance, owner, grid_name, grid_core, gps, status, comments in rows:
        embed = discord.Embed(title=instance or "Unassigned", color=discord.Color.blue())
        embed.add_field(name="Player", value=owner or "-", inline=False)
        embed.add_field(name="Grid name", value=grid_name or "-", inline=True)
        embed.add_field(name="Grid core", value=grid_core or "-", inline=True)
        embed.add_field(name="GPS", value=gps or "-", inline=True)
        embed.add_field(name="Status", value=status or "-", inline=True)
        embed.add_field(name="Comment", value=comments or "-", inline=False)
        embed.set_footer(text=f"Registered as {target_table}")
        embeds.append(embed)

    await interaction.response.send_message(embeds=embeds[:10])
        
class EditModal(discord.ui.Modal, title="Fleet-Entry bearbeiten"):
    def __init__(self, target_table: str, rowid: int, current: tuple):
        super().__init__()
        self.target_table = target_table
        self.rowid = rowid

        owner, grid_name, grid_core, gps, status, comments = current

        self.grid_name = discord.ui.TextInput(
            label="Grid name", default=grid_name or "", required=True, max_length=100
        )
        self.grid_core = discord.ui.TextInput(
            label="Grid core", default=grid_core or "", required=True, max_length=100
        )
        self.gps = discord.ui.TextInput(
            label="GPS", default=gps or "", required=True, max_length=100
        )
        self.status = discord.ui.TextInput(
            label="Status", default=status or "", required=True, max_length=50
        )
        self.comments = discord.ui.TextInput(
            label="Comment", style=discord.TextStyle.paragraph,
            default=comments or "", required=False, max_length=1000
        )

        for item in (self.grid_name, self.grid_core, self.gps, self.status, self.comments):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        cursor.execute(f"""
            UPDATE "{self.target_table}"
            SET Grid_Name = ?, Grid_Core = ?, GPS = ?, Status = ?, Comments = ?
            WHERE rowid = ?
        """, (self.grid_name.value, self.grid_core.value, self.gps.value,
              self.status.value, self.comments.value or "", self.rowid))
        database.commit()

        embed = discord.Embed(title="Updated", color=discord.Color.orange())
        embed.add_field(name="Grid name", value=self.grid_name.value, inline=True)
        embed.add_field(name="Grid core", value=self.grid_core.value, inline=True)
        embed.add_field(name="GPS", value=self.gps.value, inline=True)
        embed.add_field(name="Status", value=self.status.value, inline=True)
        embed.add_field(name="Comment", value=self.comments.value or "-", inline=False)
        embed.set_footer(text=f"Edited by {interaction.user.display_name}")
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Fehler im EditModal: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Fehler beim Speichern: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"Fehler beim Speichern: {error}", ephemeral=True)


class EditSelectView(discord.ui.View):
    def __init__(self, target_table: str, rows: list):
        super().__init__(timeout=60)
        options = []
        for rowid, owner, grid_name, grid_core, gps, status, comments in rows:
            label = f"{grid_name or '-'} ({status or '-'})"
            options.append(discord.SelectOption(label=label[:100], value=str(rowid)))

        self.rows_by_id = {r[0]: r[1:] for r in rows}
        select = discord.ui.Select(placeholder="Eintrag wählen", options=options[:25])
        select.callback = self.select_callback
        self.target_table = target_table
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        rowid = int(interaction.data["values"][0])
        current = self.rows_by_id[rowid]
        await interaction.response.send_modal(EditModal(self.target_table, rowid, current))


@client.tree.command(name="edit", description="Edit an existing fleet entry", guild=GUILD_ID)
@app_commands.choices(category=[
    app_commands.Choice(name="Faction", value="Faction"),
    app_commands.Choice(name="Player", value="Player"),
])
async def edit(
    interaction: discord.Interaction,
    category: app_commands.Choice[str],
    member: discord.Member = None
):
    if category.value == "Faction":
        target_table = "Faction"
    else:
        if member is None:
            await interaction.response.send_message(
                "Please specify a player for the Player category.",
                ephemeral=True
            )
            return
        if member.id != interaction.user.id and not is_admin(interaction.user):
            await interaction.response.send_message(
                "You can only edit your own entries.",
                ephemeral=True
            )
            return
        target_table = user_table_name(member.id)

    if not table_exists(target_table):
        await interaction.response.send_message(f"No data found for {target_table}.", ephemeral=True)
        return

    cursor.execute(f'SELECT rowid, Owner, Grid_Name, Grid_Core, GPS, Status, Comments FROM "{target_table}"')
    rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message(f"No entries for {target_table}.", ephemeral=True)
        return

    if len(rows) == 1:
        rowid = rows[0][0]
        current = rows[0][1:]
        await interaction.response.send_modal(EditModal(target_table, rowid, current))
    else:
        await interaction.response.send_message(
            "Multiple entries found, please pick one:",
            view=EditSelectView(target_table, rows),
            ephemeral=True
        )
client.run(token, log_handler=handler, log_level=logging.DEBUG)