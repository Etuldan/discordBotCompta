# bot.py
# python3 -m pip install discord.py discord-py-interactions fpdf

import discord
import discord_slash

from discord_slash.utils.manage_components import create_button, create_actionrow, wait_for_component, ComponentContext
from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import ButtonStyle, SlashCommandPermissionType
from discord_slash import SlashContext, SlashCommand

import sys
import psutil
import locale
import fpdf
import datetime
import requests

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

        self.permissionsEmployee = {}
        self.permissionsStaff = {}
        self.permissionsAdmin = {}
        self.guild_ids = []
        self.roleService = {}
        self.channelLogService = {}
        self.channelVente ={}
        self.messageStock = {}
        guilds = self.cur.execute("SELECT guildId, id FROM guilds")
        for rowGuilds in guilds.fetchall():
            self.guild_ids.append((int(rowGuilds[0])))

            # Permissions
            rolesStaffId = []
            rolesEmployeeId = []

            roles = self.cur.execute("SELECT roleId FROM roles LEFT JOIN rolesType ON roles.type = rolesType.id WHERE rolesType.usage = 'Staff' AND guildId = ?" ,(rowGuilds[1],))
            for rowRoles in roles.fetchall():
                rolesStaffId.append(create_permission(int(rowRoles[0]), SlashCommandPermissionType.ROLE, True))
            rolesStaffId.append(create_permission(650295737308938322, SlashCommandPermissionType.USER, True))
            self.permissionsStaff[int(rowGuilds[0])] = rolesStaffId

            roles = self.cur.execute("SELECT roleId FROM roles LEFT JOIN rolesType ON roles.type = rolesType.id WHERE rolesType.usage = 'Employé' AND guildId = ?" ,(rowGuilds[1],))
            for rowRoles in roles.fetchall():
                rolesEmployeeId.append(create_permission(int(rowRoles[0]), SlashCommandPermissionType.ROLE, True))
            rolesEmployeeId.append(create_permission(650295737308938322, SlashCommandPermissionType.USER, True))
            self.permissionsEmployee[int(rowGuilds[0])] = rolesEmployeeId

            self.permissionsAdmin[int(rowGuilds[0])] = [create_permission(650295737308938322, SlashCommandPermissionType.USER, True)]
            # Permissions

            # PDS
            roles = self.cur.execute("SELECT roleId FROM roles LEFT JOIN rolesType ON roles.type = rolesType.id WHERE rolesType.usage = 'Service' AND guildId = ?" ,(rowGuilds[1],))
            self.roleService[int(rowGuilds[0])] = roles.fetchone()
            channel = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id WHERE channelsType.usage = 'Log Prise de Service' AND guildId = ?", (rowGuilds[1],))
            self.channelLogService[int(rowGuilds[0])] = channel.fetchone()
            # PDS

            # Vente
            channel = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id WHERE channelsType.usage = 'Vente' AND guildId = ?", (rowGuilds[1],))
            self.channelVente[int(rowGuilds[0])] = channel.fetchone()
            # Vente

            # Items
            self.choice = []
            items = self.cur.execute("SELECT name FROM items WHERE guildId = ?", (rowGuilds[1],))
            for item in items.fetchall():
                self.choice.append({"name": item[0], "value": item[0]})
            # Items

        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)       
        slash = SlashCommand(self.client, sync_commands=True)

        self.on_ready = self.client.event(self.on_ready)
        self.on_raw_reaction_add = self.client.event(self.on_raw_reaction_add)
        self.on_component = self.client.event(self.on_component)
              
        self.client.loop.create_task(self.background_task())
    
    async def update_farm(self):
        guilds = self.cur.execute("SELECT id, guildId FROM guilds")
        for rowGuilds in guilds.fetchall():
            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days = 1)
            dt = datetime.datetime.combine(yesterday, datetime.time())
            channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id WHERE channelsType.usage = 'RapportFailyV' AND guildId = ?", (rowGuilds[0],))
            messages = await self.client.get_channel(channels.fetchone()[0]).history(limit=100, after=dt).flatten()

            for msg in messages:
                if(msg.author.id == self.userIdBotFailyV):
                    embeds = msg.embeds
                    for embed in embeds:
                        if(embed.title == "Détails Tâches"):
                            for field in embed.fields:
                                employee = field.name
                                farm = int(field.value.split("**")[1])

    async def update_taxes(self):
        guilds = self.cur.execute("SELECT id, guildId FROM guilds")
        for rowGuilds in guilds.fetchall():
            amount_income = 0
            amount_outcome = 0
            amount_depense_deduc = 0
            amount_depense_nondeduc = 0
            amount_impot = 0
            amount_remaining = 0
            amount_entreprise = 0

            today = datetime.date.today()
            last_tuesday = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days = 1)
            dt = datetime.datetime.combine(last_tuesday, datetime.time())
            channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id WHERE channelsType.usage = 'RapportFailyV' AND guildId = ?", (rowGuilds[0],))
            messages = await self.client.get_channel(channels.fetchone()[0]).history(limit=100, after=dt).flatten()

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

            contracts = self.cur.execute("SELECT amount, company, paid, positive, deduc FROM contracts WHERE guildId = ?", (rowGuilds[0],))
            for rowContract in contracts:
                if(rowContract[0] != 0 and rowContract[3] == 0 and rowContract[2] == 1):
                    if(rowContract[4] == 0):
                        amount_depense_nondeduc = amount_depense_nondeduc + rowContract[0]
                    elif(rowContract[1] != "Impôts" and rowContract[1] != "Bénéfices"):
                        amount_depense_deduc = amount_depense_deduc + rowContract[0]
                elif(rowContract[0] != 0 and rowContract[3] == 1 and rowContract[2] == 1):
                    amount_entreprise = amount_entreprise + rowContract[0]

            amount_depense_deduc = amount_depense_deduc

            taux = 0
            if(amount_income - amount_depense_deduc > 300000):
                taux = 15
            elif(amount_income - amount_depense_deduc > 75000):
                taux = 10

            amount_impot = round((amount_income - amount_depense_deduc)*taux/100)
            amount_remaining = amount_income - amount_outcome - amount_depense_deduc - amount_depense_nondeduc - amount_impot

            await self._writePDF(rowGuilds[0], taux, amount_income, amount_impot, amount_entreprise, amount_depense_deduc)

            contracts = self.cur.execute("SELECT company, reset, temp, id FROM contracts WHERE guildId = ?" , (rowGuilds[0],))
            for rowContract in contracts.fetchall():
                if(rowContract[0] == "Impôts"):
                    self.cur.execute("UPDATE contracts SET amount = ? WHERE guildId = ? AND company = ? AND id = ?", (amount_impot, rowGuilds[0], "Impôts", rowContract[3],))
                elif(rowContract[0] == "Bénéfices"):
                    self.cur.execute("UPDATE contracts SET amount = ? WHERE guildId = ? AND company = ? AND id = ?", (max(0,amount_remaining), rowGuilds[0], "Bénéfices", rowContract[3],))
                
                if rowContract[1] == 1:
                    self.cur.execute("UPDATE contracts SET amount = ? WHERE guildId = ? AND id = ?", (0, rowGuilds[0],rowContract[3],))
                if rowContract[2] == 1:
                    self.cur.execute("DELETE FROM contracts WHERE guildId = ? AND id = ?", (rowGuilds[0], rowContract[3],))

            self.cur.execute("UPDATE contracts SET paid = ? WHERE guildId = ?", (0, rowGuilds[0],))
            await bot.update_contract(rowGuilds[1])

    async def _writePDF(self, guildId: int, taux: int, amount_income: int, amount_impot: int, amount_entreprise: int, amount_depense_deduc: int):
        if sys.platform == "linux" or sys.platform == "linux2":
            locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
        elif sys.platform == "win32":
            locale.setlocale(locale.LC_ALL, 'fr_FR')

        pdf = fpdf.FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.rect(5.0, 5.0, 200.0,287.0)
        #pdf.image("logo.png", link='', type='', x=70.0, y=6.0, h=1920/80)

        pdf.set_xy(100.0,30.0)
        pdf.set_font('Arial', 'B', 20)
        pdf.set_text_color(50, 50, 220)
        pdf.cell(w=10.0, h=10.0, align='C', txt="Feuille d'Impôts", border=0)

        now = datetime.datetime.now()
        monday = now - datetime.timedelta(days = now.weekday() + 7)
        sunday = monday + datetime.timedelta(days = 6)
        pdf.set_xy(100.0, 40.0)
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(w=10.0, h=10.0, align='C', txt="Du {} au {}".format(monday.strftime("%d %B %Y"), sunday.strftime("%d %B %Y")), border=0)

        pdf.set_xy(100.0,55.0)
        pdf.set_font('Arial', '', 15)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Chiffre d'affaire Net", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt="{} $".format(max(0, amount_income - amount_depense_deduc)), border=0)

        pdf.set_xy(100.0,62.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Taux d'imposition", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt="{} %".format(taux), border=0)
        pdf.set_xy(100.0,69.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Impôts", border=0)
        pdf.set_font('Arial', 'B', 15)
        pdf.set_text_color(210.0, 50, 50)
        pdf.cell(w=10.0, h=10.0, align='L', txt="{} $".format(amount_impot), border=0)

        pdf.set_font('Arial', '', 15)
        pdf.set_text_color(50, 50, 50)
        pdf.set_xy(100.0,85.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Chiffre d'affaire Entreprises", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt="{} $".format(amount_entreprise), border=0)

        pdf.set_xy(100.0,92.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Dépense déductibles", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt="{} $".format(amount_depense_deduc), border=0)

        pdf.set_font('Arial', 'B', 15)
        pdf.set_xy(100.0, 105.0)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Détails Recettes", border=0)
        i = 0.0
        pdf.set_font('Arial', '', 13)

        contracts = self.cur.execute("SELECT company, amount, positive, paid, deduc FROM contracts WHERE guildId = ?", (guildId,))
        for rowContract in contracts.fetchall():
            if(rowContract[1] != 0 and rowContract[2] == 1 and rowContract[3] == 1):
                pdf.set_xy(100.0, 110 + i)
                pdf.cell(w=10.0, h=10.0, align='R', txt=rowContract[0], border=0)
                pdf.cell(w=10.0, h=10.0, align='L', txt="{} $".format(rowContract[1]), border=0)
                i = i + 5

        pdf.set_font('Arial', 'B', 15)
        pdf.set_xy(100.0, i+120)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Détails Dépenses déductibles", border=0)
        pdf.set_font('Arial', '', 13)

        contracts = self.cur.execute("SELECT company, amount, positive, paid, deduc FROM contracts WHERE guildId = ?", (guildId,))
        for rowContract in contracts.fetchall():
            if(rowContract[1] != 0 and rowContract[2] == 0 and rowContract[4] == 1 and rowContract[3] == 1 and rowContract[0] != "Impôts" and rowContract[0] != "Bénéfices"):
                pdf.set_xy(100.0, 125 + i)
                pdf.cell(w=10.0, h=10.0, align='R', txt=rowContract[0], border=0)
                pdf.cell(w=10.0, h=10.0, align='L', txt="{} $".format(rowContract[1]), border=0)
                i = i + 5

        pdf.output('Impots_Hebdo.pdf','F')
        channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id WHERE channelsType.usage = 'Compta' AND channels.guildId = ?", (guildId,))
        await self.client.get_channel(channels.fetchone()[0]).send(file=discord.File('Impots_Hebdo.pdf'))

    async def background_task(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await asyncio.sleep(50)
            now = datetime.datetime.now().time()
            if(datetime.datetime.now().weekday() == 0 and now.hour == 7 and now.minute == 0):
                await bot.update_taxes()
            if(now.hour == 7 and now.minute == 10):
                await bot.update_farm()
     
    async def update_head_contracts(self, guildId: int):
        embedEncaissement=discord.Embed(title="Encaissement", color=COLOR_GREEN)

        contracts = self.cur.execute("SELECT company, amount, positive, paid, deduc, temp, reset FROM contracts  LEFT JOIN guilds ON contracts.guildId = guilds.id WHERE guilds.guildId = ?", (guildId,))
        for rowContract in contracts.fetchall():
            name = ""
            if(rowContract[2] == False):
                continue
            name = name + rowContract[0]

            amount = str(rowContract[1])
            if(rowContract[3] == True):
                amount = "{} ✅".format(amount)
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
                name = "{}💰 ".format(name)
            if(rowContract[6] == False and rowContract[5] == False):
                name = "{}🔄 ".format(name)
            if(rowContract[5] == True):
                name = "{}♻ ".format(name)
            name = name + rowContract[0]
            
            amount = str(rowContract[1])
            if(rowContract[3] == True):
                amount = "{} ✅".format(amount)
            embedPaiement.add_field(name=name, value=amount, inline=False)
        try:
            await self.message_head_outcome[guildId].edit(embed = embedPaiement)
        except:
            channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'ContratPatron' AND guilds.guildId = ?", (guildId,))
            channelContratPatron = channels.fetchone()[0]
            self.message_head_outcome[guildId] = await self.client.get_channel(channelContratPatron).send(embed=embedPaiement)

    async def update_contract(self, guildId: int):
        self.con.commit()

        channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'Contrat' AND guilds.guildId =  ?", (guildId,))
        channelContrat = channels.fetchone()[0]
        channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'ContratPatron' AND guilds.guildId = ?", (guildId,))
        channelContratPatron = channels.fetchone()[0]
        await self.client.get_channel(channelContrat).purge()
        await self.client.get_channel(channelContratPatron).purge()

        await self.update_head_contracts(guildId)

        contracts = self.cur.execute("SELECT company, amount, paid, positive FROM contracts LEFT JOIN guilds ON contracts.guildId = guilds.id WHERE guilds.guildId = ?", (guildId,))
        buttons = []
        for rowContract in contracts.fetchall():
            if(rowContract[1] != 0):
                if(rowContract[2] == False):
                    if(rowContract[3] == True):
                        embedVar = discord.Embed(title=rowContract[0], description = "{}$".format(rowContract[1]), color=COLOR_GREEN)
                        msg = await self.client.get_channel(channelContrat).send(embed=embedVar)
                        await msg.add_reaction("✅")
                    else:
                        embedVar = discord.Embed(title=rowContract[0], description = "{}$".format(rowContract[1]), color=COLOR_RED)
                        msg = await self.client.get_channel(channelContratPatron).send(embed=embedVar)
                        await msg.add_reaction("✅")
    
    async def update_PDS(self, guildId: int):
        channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'Prise de Service' AND guilds.guildId = ?", (guildId,))
        channelPDS = channels.fetchone()
        if channelPDS != None:
            await self.client.get_channel(channelPDS[0]).purge()
            buttons = [
                create_button(style=ButtonStyle.green, label="Prise de Service", custom_id="PDS"),
                create_button(style=ButtonStyle.blue, label="Fin de Service", custom_id="FDS"),
            ]
            action_row = create_actionrow(*buttons)
            await self.client.get_channel(channelPDS[0]).send(components=[action_row])

    async def update_stock(self, updateList: bool, guildId: int):
        if(guildId == 0):
            guilds = self.cur.execute("SELECT guildId FROM guilds")
            for rowGuilds in guilds.fetchall():
                await self.update_stock(True, rowGuilds[0])
            return

        if(updateList):
            self.choice = []
            items = self.cur.execute("SELECT name FROM items WHERE guildId = (SELECT id FROM guilds WHERE guildId = ?)", (guildId,))
            for item in items.fetchall():
                self.choice.append({"name": item[0], "value": item[0]})

            slash.commands['stockajout'].options[0]['choices'] = self.choice
            slash.commands['stockretrait'].options[0]['choices'] = self.choice
            slash.commands['stockgestiondel'].options[0]['choices'] = self.choice
            slash.commands['stockgestionquantity'].options[0]['choices'] = self.choice
            slash.commands['stockgestionseuil'].options[0]['choices'] = self.choice
            await slash.sync_all_commands()

        channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id LEFT JOIN guilds on channels.guildId = guilds.id WHERE channelsType.usage = 'Stock' AND guilds.guildId = ?", (guildId,))
        channelStock = channels.fetchone()
        if channelStock != None:
            embedStock=discord.Embed(title="Etat des Stocks", color=COLOR_GREEN)
            items = self.cur.execute("SELECT items.name, quantity, maxQuantity, threshold FROM items LEFT JOIN guilds ON items.guildId = guilds.id WHERE guilds.guildId = ?", (guildId,))
            itemNames = ""
            itemsquantity = ""
            for rowItems in items.fetchall():
                if(rowItems[1] >= rowItems[3]):
                    itemNames = "{}:green_circle: {} \n".format(itemNames, rowItems[0])
                else:
                    itemNames = "{}:green_circle: {} \n".format(itemNames, rowItems[0])
                itemsquantity = "{}{}/{}\n".format(itemsquantity, rowItems[1], rowItems[2])

            embedStock.add_field(name="Nom", value=itemNames, inline=True)
            embedStock.add_field(name="Quantité", value=itemsquantity, inline=True)

            if self.messageStock == {}:
                await self.client.get_channel(channelStock[0]).purge()
                self.messageStock[guildId] = await self.client.get_channel(channelStock[0]).send(embed=embedStock)
            else:
                await self.messageStock[guildId].edit(embed=embedStock)

    async def add_items(self, guildId: int, user, quantity: int):
        pass
    
    async def on_ready(self):
        print("{} has connected to Discord".format(self.client.user))
        print("Bot ID is {}".format(self.client.user.id))

        await self.update_stock(True, 0)

        guilds = self.cur.execute("SELECT id, guildId FROM guilds")
        for rowGuilds in guilds.fetchall():
            await self.update_contract(rowGuilds[1])
            await self.update_PDS(rowGuilds[1])
        await self.client.wait_until_ready()

        print("{} is now ready!".format(self.client.user))

    async def on_component(self, ctx: ComponentContext):
        await ctx.defer(hidden= True, ignore = True)
        if(ctx.component["label"] == "Prise de Service"):
            await ctx.author.add_roles(ctx.guild.get_role(self.roleService[ctx.guild_id][0]))
            await self.client.get_channel(self.channelLogService[ctx.guild_id][0]).send(content=":green_circle: PDS de {}".format(ctx.author.display_name))
        elif(ctx.component["label"] == "Fin de Service"):
            await ctx.author.remove_roles(ctx.guild.get_role(self.roleService[ctx.guild_id][0]))
            await self.client.get_channel(self.channelLogService[ctx.guild_id][0]).send(content=":blue_circle: FDS de {}".format(ctx.author.display_name))

    async def on_raw_reaction_add(self, payload):
        try:
            if(payload.emoji.name == "✅"):
                guild = self.client.get_guild(payload.guild_id)
                user = guild.get_member(payload.user_id)

                if user == self.client.user:
                    return

                channel = self.client.get_channel(payload.channel_id)
                message = await channel.fetch_message(payload.message_id)

                guilds = self.cur.execute("SELECT id, guildId FROM guilds")
                for rowGuilds in guilds.fetchall():
                    if(rowGuilds[1] == payload.guild_id):
                        channels = self.cur.execute("SELECT channelId FROM channels LEFT JOIN channelsType ON channels.type = channelsType.id WHERE guildId = ? AND (channelsType.usage = 'Contrat' OR channelsType.usage = 'ContratPatron')", (rowGuilds[0],))
                        for channelSQL in channels.fetchall():
                            if(channelSQL[0] == payload.channel_id):
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
                                            await self.client.get_channel(channels.fetchone()[0]).send("🟢 Le **Contrat {}** de {} a été encaissé par {}".format(message.embeds[0].title, message.embeds[0].description, user.display_name))
                                        else:
                                            await self.client.get_channel(channels.fetchone()[0]).send("🔴 Le **Contrat {}** de {} a été payé par {}".format(message.embeds[0].title, message.embeds[0].description, user.display_name))
                        await self.update_head_contracts(payload.guild_id)
                        
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
    permissions=bot.permissionsStaff,
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
    
    positive = 0
    deduc = 1
    reset = 0
    temp = 0

    if(typec == 1):
        positive = 1
    if(typec == 2):
        deduc = 0
    elif(typec == 3):
        deduc = 0
        reset = 1
    elif(typec == 4):
        reset = 1
    elif(typec == 5):
        temp = 1
    elif(typec == 6):
        deduc = 0
        temp = 1

    bot.cur.execute("INSERT INTO contracts (guildId, company, amount, paid, positive, deduc, reset, temp) SELECT id, ?, ?, ?, ?, ?, ?, ? FROM guilds WHERE guildId = ?", (entreprise, montant, False, positive, deduc, reset, temp, ctx.guild_id))
    await bot.update_contract(ctx.guild_id)
    await ctx.send(content="Contrat {} ajouté !".format(entreprise),hidden=True)

@slash.slash(
    name="modifierContrat",
    description="Modifie un contrat existant",
    default_permission = False,
    permissions=bot.permissionsStaff,
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
    bot.cur.execute("UPDATE contracts SET amount = (CASE WHEN reset = 1 THEN amount + ? ELSE ? END) WHERE guildId = (SELECT id FROM guilds WHERE guildId = ?) AND company = ?", (montant, montant, ctx.guild_id, entreprise))
    await bot.update_contract(ctx.guild_id)
    await ctx.send(content="Contrat {} modifié !".format(entreprise),hidden=True)

@slash.slash(
    name="supprimerContrat",
    description="Supprime un contrat existant",
    default_permission = False,
    permissions=bot.permissionsStaff,
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
    await ctx.send(content="Contrat {} supprimé !".format(entreprise),hidden=True)
        
@slash.slash(
    name="rechargerContrat",
    description="Recharge les contrats",
    default_permission = False,
    permissions=bot.permissionsStaff,
    options = [],
    guild_ids=bot.guild_ids)
async def _rechargerContrat(ctx: SlashContext):
    await ctx.defer(hidden=True)
    await bot.update_contract(ctx.guild_id)
    await ctx.send(content="Contrat rechargés !",hidden=True)

@slash.slash(
    name="stockAjout",
    description="Ajoute des objets au Stock",
    default_permission = False,
    permissions=bot.permissionsEmployee,
    options = [
        {
            "name": "objet",
            "description": "Type d'objet à ajouter",
            "type": 3,
            "required": True,
            "choices": [] 
        },{
            "name": "montant",
            "description": "Nombre d'objet à ajouter",
            "type": 4,
            "required": True
        }
    ],
    guild_ids=bot.guild_ids
    )
async def _stockAjout(ctx: SlashContext, objet: str, montant: int):
    await ctx.defer(hidden= True)
    itemsData = bot.cur.execute("SELECT quantity, threshold, craft FROM items WHERE name = ? AND guildId = (SELECT id FROM guilds WHERE guildId = ?)", (objet, ctx.guild_id, ))
    itemData = itemsData.fetchone()
    if itemData != None:
        toAdd = max(min(itemData[1] - itemData[0], montant),0)
        if(toAdd > 0):
            await bot.add_items(ctx.guild_id, ctx.author, toAdd * itemData[2])            

    bot.cur.execute("UPDATE items SET quantity = MIN(maxQuantity, quantity + ?) WHERE name = ? AND guildId = (SELECT id FROM guilds WHERE guildId = ?)", (montant, objet, ctx.guild_id, ))
    bot.con.commit()
    await bot.update_stock(False, ctx.guild_id)
    await ctx.send(content="Objet ajouté au stock !",hidden=True)

@slash.slash(
    name="stockRetrait",
    description="Supprime des objets du Stock",
    default_permission = False,
    permissions=bot.permissionsEmployee,
    options = [
        {
            "name": "objet",
            "description": "Type d'objet à supprimer",
            "type": 3,
            "required": True,
            "choices": [] 
        },{
            "name": "montant",
            "description": "Nombre d'objet à supprimer",
            "type": 4,
            "required": True
        }],
    guild_ids=bot.guild_ids
    )
async def _stockRetrait(ctx: SlashContext, objet: str, montant: int):
    await ctx.defer(hidden= True)
    bot.cur.execute("UPDATE items SET quantity = MAX(0, quantity - ?, 0) WHERE name = ? AND guildId = (SELECT id FROM guilds WHERE guildId = ?)", (montant, objet, ctx.guild_id, ))
    bot.con.commit()
    await bot.update_stock(False, ctx.guild_id)
    await ctx.send(content="Objet supprimé du stock !",hidden=True)

@slash.slash(
    name="stockGestionAdd",
    description="Ajoute des nouveaux objets au Stock",
    default_permission = False,
    permissions=bot.permissionsStaff,
    options = [
        {
            "name": "objet",
            "description": "Nom de l'objet à ajouter",
            "type": 3,
            "required": True,  
        },{
            "name": "quantitemax",
            "description": "Quantité maximum de l'objet",
            "type": 4,
            "required": True
        },{
            "name": "seuil",
            "description": "Seuil de stock",
            "type": 4,
            "required": True
        },{
            "name": "craft",
            "description": "Nombre d'objet requis pour fabriquer l'objet",
            "type": 10,
            "required": True
        }],
    guild_ids=bot.guild_ids
    )
async def _stockGestionAdd(ctx: SlashContext, objet: str, quantitemax: int, seuil: int, craft: float):
    await ctx.defer(hidden= True)
    bot.cur.execute("INSERT INTO items ('guildId', 'name', 'maxQuantity', 'threshold', 'craft') VALUES ((SELECT id FROM guilds WHERE guildId = ?), ?, ?, ?, ?)", (ctx.guild_id, objet, quantitemax, seuil, craft, ))
    bot.con.commit()
    await bot.update_stock(True, ctx.guild_id)
    await ctx.send(content="Nouvel objet ajouté au stock !",hidden=True)

@slash.slash(
    name="stockGestionDel",
    description="Supprime un type d'objet du Stock",
    default_permission = False,
    permissions=bot.permissionsStaff,
    options = [
        {
            "name": "objet",
            "description": "Nom de l'objet à supprimer",
            "type": 3,
            "required": True,
            "choices": []
        }],
    guild_ids=bot.guild_ids
    )
async def _stockGestionDel(ctx: SlashContext, objet: str):
    await ctx.defer(hidden= True)
    bot.cur.execute("DELETE FROM items WHERE name = ? AND guildId = (SELECT id FROM guilds WHERE guildId = ?)", (objet, ctx.guild_id, ))
    bot.con.commit()
    await bot.update_stock(True, ctx.guild_id)
    await ctx.send(content="Type d'Objet supprimé du stock !",hidden=True)

@slash.slash(
    name="stockGestionQuantity",
    description="Modifie la quantité maximum d'un objet",
    default_permission = False,
    permissions=bot.permissionsStaff,
    options = [
        {
            "name": "objet",
            "description": "Nom de l'objet à modifier",
            "type": 3,
            "required": True,
            "choices": []
        },{
            "name": "quantite",
            "description": "Nouvelle quantité maximum de l'objet",
            "type": 4,
            "required": True
        }],
    guild_ids=bot.guild_ids
    )
async def _stockGestionQuantity(ctx: SlashContext, objet: str, quantite: int):
    await ctx.defer(hidden= True)
    bot.cur.execute("UPDATE items SET maxQuantity = ? WHERE name = ? AND guildId = (SELECT id FROM guilds WHERE guildId = ?)", (quantite, objet, ctx.guild_id, ))
    bot.con.commit()
    await bot.update_stock(False, ctx.guild_id)
    await ctx.send(content="Quantité maximum de l'objet modifiée !",hidden=True)

@slash.slash(
    name="stockGestionSeuil",
    description="Modifie le seuil d'un objet",
    default_permission = False,
    permissions=bot.permissionsStaff,
    options = [
        {
            "name": "objet",
            "description": "Nom de l'objet à modifier",
            "type": 3,
            "required": True,
            "choices": []
        },{
            "name": "seuil",
            "description": "Nouveau seuil de l'objet",
            "type": 4,
            "required": True
        }],
    guild_ids=bot.guild_ids
)
async def _stockGestionSeuil(ctx: SlashContext, objet: str, seuil: int):
    await ctx.defer(hidden= True)
    bot.cur.execute("UPDATE items SET threshold = ? WHERE name = ? AND guildId = (SELECT id FROM guilds WHERE guildId = ?)", (seuil, objet, ctx.guild_id, ))
    bot.con.commit()
    await bot.update_stock(False, ctx.guild_id)
    await ctx.send(content="Seuil de l'objet modifié !",hidden=True)

@slash.slash(
    name="vente",
    description="Vends un objet",
    default_permission = False,
    permissions=bot.permissionsEmployee,
    options = [
        {
            "name": "prix",
            "description": "Prix de vente",
            "type": 4,
            "required": True
        },{
            "name": "acheteur",
            "description": "Acheteur",
            "type": 3,
            "required": True
        },{
            "name": "description",
            "description": "Information sur les objets vendus",
            "type": 3,
            "required": True
        }],
    guild_ids=bot.guild_ids
)
async def _vente(ctx: SlashContext, prix: int, acheteur: str, description: str):
    await ctx.defer(hidden= True)
    await bot.client.get_channel(bot.channelVente[ctx.guild_id][0]).send(content="Vente de {} à {} pour {}$".format(description, acheteur, prix))
    await ctx.send(content="Vente effectuée",hidden=True)

@slash.slash(
    name="adminForceCompute",
    description="Force le calcul des impots",
    default_permission = False,
    permissions=bot.permissionsAdmin,
    guild_ids=bot.guild_ids
)
async def _adminForceCompute(ctx: SlashContext):
    await ctx.defer(hidden= True)
    await bot.update_taxes(ctx.guild_id)
    await ctx.send(content="Impôts calculés !",hidden=True)

@slash.slash(
    name="adminDebug",
    description="Affiche les infos de Debug",
    default_permission = False,
    permissions=bot.permissionsAdmin,
    guild_ids=bot.guild_ids)
async def _adminDebug(ctx: SlashContext):
    await ctx.defer(hidden=True)
    ip = requests.get('https://checkip.amazonaws.com').text.strip()
    content = "System {}\nDiscord.py {}\ndiscord-slash {}\nSQLite {}\nFPDF {}\nRAM {}%\nCPU {}%\nIP {}\n".format(sys.version, discord.__version__, discord_slash.__version__, sqlite3.sqlite_version, fpdf.FPDF_VERSIONpsutil.virtual_memory().percent, psutil.cpu_percent(), ip)
    await ctx.send(content=content,hidden=True)

bot.run()
