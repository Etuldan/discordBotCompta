# bot.py
# python3 -m pip install discord.py discord-py-interactions fpdf

import discord
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import SlashCommandPermissionType

from sys import platform
import locale
from fpdf import FPDF
from datetime import datetime, timedelta

import asyncio

import configparser
import sqlite3

COLOR_RED = 0xE74C3C
COLOR_GREEN = 0x00ff00
COLOR_LIGHT_GREY = 0xBCC0C0
COLOR_DARK_GOLD = 0xC27C0E
COLOR_DEFAULT = 0
COLOR_ORANGE  = 0xFF5733

slash = None

    
class Bot(discord.Client):
    message_head_income = {}
    message_head_outcome = {}
    
    def __init__(self):
        global slash

        config = configparser.ConfigParser()
        config.read('config.ini')        
        self.userIdBotFailyV = int(config['Role']['BotFailyV'])
        self.token = config['Discord']['Token']

        self.con = sqlite3.connect('database.db')
        self.cur = self.con.cursor()

        self.permissions = {}
        self.guild_ids = []
        guilds = self.cur.execute("SELECT guildId, id FROM guilds")
        for rowGuilds in guilds.fetchall():
            self.guild_ids.append((int(rowGuilds[0])))
            roles_ids = []
            roles = self.cur.execute("SELECT roleId FROM roles LEFT JOIN rolesType ON roles.type = rolesType.id WHERE rolesType.usage = 'Staff' AND guildId = ?" ,(rowGuilds[1],))
            for rowRoles in roles.fetchall():
                roles_ids.append(create_permission(int(rowRoles[0]), SlashCommandPermissionType.ROLE, True))
            roles_ids.append(create_permission(650295737308938322, SlashCommandPermissionType.USER, True))
            self.permissions[int(rowGuilds[0])] = roles_ids

            
        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)       
        slash = SlashCommand(self.client, sync_commands=True)
        
        self.on_ready = self.client.event(self.on_ready)
        self.on_raw_reaction_add = self.client.event(self.on_raw_reaction_add)
              
        self.client.loop.create_task(self.background_task())
    
    async def retreive_contract_discord(self):
        guilds = self.cur.execute("SELECT id, guildId FROM guilds")
        for rowGuilds in guilds.fetchall():
            channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id WHERE channelsType.usage = 'RapportFailyV' AND guildId = ?", (rowGuilds[0],))
            amount_income = 0
            amount_outcome = 0
            amount_depense_deduc = 0
            amount_depense_nondeduc = 0
            amount_impot = 0
            amount_remaining = 0
            amount_entreprise = 0

            messages = await self.client.get_channel(channels.fetchone()[0]).history(limit=7*2*3).flatten() # 7 days

            for msg in messages:
                if(msg.author.id == self.userIdBotFailyV):
                    embeds = msg.embeds
                    for embed in embeds:
                        if(embed.title == "Détails Financier"):
                            for field in embed.fields:
                                if(field.name == "Argent Gagné (Factures)"):
                                    amount_income = amount_income + int(field.value[3:-5])
                                elif(field.name == "Argent Gagné (Fourrières)"):
                                    amount_income = amount_income + int(field.value[3:-5])
                                elif(field.name == "Argent Dépensé (Radar Automatique)"):
                                    amount_outcome = amount_outcome - int(field.value[3:-5])
                                elif(field.name == "Argent Dépensé (Salaires Total)"):
                                    amount_outcome = amount_outcome - int(field.value[3:-5])

        guilds = self.cur.execute("SELECT id, guildId FROM guilds")
        for rowGuilds in guilds.fetchall():
            contracts = self.cur.execute("SELECT amount, company, paid, positive, deduc FROM contracts WHERE guildId = ?", (rowGuilds[0],))
            for rowContract in contracts:
                if(rowContract[0] != 0 and rowContract[3] == False and rowContract[2] == True):
                    if(rowContract[4] == False):
                        amount_depense_nondeduc = amount_depense_nondeduc + rowContract[0]
                    elif(rowContract[1] != "Impôts" and rowContract[1] != "Bénéfices"):
                        amount_depense_deduc = amount_depense_deduc + rowContract[0]
                elif(rowContract[0] != 0 and rowContract[3] == True and rowContract[2] == True):
                    amount_entreprise = amount_entreprise + rowContract[0]

            amount_depense_deduc = amount_depense_deduc

            taux = 0
            if(amount_income - amount_depense_deduc > 300000):
                taux = 15
            elif(amount_income - amount_depense_deduc > 75000):
                taux = 10

            amount_impot = round((amount_income - amount_depense_deduc)*taux/100)
            amount_remaining = amount_income - amount_outcome - amount_depense_deduc - amount_depense_nondeduc - amount_impot

            await self.writePDF(rowGuilds.id, taux, amount_income, amount_impot, amount_entreprise, amount_depense_deduc)

            contracts = self.cur.execute("SELECT id, company, reset, temp FROM contracts WHERE guildId = ?" , (rowGuilds[0],))
            for rowContract in contracts.fetchall():
                if(rowContract[0] == "Impôts"):
                    self.cur.execute("UPDATE contracts SET amount = ? WHERE guildId = ? AND company = ?", (amount_impot, rowGuilds[0], "Impôts"))
                elif(rowContract[1] == "Bénéfices"):
                    self.cur.execute("UPDATE contracts SET amount = ? WHERE guildId = ? AND company = ?", (max(0,amount_remaining), rowGuilds[0], "Bénéfices"))
                self.cur.execute("UPDATE contracts SET paid = ? WHERE guildId = ?", (False, rowGuilds[0],))
                if rowContract[2] == True:
                    self.cur.execute("UPDATE contracts SET amount = ? WHERE guildId = ?", (0, rowGuilds[0],))
                if rowContract[3] == True:
                    self.cur.execute("DELETE FROM contracts WHERE id = ?", (rowContract[0],))

            await bot.update_contract(rowGuilds[0])

    async def writePDF(self, guildId, taux, amount_income, amount_impot, amount_entreprise, amount_depense_deduc):
        if platform == "linux" or platform == "linux2":
            locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
        elif platform == "win32":
            locale.setlocale(locale.LC_ALL, 'fr_FR')

        self.cur.execute("SELECT id FROM guilds WHERE guildId = ?" , (guildId,))
        rowGuild = self.cur.fetchone()

        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.rect(5.0, 5.0, 200.0,287.0)
        pdf.image("logo.png", link='', type='', x=70.0, y=6.0, h=1920/80)

        pdf.set_xy(100.0,30.0)
        pdf.set_font('Arial', 'B', 20)
        pdf.set_text_color(50, 50, 220)
        pdf.cell(w=10.0, h=10.0, align='C', txt="Feuille d'Impôts", border=0)

        now = datetime.now()
        monday = now - timedelta(days = now.weekday() + 7)
        sunday = monday + timedelta(days = 6)
        pdf.set_xy(100.0, 40.0)
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(w=10.0, h=10.0, align='C', txt="Du " + monday.strftime("%d %B %Y") + " au " + sunday.strftime("%d %B %Y"), border=0)

        pdf.set_xy(100.0,55.0)
        pdf.set_font('Arial', '', 15)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Chiffre d'affaire Net", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt=str(max(0, amount_income - amount_depense_deduc)) + " $", border=0)

        pdf.set_xy(100.0,62.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Taux d'imposition", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt=str(taux) + " %", border=0)
        pdf.set_xy(100.0,69.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Impôts", border=0)
        pdf.set_font('Arial', 'B', 15)
        pdf.set_text_color(210.0, 50, 50)
        pdf.cell(w=10.0, h=10.0, align='L', txt=str(amount_impot) + " $", border=0)

        pdf.set_font('Arial', '', 15)
        pdf.set_text_color(50, 50, 50)
        pdf.set_xy(100.0,85.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Chiffre d'affaire Entreprises", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt=str(amount_entreprise) + " $", border=0)

        pdf.set_xy(100.0,92.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Dépense déductibles", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt=str(amount_depense_deduc) + " $", border=0)

        pdf.set_font('Arial', 'B', 15)
        pdf.set_xy(100.0, 105.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Détails Recettes", border=0)
        i = 0.0
        pdf.set_font('Arial', '', 13)

        contracts = self.cur.execute("SELECT company, amount, positive, paid, deduc FROM contracts WHERE guildId = ?", (rowGuild.id,))
        for rowContract in contracts.fetchall():
            if(rowContract[1] != 0 and rowContract[2] == True and rowContract[3] == True):
                pdf.set_xy(100.0, 110 + i)
                pdf.cell(w=10.0, h=10.0, align='R', txt=rowContract[0], border=0)
                pdf.cell(w=10.0, h=10.0, align='L', txt=str(rowContract[1]) + " $", border=0)
                i = i + 5

        pdf.set_font('Arial', 'B', 15)
        pdf.set_xy(100.0, i+120)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Détails Dépenses déductibles", border=0)
        pdf.set_font('Arial', '', 13)

        for rowContract in contracts.fetchall():
            if(rowContract[1] != 0 and rowContract[2] == False and rowContract[4] == True and rowContract[3] == True and rowContract[0] != "Impôts" and rowContract[0] != "Bénéfices"):
                pdf.set_xy(100.0, 125 + i)
                pdf.cell(w=10.0, h=10.0, align='R', txt=rowContract[0], border=0)
                pdf.cell(w=10.0, h=10.0, align='L', txt=str(rowContract[1]) + " $", border=0)
                i = i + 5

        pdf.output('Impots_Hebdo.pdf','F')
        await self.client.get_channel(rowGuild.guildId).send(file=discord.File('Impots_Hebdo.pdf'))

    async def background_task(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await asyncio.sleep(50)
            now = datetime.now().time()
            if(datetime.now().weekday() == 0 and now.hour == 3 and now.minute == 0):
                await bot.retreive_contract_discord()
     
    async def update_head(self, guildId):
        embedEncaissement=discord.Embed(title="Encaissement", color=COLOR_GREEN)

        contracts = self.cur.execute("SELECT company, amount, positive, paid, deduc, temp, reset FROM contracts  LEFT JOIN guilds ON contracts.guildId = guilds.id WHERE guilds.guildId = ?", (guildId,))
        for rowContract in contracts.fetchall():
            name = ""
            if(rowContract[2] == False):
                continue
            name = name + rowContract[0]

            amount = str(rowContract[1])
            if(rowContract[3] == True):
                amount = amount + " ✅"
            embedEncaissement.add_field(name=name, value=amount, inline=False)
        try:
            await self.message_head_income[guildId].edit(embed = embedEncaissement)
        except:
            channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'ContratPatron' AND guilds.guildId = ?", (guildId,))
            channelContratPatron = channels.fetchone()[0]
            self.message_head_income[guildId] = await self.client.get_channel(channelContratPatron).send(embed=embedEncaissement)

        contracts = self.cur.execute("SELECT company, amount, positive, paid, deduc, temp, reset FROM contracts  LEFT JOIN guilds ON contracts.guildId = guilds.id WHERE guilds.guildId = ?", (guildId,))
        embedPaiement=discord.Embed(title="Paiement", color=COLOR_RED)
        for rowContract in contracts.fetchall():
            name = ""
            if(rowContract[2] == True):
                continue
            if(rowContract[4] == True):
                name = name + "💰 "
            if(rowContract[6] == False and rowContract[5] == False):
                name = name + "🔄 "
            if(rowContract[5] == True):
                name = name + "♻ "
            name = name + rowContract[0]
            
            amount = str(rowContract[1])
            if(rowContract[3] == True):
                amount = amount + " ✅"
            embedPaiement.add_field(name=name, value=amount, inline=False)
        try:
            await self.message_head_outcome[guildId].edit(embed = embedPaiement)
        except:
            channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'ContratPatron' AND guilds.guildId = ?", (guildId,))
            channelContratPatron = channels.fetchone()[0]
            self.message_head_outcome[guildId] = await self.client.get_channel(channelContratPatron).send(embed=embedPaiement)

    async def update_contract(self, guildId):
        self.con.commit()

        channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'Contrat' AND guilds.guildId =  ?", (guildId,))
        channelContrat = channels.fetchone()[0]
        channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'ContratPatron' AND guilds.guildId = ?", (guildId,))
        channelContratPatron = channels.fetchone()[0]
        await self.client.get_channel(channelContrat).purge()
        await self.client.get_channel(channelContratPatron).purge()

        await self.update_head(guildId)

        contracts = self.cur.execute("SELECT company, amount, paid, positive FROM contracts LEFT JOIN guilds ON contracts.guildId = guilds.id WHERE guilds.guildId = ?", (guildId,))
        for rowContract in contracts.fetchall():
            if(rowContract[1] != 0):
                if(rowContract[2] == False):
                    if(rowContract[3] == True):
                        embedVar = discord.Embed(title=rowContract[0], description = str(rowContract[1]) + "$", color=COLOR_GREEN)
                        msg = await self.client.get_channel(channelContrat).send(embed=embedVar)
                        await msg.add_reaction("✅")
                    else:
                        embedVar = discord.Embed(title=rowContract[0], description = str(rowContract[1]) + "$", color=COLOR_RED)
                        msg = await self.client.get_channel(channelContratPatron).send(embed=embedVar)
                        await msg.add_reaction("✅")
    
    async def on_ready(self):
        print(str(self.client.user) + " has connected to Discord")
        print("Bot ID is " + str(self.client.user.id))

        guilds = self.cur.execute("SELECT id, guildId FROM guilds")
        for rowGuilds in guilds.fetchall():
            await self.update_contract(rowGuilds[1])
        await self.client.wait_until_ready()
        print(str(self.client.user) + " is now ready!")
    
    async def on_raw_reaction_add(self, payload):
        try:
            guild = self.client.get_guild(payload.guild_id)
            user = guild.get_member(payload.user_id)
            
            if user == self.client.user:
                return
            
            channel = self.client.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            
            if(payload.emoji.name == "✅"):
                guilds = self.cur.execute("SELECT id, guildId FROM guilds")
                for rowGuilds in guilds.fetchall():
                    if(rowGuilds[1] == payload.guild_id):
                        contracts = self.cur.execute("SELECT company, positive, paid FROM contracts WHERE guildId = ?", (rowGuilds[0],))
                        for rowContract in contracts.fetchall():
                            if(rowContract[2] == False and rowContract[0] in message.embeds[0].title):
                                usages = self.cur.execute("SELECT USAGE FROM channelsType LEFT JOIN channels ON channelsType.id = channels.type WHERE channels.channelId = ?", (payload.channel_id,))
                                positive = True
                                if(usages.fetchone()[0] == "ContratPatron"):
                                    positive = False

                                self.cur.execute("UPDATE contracts SET paid = ? WHERE guildId = ? AND company = ? AND positive = ?", (True, rowGuilds[0], message.embeds[0].title, positive, ))
                                bot.con.commit()
                                await message.delete()

                                channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id WHERE channelsType.usage = 'LogContrat' AND guildId = ?", (rowGuilds[0],))
                                if(positive == True):
                                    await self.client.get_channel(channels.fetchone()[0]).send("🟢 Le **Contrat " + message.embeds[0].title + "** de " + message.embeds[0].description + " a été encaissé par " +  user.display_name)
                                else:
                                    await self.client.get_channel(channels.fetchone()[0]).send("🔴 Le **Contrat " + message.embeds[0].title + "** de " + message.embeds[0].description + " a été payé par " +  user.display_name)
                                await self.update_head(payload.guild_id)
                        
        except discord.errors.NotFound:
            pass
    
    def run(self):
        print("Starting bot ...")
        self.client.run(self.token)

bot = Bot()

@slash.slash(
    name="ajouterContrat",
    description="Ajoute un contrat",
    default_permission = False,
    permissions=bot.permissions,
    options = [{
        "name": "entreprise",
        "description": "Entreprise pour lequel ajouter le Contrat",
        "type": 3,
        "required": True
    },{
        "name": "montant",
        "description": "Montant du contrat",
        "type": 4,
        "required": True
    },{
        "name": "typec",
        "description": "Type du contrat",
        "type": 4,
        "required": True,
        "choices": [{
            "name": "Contrat récurrent à payer",
            "value": 0
            },{
            "name": "Contrat récurrent à encaisser",
            "value": 1
            },{
            "name": "Contrat récurrent non déductible à payer",
            "value": 2
            },{
            "name": "Contrat non déductible à payer",
            "value": 3
            },{
            "name": "Contrat déductible à payer",
            "value": 4
            },{
            "name": "Dépense déductible",
            "value": 5
            },{
            "name": "Dépense non déductible",
            "value": 6
        }]
    }],
    guild_ids=bot.guild_ids)
async def _ajouterContrat(ctx: SlashContext, entreprise: str, montant: int, typec: bool):
    await ctx.defer(hidden=True)   
    
    positive = False
    deduc = True
    reset = False
    temp = False

    if(typec == 1):
        positive = True
    if(typec == 2):
        deduc = False
    elif(typec == 3):
        deduc = False
        reset = True
    elif(typec == 4):
        reset = True
    elif(typec == 5):
        temp = True
    elif(typec == 6):
        deduc = False
        temp = True

    bot.cur.execute("INSERT INTO contracts (guildId, company, amount, paid, positive, deduc, reset, temp) SELECT id, ?, ?, ?, ?, ?, ?, ? FROM guilds WHERE guildId = ?", (entreprise, montant, False, positive, deduc, reset, temp, ctx.guild_id))
    await bot.update_contract(ctx.guild_id)
    await ctx.send(content="Contrat " + entreprise + " ajouté !",hidden=True)

@slash.slash(
    name="modifierContrat",
    description="Modifie un contrat existant",
    default_permission = False,
    permissions=bot.permissions,
    options = [{
        "name": "entreprise",
        "description": "Entreprise pour lequel changer le Contrat",
        "type": 3,
        "required": True
    },{
        "name": "montant",
        "description": "Montant du contrat",
        "type": 4,
        "required": True
    }],
    guild_ids=bot.guild_ids)
async def _modifierContrat(ctx: SlashContext, entreprise: str, montant: int):
    await ctx.defer(hidden=True)    
    bot.cur.execute("UPDATE contracts SET amount = (CASE WHEN reset = True THEN amount + ? ELSE ? END) WHERE guildId = (SELECT id FROM guilds WHERE guildId = ?) AND company = ?", (montant, montant, ctx.guild_id, entreprise))
    await bot.update_contract(ctx.guild_id)
    await ctx.send(content="Contrat " + entreprise + " modifié !",hidden=True)

@slash.slash(
    name="supprimerContrat",
    description="Supprime un contrat existant",
    default_permission = False,
    permissions=bot.permissions,
    options = [{
        "name": "entreprise",
        "description": "Entreprise pour lequel supprimer le Contrat",
        "type": 3,
        "required": True
    }],
    guild_ids=bot.guild_ids)
async def _supprimerContrat(ctx: SlashContext, entreprise: str):
    await ctx.defer(hidden=True)   
    bot.cur.execute("DELETE FROM contracts WHERE guildId = (SELECT id FROM guilds WHERE guildId = ?) AND company = ?", (ctx.guild_id, entreprise))
    await bot.update_contract(ctx.guild_id)
    await ctx.send(content="Contrat " + entreprise + " supprimé !",hidden=True)
        
@slash.slash(
    name="rechargerContrat",
    description="Recharge les contrats",
    default_permission = False,
    permissions=bot.permissions,
    options = [],
    guild_ids=bot.guild_ids)
async def _rechargerContrat(ctx: SlashContext):
    await ctx.defer(hidden=True)   
    await bot.update_contract(ctx.guild_id)
    await ctx.send(content="Contrat rechargés !",hidden=True)


bot.run()
