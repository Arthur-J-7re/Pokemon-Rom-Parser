import json, sqlite3
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from .parser import parse_log
from .database import init_db, get_db_path
from datetime import datetime

app = FastAPI(title="PokeRando Wiki")
BASE_DIR = Path(__file__).parent
DATA_DIR = Path("/data")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def startup():
    DATA_DIR.mkdir(exist_ok=True)
    db_path = get_db_path(DATA_DIR)
    init_db(db_path)
    # Ensure at least one adventure exists
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    count = c.execute("SELECT COUNT(*) FROM adventures").fetchone()[0]
    if count == 0:
        c.execute("INSERT INTO adventures (name, log_file, lang) VALUES (?, ?, ?)",
                  ("Default Adventure", None, "fr"))
        conn.commit()
    conn.close()


def db():
    return sqlite3.connect(get_db_path(DATA_DIR))


def get_active_adventure():
    conn = db()
    c = conn.cursor()
    row = c.execute("SELECT id FROM adventures WHERE active=1 LIMIT 1").fetchone()
    conn.close()
    return row[0] if row else 1


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    has_data, log_name, stats, lang, adventures = False, None, {}, 'fr', []
    try:
        c = db().cursor()
        adventures = c.execute("SELECT id, name, log_file FROM adventures ORDER BY created_at DESC").fetchall()
        adventures = [{"id": a[0], "name": a[1], "log_file": a[2]} for a in adventures]
        
        active_adv_id = get_active_adventure()
        row = c.execute("SELECT id, name, log_file, lang FROM adventures WHERE id=?", (active_adv_id,)).fetchone()
        if row:
            log_name, has_data = row[1], bool(row[2])
            lang = row[3]
        
        if has_data:
            for tbl, key in [("base_stats","pokemon"),("trainers","trainers"),
                             ("wild_sets","wild_sets"),("tms","tms"),("shops","shops")]:
                count = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                stats[key] = count
    except:
        pass
    return templates.TemplateResponse("index.html", {
        "request": request, "has_data": has_data, "log_name": log_name, "stats": stats, "lang": lang, "adventures": adventures, "active_adv_id": get_active_adventure()
    })


@app.post("/upload")
async def upload_log(file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8", errors="replace")
    db_path = get_db_path(DATA_DIR)
    try:
        data = parse_log(text)
        
        # Create new adventure instead of resetting the entire DB
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Mark all adventures as inactive
        c.execute("UPDATE adventures SET active=0")
        
        # Create new adventure
        c.execute("INSERT INTO adventures (name, log_file, lang, active) VALUES (?, ?, ?, 1)",
                  (file.filename, file.filename, data.get('lang','fr')))
        adventure_id = c.lastrowid
        
        # Insert data
        for s in data["base_stats"]:
            c.execute("INSERT OR REPLACE INTO base_stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (s["num"],s["name"],s["type"],s["hp"],s["atk"],s["def"],
                 s["spa"],s["spd"],s["spe"],s["ability1"],s["ability2"],s["item"]))

        for m in data["movesets"]:
            c.execute("INSERT INTO movesets (name,evolves_to,level_moves,egg_moves) VALUES (?,?,?,?)",
                (m["name"],m["evolves_to"],
                 json.dumps(m["level_moves"],ensure_ascii=False),
                 json.dumps(m["egg_moves"],ensure_ascii=False)))

        for t in data["trainers"]:
            c.execute("INSERT OR REPLACE INTO trainers VALUES (?,?,?)",
                (t["id"],t["class"],json.dumps(t["pokemon"],ensure_ascii=False)))

        for ws in data["wild"]:
            c.execute("INSERT INTO wild_sets (set_num,location,type,rate) VALUES (?,?,?,?)",
                (ws["set"],ws["location"],ws["type"],ws["rate"]))
            sid = c.lastrowid
            for p in ws["pokemon"]:
                c.execute("INSERT INTO wild_pokemon (set_id,name,level) VALUES (?,?,?)",
                    (sid,p["name"],p["level"]))

        for pr in data["pickup_items"]:
            for pi in pr["items"]:
                c.execute("INSERT INTO pickup_items (level_range,item,chance) VALUES (?,?,?)",
                    (pr["range"],pi["item"],pi["chance"]))

        for sh in data["shops"]:
            c.execute("INSERT INTO shops (name) VALUES (?)", (sh["name"],))
            shid = c.lastrowid
            for item in sh["items"]:
                c.execute("INSERT INTO shop_items (shop_id,item) VALUES (?,?)", (shid,item))

        for tr in data["trades"]:
            c.execute("INSERT INTO trades (give,receive_nick,receive,give2,receive_nick2,receive2) VALUES (?,?,?,?,?,?)",
                (tr["give"],tr["receive_nick"],tr["receive"],tr["give2"],tr["receive_nick2"],tr["receive2"]))

        for tm in data["tms"]:
            c.execute("INSERT OR REPLACE INTO tms VALUES (?,?)", (tm["tm"],tm["move"]))

        for entry in data["tm_compat"]:
            for tm in entry["tms"]:
                c.execute("INSERT INTO tm_compat (pokemon_name,tm) VALUES (?,?)", (entry["name"],tm))

        for evo in data["evolutions"]:
            c.execute("INSERT INTO evolutions (from_poke,to_poke,method) VALUES (?,?,?)",
                (evo["from"],evo["to"],evo["method"]))

        conn.commit()
        conn.close()
        counts = {k: len(v) for k, v in data.items()}
        return JSONResponse({"ok": True, "message":
            f"Importé ! {counts['base_stats']} Pokémon · {counts['trainers']} dresseurs · "
            f"{counts['wild']} zones · {counts['tms']} TMs · {counts['shops']} shops"})
    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "message": str(e)+"\n"+traceback.format_exc()}, status_code=400)


# ── API ──────────────────────────────────────────────────────────────────────

@app.get("/api/adventures")
def get_adventures():
    c = db().cursor()
    rows = c.execute("SELECT id, name, log_file, created_at FROM adventures ORDER BY created_at DESC").fetchall()
    active_id = get_active_adventure()
    return [{"id": r[0], "name": r[1], "log_file": r[2], "created_at": r[3], "active": r[0] == active_id} for r in rows]


@app.post("/api/adventures/{adv_id}/select")
def select_adventure(adv_id: int):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE adventures SET active=0")
    c.execute("UPDATE adventures SET active=1 WHERE id=?", (adv_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/team-state")
def get_team_state():
    active_adv_id = get_active_adventure()
    c = db().cursor()
    rows = c.execute(
        "SELECT id, pokemon_name, pokemon_level, nickname, status, team_position FROM pokemon_state "
        "WHERE adventure_id=? ORDER BY team_position ASC", (active_adv_id,)
    ).fetchall()
    team = []
    pc = []
    dead = []
    for r in rows:
        poke = {"id": r[0], "name": r[1], "level": r[2], "nickname": r[3], "status": r[4], "team_position": r[5]}
        if r[4] == "team":
            team.append(poke)
        elif r[4] == "pc":
            pc.append(poke)
        elif r[4] == "dead":
            dead.append(poke)
    return {"team": team, "pc": pc, "dead": dead}


@app.post("/api/pokemon-state")
async def post_pokemon_state(request: Request):
    try:
        data = await request.json()
        active_adv_id = get_active_adventure()
        conn = db()
        c = conn.cursor()
        
        # Check if pokemon already exists
        existing = c.execute(
            "SELECT id FROM pokemon_state WHERE adventure_id=? AND pokemon_name=? ORDER BY created_at DESC LIMIT 1",
            (active_adv_id, data["name"])
        ).fetchone()
        
        if existing:
            # Update existing
            c.execute(
                "UPDATE pokemon_state SET pokemon_level=?, nickname=?, status=?, team_position=? WHERE id=?",
                (data.get("level"), data.get("nickname"), data.get("status"), data.get("team_position"), existing[0])
            )
        else:
            # Insert new
            c.execute(
                "INSERT INTO pokemon_state (adventure_id, pokemon_name, pokemon_level, nickname, status, team_position) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (active_adv_id, data["name"], data.get("level"), data.get("nickname"), data.get("status"), data.get("team_position"))
            )
        
        conn.commit()
        conn.close()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=400)


@app.get("/api/journey")
def get_journey():
    active_adv_id = get_active_adventure()
    c = db().cursor()
    rows = c.execute(
        "SELECT id, entry_type, pokemon_name, pokemon_level, evolved_to, location, capture_zone, destination, swapped_pokemon, "
        "trainer_name, trainer_class, trainer_team, deaths_in_battle, description, created_at FROM journey_entries "
        "WHERE adventure_id=? ORDER BY created_at ASC", (active_adv_id,)
    ).fetchall()
    result = []
    for r in rows:
        result.append({
            "id": r[0], "type": r[1], "pokemon": r[2], "level": r[3], "evolved_to": r[4],
            "location": r[5], "capture_zone": r[6], "destination": r[7], 
            "swapped_pokemon": r[8], "trainer_name": r[9], "trainer_class": r[10],
            "trainer_team": json.loads(r[11]) if r[11] else None,
            "deaths_in_battle": json.loads(r[12]) if r[12] else None,
            "description": r[13], "date": r[14]
        })
    return result


@app.post("/api/journal-entry")
async def post_journey_entry(request: Request):
    try:
        data = await request.json()
        active_adv_id = get_active_adventure()
        conn = db()
        c = conn.cursor()
        
        # If it's a capture or team change, update pokemon_state accordingly
        entry_type = data.get("type")
        pokemon_name = data.get("pokemon")
        pokemon_level = data.get("level")
        
        if entry_type == "pokemon_capture":
            destination = data.get("destination")  # "team" or "pc"
            team_pos = data.get("team_position") if destination == "team" else None
            c.execute(
                "INSERT INTO pokemon_state (adventure_id, pokemon_name, pokemon_level, nickname, status, team_position, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                (active_adv_id, pokemon_name, pokemon_level, data.get("nickname"), destination, team_pos)
            )
            
            # If pokemon was moved to PC, update the swapped one
            if data.get("swapped_pokemon"):
                c.execute(
                    "UPDATE pokemon_state SET status=? WHERE adventure_id=? AND pokemon_name=? ORDER BY created_at DESC LIMIT 1",
                    ("pc", active_adv_id, data.get("swapped_pokemon"))
                )
        
        elif entry_type == "pokemon_death":
            # Mark the pokemon as dead (whether it's in team or pc)
            c.execute(
                "UPDATE pokemon_state SET status=? WHERE adventure_id=? AND pokemon_name=? AND status IN ('team', 'pc') ORDER BY created_at DESC LIMIT 1",
                ("dead", active_adv_id, pokemon_name)
            )
        
        elif entry_type == "evolution":
            # Replace the pokemon with its evolved form in the same location
            evolved_to = data.get("evolved_to")
            team_pos = data.get("team_position")
            # Update the pokemon_state to change the name and level
            c.execute(
                "UPDATE pokemon_state SET pokemon_name=?, pokemon_level=? "
                "WHERE adventure_id=? AND pokemon_name=? ORDER BY created_at DESC LIMIT 1",
                (evolved_to, pokemon_level, active_adv_id, pokemon_name)
            )
        
        elif entry_type == "team_change":
            # Move pokemon from PC to team (and optionally swap one out)
            swapped_pokemon = data.get("swapped_pokemon")
            
            # Update PC pokemon to team
            c.execute(
                "UPDATE pokemon_state SET status=? WHERE adventure_id=? AND pokemon_name=? AND status=? ORDER BY created_at DESC LIMIT 1",
                ("team", active_adv_id, pokemon_name, "pc")
            )
            
            # If swapping, move the team pokemon to PC
            if swapped_pokemon:
                c.execute(
                    "UPDATE pokemon_state SET status=? WHERE adventure_id=? AND pokemon_name=? AND status=? ORDER BY created_at DESC LIMIT 1",
                    ("pc", active_adv_id, swapped_pokemon, "team")
                )
        
        # Insert journal entry
        c.execute(
            "INSERT INTO journey_entries "
            "(adventure_id, entry_type, pokemon_name, pokemon_level, evolved_to, location, capture_zone, destination, swapped_pokemon, "
            "trainer_name, trainer_class, trainer_id, trainer_team, deaths_in_battle, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (active_adv_id, entry_type, pokemon_name, pokemon_level, data.get("evolved_to"), data.get("location"), 
             data.get("capture_zone"), data.get("destination"), data.get("swapped_pokemon"),
             data.get("trainer_name"), data.get("trainer_class"), data.get("trainer_id"),
             json.dumps(data.get("trainer_team"), ensure_ascii=False) if data.get("trainer_team") else None,
             json.dumps(data.get("deaths_in_battle"), ensure_ascii=False) if data.get("deaths_in_battle") else None,
             data.get("description"))
        )
        
        conn.commit()
        entry_id = c.lastrowid
        conn.close()
        return {"ok": True, "id": entry_id}
    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "message": str(e) + "\n" + traceback.format_exc()}, status_code=400)


@app.delete("/api/journal-entry/{entry_id}")
def delete_journey_entry(entry_id: int):
    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM journey_entries WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/pokemon")
def get_pokemon(q: str = ""):
    c = db().cursor()
    rows = c.execute(
        "SELECT num,name,type,hp,atk,def_,spa,spd,spe,ability1,ability2,item FROM base_stats"
        + (" WHERE name LIKE ? ORDER BY num" if q else " ORDER BY num"),
        (f"%{q}%",) if q else ()
    ).fetchall()
    cols = ["num","name","type","hp","atk","def","spa","spd","spe","ability1","ability2","item"]
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        # TMs this pokemon can learn
        tms = c.execute("SELECT tm FROM tm_compat WHERE pokemon_name=? ORDER BY tm", (d["name"],)).fetchall()
        d["tms"] = [t[0] for t in tms]
        # Evolution info (from evolutions table = modified ones)
        evos = c.execute("SELECT to_poke,method FROM evolutions WHERE from_poke=?", (d["name"],)).fetchall()
        d["evolutions"] = [{"to": e[0], "method": e[1]} for e in evos]
        # evolves_to from movesets (always present, even unmodified)
        ms = c.execute("SELECT evolves_to FROM movesets WHERE name=?", (d["name"],)).fetchone()
        d["evolves_to"] = ms[0] if ms else None
        # Wild locations
        wild = c.execute("""
            SELECT DISTINCT ws.location, ws.type, wp.level
            FROM wild_sets ws
            JOIN wild_pokemon wp ON ws.id = wp.set_id
            WHERE wp.name = ?
            ORDER BY ws.location""", (d["name"],)).fetchall()
        d["wild"] = [{"location": w[0], "type": w[1], "level": w[2]} for w in wild]
        result.append(d)
    return result


@app.get("/api/movesets")
def get_movesets(q: str = ""):
    c = db().cursor()
    rows = c.execute(
        "SELECT name,evolves_to,level_moves,egg_moves FROM movesets"
        + (" WHERE name LIKE ? ORDER BY name" if q else " ORDER BY name"),
        (f"%{q}%",) if q else ()
    ).fetchall()
    return [{"name":r[0],"evolves_to":r[1],
             "level_moves":json.loads(r[2]),"egg_moves":json.loads(r[3])} for r in rows]


@app.get("/api/trainers")
def get_trainers(q: str = ""):
    c = db().cursor()
    rows = c.execute(
        "SELECT id,class,pokemon FROM trainers"
        + (" WHERE class LIKE ? OR pokemon LIKE ? ORDER BY id" if q else " ORDER BY id"),
        (f"%{q}%", f"%{q}%") if q else ()
    ).fetchall()
    return [{"id":r[0],"class":r[1],"pokemon":json.loads(r[2])} for r in rows]


@app.get("/api/wild")
def get_wild(q: str = ""):
    c = db().cursor()
    rows = c.execute(
        "SELECT ws.id,ws.location,ws.type,wp.name,wp.level FROM wild_sets ws "
        "JOIN wild_pokemon wp ON ws.id=wp.set_id"
        + (" WHERE ws.location LIKE ? OR wp.name LIKE ? ORDER BY ws.id" if q else " ORDER BY ws.id"),
        (f"%{q}%", f"%{q}%") if q else ()
    ).fetchall()
    by_loc = {}
    for r in rows:
        loc = r[1]
        if loc not in by_loc:
            by_loc[loc] = {"location": loc, "encounter_types": {}}
        et = r[2]
        if et not in by_loc[loc]["encounter_types"]:
            by_loc[loc]["encounter_types"][et] = []
        p = {"name": r[3], "level": r[4]}
        if not any(x["name"] == p["name"] for x in by_loc[loc]["encounter_types"][et]):
            by_loc[loc]["encounter_types"][et].append(p)
    return list(by_loc.values())


@app.get("/api/tms")
def get_tms(q: str = ""):
    c = db().cursor()
    rows = c.execute(
        "SELECT tm,move FROM tms"
        + (" WHERE tm LIKE ? OR move LIKE ? ORDER BY tm" if q else " ORDER BY tm"),
        (f"%{q}%", f"%{q}%") if q else ()
    ).fetchall()
    return [{"tm":r[0],"move":r[1]} for r in rows]


@app.get("/api/shops")
def get_shops(q: str = ""):
    c = db().cursor()
    rows = c.execute(
        "SELECT s.id,s.name,si.item FROM shops s JOIN shop_items si ON s.id=si.shop_id"
        + (" WHERE s.name LIKE ? OR si.item LIKE ?" if q else ""),
        (f"%{q}%", f"%{q}%") if q else ()
    ).fetchall()
    shops = {}
    for r in rows:
        if r[0] not in shops:
            shops[r[0]] = {"id":r[0],"name":r[1],"items":[]}
        shops[r[0]]["items"].append(r[2])
    return list(shops.values())
