import requests
import json
import re
import os

URL = "https://runescape.wiki/api.php"
HEADERS = {"User-Agent": "Antigravity/1.0"}

print("Downloading RS Dump to get Item IDs...")
resp = requests.get("https://chisel.weirdgloop.org/gazproj/gazbot/rs_dump.json", headers=HEADERS)
rs_dump = resp.json()
name_to_id = {}
for item_id, item_data in rs_dump.items():
    if isinstance(item_data, dict) and "name" in item_data:
        name_to_id[item_data["name"]] = str(item_id)

recipe_db = {}

# --- 1. SMITHING MODULE ---
params = {
    "action": "parse",
    "page": "Module:Smithing profit calculator/Data",
    "prop": "wikitext",
    "format": "json"
}
resp = requests.get(URL, params=params, headers=HEADERS)
wikitext = resp.json().get("parse", {}).get("wikitext", {}).get("*", "")

current_metal = None
for line in wikitext.split("\n"):
    line = line.strip()
    match_metal = re.match(r'^([a-z_]+)\s*=\s*\{', line)
    if match_metal:
        metal = match_metal.group(1)
        if metal == 'elder': metal = 'elder_rune'
        current_metal = metal
        continue
    
    match_recipe = re.search(r"name\s*=\s*'([^']+)'", line)
    if match_recipe and current_metal:
        output_name = match_recipe.group(1)
        match_bars = re.search(r"bars\s*=\s*(\d+)", line)
        if match_bars:
            bars_qty = match_bars.group(1)
            
            if current_metal == 'adamant': bar_name = 'Adamant bar'
            elif current_metal == 'elder_rune': bar_name = 'Elder rune bar'
            elif current_metal == 'orikalkum': bar_name = 'Orikalkum bar'
            elif current_metal == 'necronium': bar_name = 'Necronium bar'
            elif current_metal == 'bane': bar_name = 'Bane bar'
            elif current_metal == 'corrupted_ore': continue
            else: bar_name = current_metal.capitalize() + " bar"
                
            output_id = name_to_id.get(output_name)
            bar_id = name_to_id.get(bar_name)
            
            if output_id and bar_id:
                recipe_db[output_id] = [{"id": bar_id, "qty": bars_qty}]

# --- 2. INFOBOX RECIPE via Generator ---
print("Querying all Infobox Recipes via generator...")
continue_token = None
pages_processed = 0

while True:
    params = {
        "action": "query",
        "generator": "embeddedin",
        "geititle": "Template:Infobox Recipe",
        "geilimit": 50,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json"
    }
    if continue_token:
        params.update(continue_token)
        
    resp = requests.get(URL, params=params, headers=HEADERS)
    data = resp.json()
    
    pages = data.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        title = page_data.get("title", "")
        revisions = page_data.get("revisions", [])
        if not revisions: continue
        w_text = revisions[0].get("slots", {}).get("main", {}).get("*", "")
        pages_processed += 1
        
        recipe_block = re.search(r'\{\{Infobox Recipe(.*?)^\}\}', w_text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if not recipe_block: continue
        block = recipe_block.group(1)
        
        ingredients = []
        for i in range(1, 6):
            mat_match = re.search(fr"\|mat{i}\s*=\s*([^|\n]+)", block)
            if not mat_match: continue
            mat_name = mat_match.group(1).strip().replace("[", "").replace("]", "")
            
            amt_match = re.search(fr"\|(?:mat{i}qty|amt{i})\s*=\s*([^|\n]+)", block)
            amt = amt_match.group(1).strip() if amt_match else "1"
            
            mat_id = name_to_id.get(mat_name)
            if mat_id:
                ingredients.append({"id": mat_id, "qty": amt})
                
        output_name = title
        out_match = re.search(r"\|output1\s*=\s*([^|\n]+)", block)
        if out_match:
            output_name = out_match.group(1).strip().replace("[", "").replace("]", "")
            
        output_id = name_to_id.get(output_name)
        if not output_id:
            output_id = name_to_id.get(title)
            
        if output_id and ingredients:
            if output_id not in recipe_db or amt != "1":
                recipe_db[output_id] = ingredients

    if "continue" in data:
        continue_token = data["continue"]
    else:
        break

target_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "recipes.json"))
print(f"Processed {pages_processed} pages.")
print(f"Saving to {target_path}")

with open(target_path, "w") as f:
    json.dump(recipe_db, f, indent=2)

print(f"Success! Generated {len(recipe_db)} total recipes.")
