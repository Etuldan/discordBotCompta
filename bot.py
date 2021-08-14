# bot.py

import discord
import discord_slash
from discord_slash import SlashCommand
from discord_slash import SlashContext

import locale
from fpdf import FPDF
from datetime import datetime, date, timedelta

import gspread
from oauth2client.service_account import ServiceAccountCredentials

import io
import asyncio
import json

import configparser

import requests
import requests_html

DB_CONTRACT = "data.json"

COLOR_RED = 15158332
COLOR_GREEN = 0x00ff00
COLOR_LIGHT_GREY = 12370112
COLOR_DARK_GOLD = 12745742
COLOR_DEFAULT = 0

slash = None


guild_ids = []    
    
class Bot(discord.Client):
    channelContrat = 0
    channelLogContrat = 0
    contracts = []
    config = 0
    message_head_income = 0
    message_head_outcome = 0
    sheet = 0
    
    def __init__(self):
        global slash
        global guild_ids
        global sheet

        client = gspread.service_account(filename = 'bennys-compta-7582b5af1081.json')
        sheet = client.open_by_key("1csE41uhT1dldHfFCEO_nrA1pTpdNvZQx7MSrU3MXzoQ")
        
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.channelIdContrat = int(self.config['Channel']['Contrat'])
        self.channelIdContratPatron = int(self.config['Channel']['ContratPatron'])
        self.channelIdLogContrat = int(self.config['Channel']['LogContrat'])
        self.channelIdHome = int(self.config['Channel']['Home'])
        self.channelIdRapportFailyV = int(self.config['Channel']['RapportFailyV'])
        self.channelIdCompta = int(self.config['Channel']['Compta'])
        
        self.userIdBotFailyV = int(self.config['Role']['BotFailyV'])
        self.roleIdPatron = self.config['Role']['Patron']
        
        self.token = self.config['Discord']['Token']
        guild_ids = []
        tempList  = self.config['Discord']['GuildID'].split(',')
        for tempid in tempList:
            guild_ids.append((int(tempid)))
        
        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)       
        slash = SlashCommand(self.client, sync_commands=True)
        
        self.on_ready = self.client.event(self.on_ready)
        self.on_message = self.client.event(self.on_message)
        self.on_raw_reaction_add = self.client.event(self.on_raw_reaction_add)
        
        self.contracts = []
        with open(DB_CONTRACT, 'r') as json_file:
            data = json.load(json_file)
            for company in data:
                contrat = Contrat(company, data[company]["amount"])
                contrat.positive = data[company]["positive"]
                contrat.paid = data[company]["paid"]
                contrat.deduc = data[company]["deduc"]
                contrat.reset = data[company]["reset"]
                contrat.temp = data[company]["temp"]
                self.contracts.append(contrat)
        
        self.client.loop.create_task(self.background_task())
    
    async def retreive_contract_discord(self):
        amount_income = 0
        amount_outcome = 0
        amount_depense_deduc = 0
        amount_depense_nondeduc = 0
        amount_impot = 0
        amount_remaining = 0
        amount_entreprise = 0

        taux_salaire = 2800

        messages = await channelRapportFailyV.history(limit=14).flatten() # 7 days

        employes = []
        for msg in messages:
            if(msg.author.id == self.userIdBotFailyV):
                print(f'{msg.embeds[0].fields[0].value = }')
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
                    if(embed.title == "Détails Salaires"):
                        for field in embed.fields:
                            employes.append(field.name)

        unique_employes = set(employes)
        print(f'{len(unique_employes)  = }')

        for contract in self.contracts:
            if(contract.amount != 0 and contract.positive == False and contract.paid == True):
                if(contract.deduc == False):
                    amount_depense_nondeduc = amount_depense_nondeduc + contract.amount
                elif(contract.company != "Impôts" and contract.company != "Bénéfices"):
                    amount_depense_deduc = amount_depense_deduc + contract.amount
            elif(contract.amount != 0 and contract.positive == True and contract.paid == True):
                amount_entreprise = amount_entreprise + contract.amount

            contract.paid = False
            if contract.reset == True:
                contract.amount = 0
            if contract.temp == True:
                contracts.remove(contract)

        amount_depense_deduc = amount_depense_deduc + len(unique_employes) * taux_salaire

        taux = 0
        if(amount_income - amount_depense_deduc >= 25000):
            taux = 25
            amount_impot = round((amount_income - amount_depense_deduc)*taux/100)
        amount_remaining = amount_income - amount_outcome - amount_depense_deduc - amount_depense_nondeduc - amount_impot

        for contract in contracts:
            if(contract.company == "Impôts"):
                contract.amount = amount_impot
            elif(contract.company == "Bénéfices"):
                contract.amount = amount_remaining

        await self.writePDF(taux, amount_income, amount_impot, amount_entreprise, amount_depense_deduc, len(unique_employes) * taux_salaire, len(unique_employes))


    async def writePDF(self, taux, amount_income, amount_impot, amount_entreprise, amount_depense_deduc, amount_employe, unique_employes):
        locale.setlocale(locale.LC_ALL, 'fr_FR')

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
        pdf.cell(w=10.0, h=10.0, align='L', txt=str(amount_income - amount_depense_deduc) + " $", border=0)

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
        for contract in self.contracts:
            if(contract.amount != 0 and contract.positive == True and contract.paid == True):
                pdf.set_xy(100.0, 110 + i)
                pdf.cell(w=10.0, h=10.0, align='R', txt=contract.company, border=0)
                pdf.cell(w=10.0, h=10.0, align='L', txt=str(contract.amount) + " $", border=0)
                i = i + 5

        pdf.set_font('Arial', 'B', 15)
        pdf.set_xy(100.0, i+120)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Détails Dépenses déductibles", border=0)
        pdf.set_font('Arial', '', 13)
        for contract in self.contracts:
            if(contract.amount != 0 and contract.positive == False and contract.paid == True and not("Autre" in contract.company) and contract.company != "Impôts" and contract.company != "Bénéfices"):
                pdf.set_xy(100.0, 125 + i)
                pdf.cell(w=10.0, h=10.0, align='R', txt=contract.company, border=0)
                pdf.cell(w=10.0, h=10.0, align='L', txt=str(contract.amount) + " $", border=0)
                i = i + 5

        pdf.set_xy(100.0, 125 + i)
        pdf.cell(w=10.0, h=10.0, align='R', txt="Salaires (" + str(unique_employes) + ")", border=0)
        pdf.cell(w=10.0, h=10.0, align='L', txt=str(amount_employe) + " $", border=0)

        pdf.output('Comptabilite_Bennys_-_Impots_Hebdo.pdf','F')
        await self.channelCompta.send(file=discord.File('Comptabilite_Bennys_-_Impots_Hebdo.pdf'))

    async def retreive_contract(self):
        amounts = sheet.worksheet("Histo_Contrats").row_values(5, value_render_option="UNFORMATTED_VALUE")
        names = sheet.worksheet("Histo_Contrats").row_values(2, value_render_option="UNFORMATTED_VALUE")
        impots = sheet.worksheet("Récap").cell(3, 3, value_render_option="UNFORMATTED_VALUE").value
        
        for name in names:
            for contract in self.contracts:
                if contract.company == name:
                    contract.amount = 0
        
        i = 0
        for amount in amounts:
            for contract in self.contracts:
                if contract.company == names[i]:
                    contract.amount = amount + contract.amount
            i = i+1
        
        for contract in self.contracts:
            contract.paid = False
            if contract.company == "Impôts":
                contract.amount = round(impots)
            elif contract.deduc == False:
                contracts.remove(contract)

        bot.update_db()
        await bot.update_contract()
    
    async def retreive_panel(self):
        urlLogin = 'http://panel.failyv.com/dashboard/index.php'
        urlCompany = 'http://panel.failyv.com/dashboard/index.php?section=company'
    
        selChest = "div#inventaire_coffre table tbody"
        selBank = "input[name='money']"
        selDirty = "input[name='dirty_money']"
        
        payload = {'login': self.config['Panel']['Login'], 'password': self.config['Panel']['Password']}        
        
        with requests_html.HTMLSession() as s:
            s.post(urlLogin, data=payload)
            r = s.get(urlCompany)
            moneyChest = int(r.html.find(selChest, first=True).text[0:-2].replace(' ', ''))
            moneyBank = int(r.html.find(selBank, first=True).attrs['value'].replace(' ', ''))
            moneyDirty = int(r.html.find(selDirty, first=True).attrs['value'].replace(' ', ''))
        
            sheet.worksheet("Journal").update("C14", moneyChest)
            sheet.worksheet("Journal").update("K14", moneyBank+moneyDirty)
    
    async def background_task(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await asyncio.sleep(50)
            now = datetime.now().time()
            if(datetime.now().weekday() == 0 and now.hour == 12 and now.minute == 0):
                await bot.retreive_contract()
            if(datetime.now().weekday() == 0 and now.hour == 2 and now.minute == 0):
                await bot.retreive_panel()
            elif(datetime.now().weekday() == 0 and now.hour == 3 and now.minute == 0):
                await bot.retreive_contract_discord()
    
    async def on_message(self, message):
        if message.author == self.client.user:
            return
        
        if message.author.bot:
            return
        
        if message.channel.id == self.channelIdLogContrat or message.channel.id == self.channelIdContrat or message.channel.id == self.channelIdContratPatron:
            await message.delete()
    
    async def update_head(self):           
        embed=discord.Embed(title="Encaissement", color=COLOR_GREEN)
        for contract in bot.contracts:
            name = ""
            if(contract.positive == False):
                continue
            if(contract.deduc == True):
                name = name + "💰 "
            if(contract.reset == False):
                name = name + "🔄 "
            name = name + contract.company
            
            amount = str(contract.amount)
            if(contract.paid == True):
                amount = amount + " ✅"
            embed.add_field(name=name, value=amount, inline=False)
        try:
            await self.message_head_income.edit(embed = embed)
        except:
            self.message_head_income = await self.channelContratPatron.send(embed=embed)

        embed=discord.Embed(title="Paiement", color=COLOR_RED)
        for contract in bot.contracts:
            name = ""
            if(contract.positive == True):
                continue
            if(contract.deduc == True):
                name = name + "💰 "
            if(contract.reset == False):
                name = name + "🔄 "
            name = name + contract.company

            amount = str(contract.amount)
            if(contract.paid == True):
                amount = amount + " ✅"
            embed.add_field(name=name, value=amount, inline=False)
        try:
            await self.message_head_outcome.edit(embed = embed)
        except:
            self.message_head_outcome = await self.channelContratPatron.send(embed=embed)
    
    async def update_contract(self):
        await self.channelContrat.purge()
        await self.channelContratPatron.purge()
          
        await self.update_head()
        
        for contract in self.contracts:
            if(contract.amount != 0):
                if(contract.paid == False):
                    if(contract.positive == True):
                        embedVar = discord.Embed(title="Contrat " + contract.company, description = str(contract.amount) + "$", color=COLOR_GREEN)
                        msg = await self.channelContrat.send(embed=embedVar)
                        await msg.add_reaction("✅")
                    else:
                        embedVar = discord.Embed(title=contract.company, description = str(contract.amount) + "$", color=COLOR_RED)
                        msg = await self.channelContratPatron.send(embed=embedVar)
                        await msg.add_reaction("✅")
    
    async def on_ready(self):
        print(str(self.client.user) + " has connected to Discord")
        print("Bot ID is " + str(self.client.user.id))
        
        self.channelHome = self.client.get_channel(self.channelIdHome)
        self.channelLogContrat = self.client.get_channel(self.channelIdLogContrat)
        self.channelContrat = self.client.get_channel(self.channelIdContrat)
        self.channelContratPatron = self.client.get_channel(self.channelIdContratPatron)
        self.channelRapportFailyV = self.client.get_channel(self.channelIdRapportFailyV)
        self.channelCompta = self.client.get_channel(self.channelIdCompta)

        self.rolePatron = []
        tempList  = self.roleIdPatron.split(',')
        for tempRole in tempList:
            self.rolePatron.append(self.channelHome.guild.get_role(int(tempRole)))

        await self.update_contract()

        print(str(self.client.user) + " is now ready!")
    
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id != self.channelIdContrat and payload.channel_id != self.channelIdContratPatron:
            return
        
        try:
            guild = self.client.get_guild(payload.guild_id)
            user = guild.get_member(payload.user_id)
            
            if user == self.client.user:
                return
            
            channel = self.client.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            
            if(payload.emoji.name == "✅"):
                for contract in self.contracts:
                    if(contract.paid == False and contract.company in message.embeds[0].title and ((contract.positive == True and "Contrat" in message.embeds[0].title) or (contract.positive == False and "Contrat" not in message.embeds[0].title))):
                        contract.paid = True
                        bot.update_db()
                        
                        contrat = ""
                        details = ""                        
                        if(contract.positive == True):
                            reason = "Contrat"
                            source = "Coffre"
                            contrat = message.embeds[0].title[8:]
                        else:
                            reason = message.embeds[0].title.split()[0]
                            source = "Compte en banque"
                            details = message.embeds[0].title
                        
                        form_data = {
                            'entry.' + self.config['Form']['Date']    : date.today().strftime("%Y-%m-%d"),
                            'entry.' + self.config['Form']['User']    : user.display_name, 
                            'entry.' + self.config['Form']['Reason']  : reason,
                            
                            'entry.' + self.config['Form']['Contract']: contrat, 

                            'entry.' + self.config['Form']['Amount']  : message.embeds[0].description.strip('$'),
                            'entry.' + self.config['Form']['Source']  : source,
                            'entry.' + self.config['Form']['Details'] : details,
                            
                            'draftResponse':[], 
                            'pageHistory':"0,1,2"}
                            
                        user_agent = {'Referer':self.config['Form']['URL'] + '/viewform','User-Agent':"Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.52 Safari/537.36"}
                        r = requests.post(self.config['Form']['URL'] + "/formResponse", data=form_data, headers=user_agent)
                        
                        await message.delete()
                        if(contract.positive == True):
                            await self.channelLogContrat.send("🟢 Le **" + message.embeds[0].title + "** de " + message.embeds[0].description + " a été encaissé par " +  user.display_name)
                        else:
                            await self.channelLogContrat.send("🔴 Le **Contrat " + message.embeds[0].title + "** de " + message.embeds[0].description + " a été payé par " +  user.display_name)
                        await self.update_head()
                        
        except discord.errors.NotFound:
            pass
    
    def update_db(self):
        data = {}
        for contract in self.contracts:
            data[contract.company] = {}
            data[contract.company]["amount"] = contract.amount
            data[contract.company]["positive"] = contract.positive
            data[contract.company]["paid"] = contract.paid
            data[contract.company]["deduc"] = contract.deduc
            data[contract.company]["reset"] = contract.reset
            data[contract.company]["temp"] = contract.temp
        with open(DB_CONTRACT, 'w') as outfile:
            json.dump(data, outfile)
    
    def run(self):
        print("Starting bot ...")
        self.client.run(self.token)

class Contrat(object):
    def __init__(self, company, amount):
        self.company = company
        self.amount = amount
        self.positive = False
        self.paid = False
        self.deduc = True
        self.reset = False
        self.temp = False

bot = Bot()

@slash.slash(
    name="ajouterContrat",
    description="[PATRON] Ajoute un contrat",
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
    guild_ids=guild_ids)
async def _ajouterContrat(ctx: SlashContext, entreprise: str, montant: int, typec: bool):
    await ctx.defer(hidden=True)   
    authorized = False
    for tempRole in bot.rolePatron:
        if tempRole in ctx.author.roles:
           authorized = True
    
    if authorized:
        contrat = Contrat(entreprise, montant)

        if(typec == 2):
            contrat.deduc = False
            typec = 0
        elif(typec == 3):
            contrat.deduc = False
            contrat.reset = True
            typec = 0
        elif(typec == 4):
            contrat.reset = True
            typec = 0
        elif(typec == 5):
            contrat.temp = True
            typec = 0
        elif(typec == 6):
            contrat.deduc = False
            contrat.temp = True
            typec = 0

        contrat.positive = typec
        contrat.paid = False
        bot.contracts.append(contrat)
        bot.update_db()
        await bot.update_contract()
        await ctx.send(content="Contrat " + contrat.company + " ajouté !",hidden=True)
    else:
        await ctx.send(content="🔴Echec de l'ajout du contrat !",hidden=True)

@slash.slash(
    name="modifierContrat",
    description="[PATRON] Modifie un contrat existant",
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
    guild_ids=guild_ids)
async def _modifierContrat(ctx: SlashContext, entreprise: str, montant: int):
    await ctx.defer(hidden=True)   
    authorized = False
    for tempRole in bot.rolePatron:
        if tempRole in ctx.author.roles:
           authorized = True
    
    if authorized:
        for contract in bot.contracts:
            if(contract.company == entreprise):
                if(contract.reset == True):
                    contract.amount = contract.amount + montant
                else:
                contract.amount = montant
                bot.update_db()
                await bot.update_contract()
                await ctx.send(content="Contrat " + contract.company + " modifié !",hidden=True)
                return
        await ctx.send(content="🔴Echec : Aucun contrat modifié !",hidden=True)
    else:
        await ctx.send(content="🔴Echec de la modification du contrat !",hidden=True)

@slash.slash(
    name="supprimerContrat",
    description="[PATRON] Supprime un contrat existant",
    options = [{
        "name": "entreprise",
        "description": "Entreprise pour lequel supprimer le Contrat",
        "type": 3,
        "required": True
    }],
    guild_ids=guild_ids)
async def _supprimerContrat(ctx: SlashContext, entreprise: str):
    await ctx.defer(hidden=True)   
    authorized = False
    for tempRole in bot.rolePatron:
        if tempRole in ctx.author.roles:
           authorized = True
    
    if authorized:
        for contract in bot.contracts:
            if(contract.company == entreprise):
                bot.contracts.remove(contract)
                bot.update_db()
                await bot.update_contract()
                await ctx.send(content="Contrat " + contract.company + " supprimé !",hidden=True)
                return
        await ctx.send(content="🔴Echec : Aucun contrat supprimé !",hidden=True)
    else:
        await ctx.send(content="🔴Echec de la suppression du contrat !",hidden=True)
        
@slash.slash(
    name="rechargerContrat",
    description="[PATRON] Recharge les contrats",
    options = [],
    guild_ids=guild_ids)
async def _supprimerContrat(ctx: SlashContext):
    await ctx.defer(hidden=True)   
    authorized = False
    for tempRole in bot.rolePatron:
        if tempRole in ctx.author.roles:
           authorized = True
    
    if authorized:
        await bot.retreive_contract()
        await ctx.send(content="Contrat rechargés !",hidden=True)
    else:
        await ctx.send(content="🔴Echec du rechargement des contrats !",hidden=True)

    
bot.run()
