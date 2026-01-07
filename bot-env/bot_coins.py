import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import os
from datetime import datetime, timedelta
import random
import heapq

class ConfirmView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=30) # Temps limite pour cliquer
        self.value = None
        self.author = author

    # Cette fonction s'active à chaque clic
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Si celui qui clique n'est pas l'auteur de la commande
        if interaction.user != self.author:
            # On lui répond un message invisible (ephemeral)
            await interaction.response.send_message("Hé ! Ce n'est pas ta boutique !", ephemeral=True)
            return False # On bloque l'action
        return True # Sinon, on autorise

    # Bouton Vert (Confirm)
    @discord.ui.button(label="Acheter", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop() # On arrête d'écouter les clics
        # On doit répondre à l'interaction pour éviter le message "L'interaction a échoué"
        await interaction.response.defer() 

    # Bouton Rouge (Cancel)
    @discord.ui.button(label="Laisser filer", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()

intents=discord.Intents.default()
intents.message_content=True
intents.members=True

bot=commands.Bot(command_prefix='!', intents=intents, help_command=None)

user_merchant_ids={}
next_merchant_id=0
secret_role = "vendor"
DATA_FILE="user_data.json"
SHOP_FILE="shop_items.json"
items_db={}

def load_data():
    global next_merchant_id
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            data=json.load(file)
            coins={int(k): v for k, v in data.get("coins", {}).items()}
            merchant_ids = {int(k): v for k, v in data.get("merchant_ids", {}).items()}
            next_merchant_id = data.get("next_merchant_id", 1)
            inventory = {int(k): v for k, v in data.get("inventory", {}).items()}
            
            last_daily={}
            for k, v in data.get("last_daily", {}).items():
                last_daily[int(k)]=datetime.fromisoformat(v)
            
            return coins,last_daily,merchant_ids,inventory
    return {}, {}, {}, {}

def save_data():
    data = {
        "coins": user_coins,
        "last_daily": {str(k): v.isoformat() for k, v in user_last_daily.items()},
        "merchant_ids": user_merchant_ids,
        "next_merchant_id": next_merchant_id,
        "inventory": user_inventory
    }
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def load_shop_data():
    if os.path.exists(SHOP_FILE):
        with open(SHOP_FILE, 'r',encoding='utf-8') as file:
            return json.load(file)
    return {}

def save_shop_data():
    with open(SHOP_FILE,'w',encoding='utf-8') as file:
        json.dump(items_db, file, indent=4, ensure_ascii=False)


def delete_account(user_id):
    if user_id in user_coins:
        user_coins.pop(user_id, None)
        user_last_daily.pop(user_id, None)
        user_merchant_ids.pop(user_id, None)
        user_inventory.pop(user_id, None)
        save_data()
        
def delete_last_daily(user_id):
    if user_id in user_last_daily:
        user_last_daily.pop(user_id, None)
        save_data()
        
def add_item_to_inventory(user_id, item_key, item_info):
    if user_id not in user_inventory:
        user_inventory[user_id] = {}
    
    if item_key in user_inventory[user_id]:
        user_inventory[user_id][item_key]["quantity"] += 1
        user_inventory[user_id][item_key]["unit_price"] = item_info["price"]
    else:
        user_inventory[user_id][item_key] = {
            "name": item_info["name"],
            "quantity": 1,
            "unit_price": item_info["price"]
        }
    
    save_data()

def rand_number(start, end):
    return random.randint(start,end)

def get_inventory_value(user_inventory):
    if user_inventory is None:
        return 0
    
    sum=0
    for items in user_inventory.values():
        sum+=items['unit_price'] * items['quantity']
        
    return sum

user_coins, user_last_daily, user_merchant_ids, user_inventory = load_data()
items_db=load_shop_data()

@bot.event
async def on_ready():
    print("bot coins is now ready")
    print(f"donnée chargée: {len(user_coins)} utilisateurs")
    try:
        sync=await bot.tree.sync()
        print(f"{len(sync)} commandes ont été synchronisé")
    except Exception as e:
        print(e)

@bot.hybrid_command(name="register", description="Fait une demande d'adhésion au conseil.")
async def register(ctx):
    global next_merchant_id
    role = discord.utils.get(ctx.guild.roles, name=secret_role)

    if ctx.author.id not in user_coins:
        user_coins[ctx.author.id]=100
        
        user_merchant_ids[ctx.author.id] = next_merchant_id
        merchant_id=next_merchant_id
        next_merchant_id += 1
        
        save_data()
        print(f"init is ready")
        
        if role :
            await ctx.author.add_roles(role)
            await ctx.send(f"Génial {ctx.author.mention} ta demande d'adhésion à été approuvé, te voilà enregistrez en tant que nouveau marchand ambulant !\nRavie de te compter parmis nous, ton identifiant de marchand ambulant est le n°**{merchant_id}** !\nVoilà 100 florins pour débuter... avec plaisir !")
    else:
        current_merchant_id = user_merchant_ids.get(ctx.author.id, "???")
        await ctx.send(f"oooh mais tu ne serais pas déjà dans mon _**registre**_ toi {ctx.author.mention} ?\n Siii, je me souviens maintenant. Tu es bien enregistré sous l'identifiant de marchand ambulant n°**{current_merchant_id}**")

@bot.hybrid_command(name="remove", description="Te sort de l'ordre des marchands ambulants en un rien de temps.")
# @bot.tree.command(name="remove", description="Pour sortir de l'ordre des marchands ambulants.")
async def remove(ctx):
    if ctx.author.id not in user_coins:
        merchant_number = user_merchant_ids.get(ctx.author.id, "???")
        await ctx.send(f"Eh ben... {ctx.author.mention} tu n'es même pas dans mon _**registre des marchands ambulants**_ que tu veux déjà en sortir...")
        return
    
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.remove_roles(role)
        
    delete_account(ctx.author.id)
    delete_last_daily(ctx.author.id)
    await ctx.send(f"{ctx.author.mention} à quitter l'ordre des marchands ambulants, ton identifiant ainsi que tous tes florins seront **supprimé**.\nMerci pour ton travail !")

@bot.hybrid_command(name="daily", description="Revendiques tes florins quotidiens")
# @bot.tree.command(name="daily", description="Pour revendiquer tes florins quotidiens.")
async def daily(ctx):
    if ctx.author.id not in user_coins:
        await ctx.send(f"{ctx.author.mention} huuuum...surement une erreur je ne te vois pas dans le _**registre des marchands ambulants**_.")
        return
    
    now=datetime.now()
    
    if ctx.author.id in user_last_daily:
        last_claim=user_last_daily[ctx.author.id]
        time_diff=now-last_claim

        if time_diff<timedelta(hours=24):
            temps_restant=timedelta(hours=24)-time_diff
            heures=int(temps_restant.total_seconds()//3600)
            minutes=int((temps_restant.total_seconds()%3600)//60)
            
            await ctx.send(f"⏳ {ctx.author.mention} tu as déjà réclamé tes florins quotidien !\nReviens dans **{heures}h {minutes}min**")
            return
    
    randaily=rand_number(7,24)
    user_coins[ctx.author.id]+=randaily
    user_last_daily[ctx.author.id]=now
    save_data()
    
    heure = now.strftime("%H:%M")
    print(f"[{heure}] {ctx.author.name} a gagné {randaily} coins")
    await ctx.send(f"🎁 {ctx.author.mention} tu as gagné **{randaily}** florins à {heure} !\nTon nouveau solde est de **{user_coins[ctx.author.id]}** florins")

@bot.hybrid_command(name="money", description="Affiche ton montant de florins actuel")
# @bot.tree.command(name="money", description="Pour afficher votre montant de florins actuel.")
@commands.has_role(secret_role)
async def money(ctx):
    print(f"le solde de {ctx.author.id} est de {user_coins[ctx.author.id]}")
    await ctx.send(f"Ton solde {ctx.author.mention} est actuellement de **{user_coins[ctx.author.id]}** florins !")

@bot.hybrid_command(name="member", description="Te montre à quel point vous êtes nombreux... ou pas.")
# @bot.tree.command(name="member", description="Pour te montrer à quel point vous nombreux... ou pas.")
async def member(ctx):
    total_member=len(user_coins)
    if ctx.author.id not in user_coins:
        ctx.send(f"Alors, on charche à fouiner... Je te conseils vivement de rejoindre nos rangs si le coeur t'en dis !\nAh et j'allais oublier, il y a actuellement {total_member} marchands ambulants ici.")
        
    if total_member == 1:
        await ctx.send(f"Désolé... Tu es **seul** {ctx.author.mention}...")
    else:
        await ctx.send(f"Vous êtes actuellement **{total_member}** marchands ambulants inscrits dans mon **registre** !")
    
    if total_member<5:
        await ctx.send("Je pense que tu devrais inviter des amis à nous rejoindre !")
    elif total_member<10:
        await ctx.send("Cool on commence à avoir du monde !")
    elif total_member<20:
        await ctx.send("Génial on s'agrandit... !")
    else:
        await ctx.send("Whooooaah...y'a du monde !")

@bot.hybrid_command(name="profil", description="Affiche ta carte de marchand ambulant")
# @bot.tree.command(name="profil", description="Affiche ta carte de marchand ambulant")
@commands.has_role(secret_role)
async def profil(ctx):
    if ctx.author.id not in user_coins:
        await ctx.reply(f"Euuuh... ça doit être une erreur, mais je ne te trouve pas dans mon **registre**.\nPeut-être aurais-tu envie de nous rejoindre...")
    
    merchant_id = user_merchant_ids.get(ctx.author.id, "???")
    
    embed=discord.Embed(
        title=f"˚⋆｡ʚ   {ctx.author.display_name}   ɞ ｡⋆˚",
        description=f"**Numéro de marchand ambulant :** n°{merchant_id}",
        color=discord.Color.yellow()
    )
    
    embed.add_field(name="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", value="",inline=False)
    embed.add_field(name=f"", value=f"**Florins actuels :** {user_coins[ctx.author.id]} F", inline=False)
    embed.add_field(name=f"", value=f"**Nombre d'objets en collection :** 0", inline=False)
    embed.add_field(name=f"", value=f"**Valeurs de l'inventaire :** 0 F", inline=False)
    embed.set_thumbnail(url=ctx.author.avatar.url)
    
    await ctx.reply(embed=embed)
    
@bot.hybrid_command(name="shop", description="Affiche 1 items aléatoire que tu peux acheter")
# @bot.tree.command(name="shop", description="Affiche 3 items aléatoire dans la boutique")
@commands.has_role(secret_role)
async def shop(ctx):
    if ctx.author.id not in user_coins:
        return

    available_items = {k: v for k, v in items_db.items() if v["quantity"] > 0}
    if not available_items:
        await ctx.reply("La boutique est vide pour le moment ! Revenez plus tard.")
        return

    view=ConfirmView(ctx.author)
    keys = list(available_items.keys())
    weights=[item.get("rarity_weight", 1) for item in available_items.values()]
    
    selected_key=random.choices(keys, weights=weights, k=1)[0]
    item_data=items_db[selected_key]
    
    rarity_colors = {
        "Commun": discord.Color.light_grey(),
        "Rare": discord.Color.blue(),
        "Epique": discord.Color.purple(),
        "Légendaire": discord.Color.gold()
    }
    embed_color = rarity_colors.get(item_data.get("rarity"), discord.Color.yellow())
    
    embed=discord.Embed(
        title=f"── ࣪˖  ࣪  {item_data["name"]}   ࣪ ˖ ──",
        description=item_data["description"],
        color=embed_color
    )
    
    embed.add_field(name="Rareté :", value=f"{item_data["rarity"]}", inline=False)
    embed.add_field(name="Prix :", value=f"{item_data["price"]} F", inline=False)
    embed.add_field(name="Quantité restante :", value=item_data["quantity"], inline=False)
    embed.set_thumbnail(url=item_data["url"])
    embed.set_footer(text=f"Il te reste {user_coins[ctx.author.id]} F.")
    print("shop is open")
    
    await ctx.reply("Voilà ce que j'ai pour toi... Alors tu le prends ?", embed=embed, view=view)
    await view.wait()
    
    if view.value is None:
        await ctx.reply("Tant pis... fallait être plus rapide !")
    elif view.value is True:
        current_stock = items_db[selected_key]["quantity"]
        
        if current_stock <= 0:
            await ctx.reply(f"Désolé {ctx.author.mention} quelqu'un d'autre t'es passé devant et à vider le stock... soit plus rapide la prochaine fois !")
        elif user_coins[ctx.author.id] < item_data["price"]:
            await ctx.reply(f"Oh mais je vois que tu n'as pas assez de florins en poche... pas grave je remballe. A la prochaine !")
        else:
            user_coins[ctx.author.id]-=item_data["price"]
            items_db[selected_key]["quantity"]-=1
            add_item_to_inventory(ctx.author.id, selected_key, item_data)
            
            save_data()
            save_shop_data()
            print("transaction effectué")
            await ctx.reply(f"Merci pour ton achat !\n**{item_data['name']}** à été ajouté à ton inventaire.")
    else:
        await ctx.reply("Pas de problème. A la prochaine !")

@bot.hybrid_command(name="bag", description="Affiche le contenu de ton inventaire")
@commands.has_role(secret_role)
async def bag(ctx):
    if ctx.author.id not in user_coins:
        return

    my_inventory=user_inventory.get(ctx.author.id, {})
    total_value=get_inventory_value(my_inventory)
    total_items = sum(item['quantity'] for item in my_inventory.values())
    
    user=await bot.fetch_user(ctx.author.id)
    user_banner=user.accent_color
    
    embed=discord.Embed(
        title=f"꧁༺  Inventaire de {ctx.author.display_name}  ༻꧂",
        description=f"**{total_items} objets au total**",
        color=user_banner if user.accent_color else discord.Color.green()
    )
    
    embed.add_field(name="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", value="",inline=False)
    for item in my_inventory.values():
        name=item['name']
        qty=item['quantity']
        price=item['unit_price']
        
        embed.add_field(
            name="", 
            value=f"**{qty} {name} **: {price} F",
            inline=False
        )
        
    embed.set_footer(text=f"valeur total de {total_value} F")
    embed.set_thumbnail(url=ctx.author.avatar.url)
    
    await ctx.reply(embed=embed)

#!sell name quantity

#!kiki
@bot.hybrid_command(name="kiki", description="Affiche un tableau des scores avec ta position et celui des 3 premiers.")
@commands.has_role(secret_role)
async def kiki(ctx):
    if ctx.author.id not in user_coins:
        return
    
    my_inventory=user_inventory.get(ctx.author.id, {})
    total_value=get_inventory_value(my_inventory)
    
    user_amount={}
    for user_id in user_coins:
        my_inventory=user_inventory.get(user_id, {})
        total_value=get_inventory_value(my_inventory)
        
        user_amount[user_id]=total_value+user_coins[user_id]
    
    leaderboard=sorted(user_amount.items(), key=lambda item: item[1], reverse=True)
    top_3 = leaderboard[:3]

    embed=discord.Embed(
        title="꧁༺  Tableau des scores  ༻꧂",
        color=discord.Color(0xF0E68C)
    )
    
    embed.add_field(name="╭───────────\u00A0 • \u00A0 ◈ \u00A0 • \u00A0───────────╮", value="",inline=False)
    
    for index, (user_id, amount) in enumerate(top_3,1):
        try:
            user=await bot.fetch_user(user_id)
            user_name=user.display_name
        except:
            user_name="\u00A0 _Marchand disparu_"
        
        embed.add_field(
            name="",
            value=f"\u200b\u00A0\u00A0\u00A0 **{index}**. \u00A0{user_name} \u3000\u3000\u3000 {amount} F",
            inline=False
        )

    embed.add_field(name="╰───────────\u00A0 • \u00A0 ◈ \u00A0 • \u00A0───────────╯", value="",inline=False)
    sorted_ids=[item[0] for item in leaderboard]
    try:
        my_rank=sorted_ids.index(ctx.author.id)+1
        # total_players=len(user_coins)
        
        # current_user=await bot.fetch_user(ctx.author.id)
        embed.set_footer(text=f"\u200b\u3000{my_rank}. {ctx.author.display_name}    {user_amount[ctx.author.id]} F", icon_url=ctx.author.avatar.url)
    except:
        embed.set_footer(text="ta position est encore inconnue.")

    await ctx.reply(embed=embed)

@bot.hybrid_command(name="help", description="Affiche une liste d'aide")
async def help(ctx):
    embed=discord.Embed(
        title="\u200b\u3000\u3000\u3000\u3000\u3000꧁༺  Guide du marchand ambulant  ༻꧂",
        description="Commence par utiliser '!register' et ton aventure pourra commencer",
        color=discord.Color.blue()
    )

    embed.add_field(name="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", value="",inline=False)
    embed.add_field(name="!register", value="Fait une demande d'adhésion au conseil pour t'accepter parmis nous.", inline=False)
    embed.add_field(name="!remove", value="Te sort immédiatemment de l'ordre des marchands sans y laissé de traces. **Attention cette commande est irréversible !**", inline=False)
    embed.add_field(name="!daily", value="Réclame tes florins quotidiens.", inline=False)
    embed.add_field(name="!money", value="Affiche ton montant de florins actuel", inline=False)
    embed.add_field(name="!member", value="Te montre à quel point vous êtes nombreux... ou pas.", inline=False)
    embed.add_field(name="!profil", value="Affiche ta carte de marchand ambulant", inline=False)
    embed.add_field(name="!shop", value="Affiche 1 items aléatoire que tu peux acheter", inline=False)
    embed.add_field(name="!bag", value="Affiche le contenu de ton inventaire", inline=False)
    embed.add_field(name="!kiki", value="Affiche un tableau des scores avec ta position et celui des 3 premiers.", inline=False)
    embed.set_footer(text="Toutes les commandes précédentes peuvent être éxécutées en remplaçant '!' par '/' | pour plus d'informations https://github.com/ValouHubwork")
    embed.set_author(name="Kytetsunix")
    
    await ctx.reply(embed=embed, ephemeral=True)
    

token="MTQ1NzM5NTQ0MDU1MDE1NDI0Mg.G-vez0.uRRqfEnX9z7okVozLA-cek2ghIGfWmptw7tOKQ"
handler=logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)