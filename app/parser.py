"""
Parser for Universal Pokemon Randomizer ZX log files.
"""
import re
from typing import Dict, List, Any


# Known names for language detection
_FR_NAMES = {"BULBIZARRE","SALAMECHE","CARAPUCE","RATTATA","PIKACHU","MEWTWO","EVOLI","DRACAUFEU"}
_EN_NAMES = {"BULBASAUR","CHARMANDER","SQUIRTLE","RATTATA","PIKACHU","MEWTWO","EEVEE","CHARIZARD"}

def detect_language(text: str) -> str:
    upper = text.upper()
    fr_score = sum(1 for n in _FR_NAMES if n in upper)
    en_score = sum(1 for n in _EN_NAMES if n in upper)
    return "fr" if fr_score >= en_score else "en"

def parse_log(text: str) -> Dict[str, Any]:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.splitlines()
    sections = split_sections(lines)
    lang = detect_language(text)
    return {
        "lang":         lang,
        "base_stats":   parse_base_stats(sections.get("Pokemon Base Stats & Types", [])),
        "movesets":     parse_movesets(sections.get("Pokemon Movesets", [])),
        "trainers":     parse_trainers(sections.get("Trainers Pokemon", [])),
        "wild":         parse_wild(sections.get("Wild Pokemon", [])),
        "pickup_items": parse_pickup_items(sections.get("Pickup Items", [])),
        "shops":        parse_shops(sections.get("Shops", [])),
        "trades":       parse_trades(sections.get("In-Game Trades", [])),
        "tms":          parse_tms(sections.get("TM Moves", [])),
        "tm_compat":    parse_tm_compat(sections.get("TM Compatibility", [])),
        "evolutions":   parse_evolutions(sections.get("Removing Impossible Evolutions", [])),
    }


def split_sections(lines):
    sections = {}
    current_name = None
    current_lines = []
    header_re = re.compile(r'^--(.+?)--\s*$')
    for line in lines:
        m = header_re.match(line)
        if m:
            if current_name:
                sections.setdefault(current_name, []).extend(current_lines)
            current_name = m.group(1).strip()
            current_lines = []
        elif current_name:
            current_lines.append(line)
    if current_name:
        sections.setdefault(current_name, []).extend(current_lines)
    return sections


def parse_base_stats(lines):
    stats = []
    for line in lines:
        if '|' not in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 9:
            continue
        try:
            num = int(parts[0])
        except ValueError:
            continue
        stats.append({
            "num": num, "name": parts[1], "type": parts[2],
            "hp": _int(parts[3]), "atk": _int(parts[4]), "def": _int(parts[5]),
            "spa": _int(parts[6]), "spd": _int(parts[7]), "spe": _int(parts[8]),
            "ability1": parts[9] if len(parts) > 9 else "",
            "ability2": parts[10] if len(parts) > 10 else "",
            "item": parts[11] if len(parts) > 11 else "",
        })
    return stats


def parse_movesets(lines):
    movesets = []
    current = None
    poke_header = re.compile(r'^\d{3}\s+(\S+.*?)\s*->\s*(\S+.*?)\s*$')
    level_move  = re.compile(r'^Level\s+(\d+)\s*:\s*(.+)$')
    egg_move    = re.compile(r'^\s+-\s+(.+)$')
    stat_line   = re.compile(r'^(HP|ATK|DEF|SPA|SPD|SPE)\s+\d+')
    in_egg = False
    for line in lines:
        m = poke_header.match(line)
        if m:
            if current:
                movesets.append(current)
            current = {"name": m.group(1).strip(), "evolves_to": m.group(2).strip(),
                       "level_moves": [], "egg_moves": []}
            in_egg = False
            continue
        if current is None:
            continue
        if stat_line.match(line):
            continue
        if line.strip() == "Egg Moves:":
            in_egg = True
            continue
        if in_egg:
            m2 = egg_move.match(line)
            if m2:
                current["egg_moves"].append(m2.group(1).strip())
            elif line.strip() == "":
                in_egg = False
            continue
        m3 = level_move.match(line)
        if m3:
            current["level_moves"].append({"level": int(m3.group(1)), "move": m3.group(2).strip()})
    if current:
        movesets.append(current)
    return movesets


def parse_trainers(lines):
    trainers = []
    trainer_re = re.compile(r'^#(\d+)\s+\(([^)]+)\)@[0-9A-Fa-f]+\s+-\s+(.+)$')
    entry_re   = re.compile(r'^(.+?)\s+Lv(\d+)$')
    for line in lines:
        m = trainer_re.match(line)
        if not m:
            continue
        raw_team = m.group(3).strip()
        entries = re.split(r',\s*(?=[A-ZÉÈÀÂÊÎÔÛÙÏÜ♀♂])', raw_team)
        pokemon = []
        for entry in entries:
            entry = entry.strip()
            em = entry_re.match(entry)
            if not em:
                continue
            name_item = em.group(1).strip()
            level = int(em.group(2))
            if '@' in name_item:
                parts = name_item.split('@', 1)
                name, item = parts[0].strip(), parts[1].strip()
            else:
                name, item = name_item, ""
            pokemon.append({"name": name, "item": item, "level": level})
        if pokemon:
            trainers.append({"id": int(m.group(1)), "class": m.group(2).strip(), "pokemon": pokemon})
    return trainers


def parse_wild(lines):
    sets = []
    current = None
    set_header = re.compile(r'^Set #(\d+)\s+-\s+(.+?)\s+([\w/]+)\s+\(rate=(\d+)\)')
    poke_line  = re.compile(r'^([A-ZÉÈÀÂÊÎÔÛÙÏÜ♀♂][A-ZÉÈÀÂÊÎÔÛÙÏÜa-záéèàâêîôûùïü♀♂\.\-\' ]+?)\s+Lv(\d+)\s+HP')
    for line in lines:
        m = set_header.match(line)
        if m:
            if current:
                sets.append(current)
            current = {"set": int(m.group(1)), "location": m.group(2).strip(),
                       "type": m.group(3).strip(), "rate": int(m.group(4)), "pokemon": []}
            continue
        if current:
            m2 = poke_line.match(line)
            if m2:
                name, level = m2.group(1).strip(), int(m2.group(2))
                if not any(p["name"] == name and p["level"] == level for p in current["pokemon"]):
                    current["pokemon"].append({"name": name, "level": level})
    if current:
        sets.append(current)
    return sets


def parse_pickup_items(lines):
    result = []
    current_range = None
    seen_ranges = set()
    range_re = re.compile(r'^Level\s+(\d+)-(\d+)\s*$')
    item_re  = re.compile(r'^(\d+)%:\s+(.+)$')
    for line in lines:
        m = range_re.match(line)
        if m:
            key = (m.group(1), m.group(2))
            if key in seen_ranges:
                current_range = None
                continue
            seen_ranges.add(key)
            current_range = {"range": f"{m.group(1)}-{m.group(2)}", "items": []}
            result.append(current_range)
            continue
        if current_range:
            m2 = item_re.match(line)
            if m2:
                for item in m2.group(2).split(','):
                    current_range["items"].append({"item": item.strip(), "chance": int(m2.group(1))})
    return result


def parse_shops(lines):
    shops = []
    current = None
    for line in lines:
        if line.strip() == "":
            continue
        if line.startswith("- "):
            if current:
                current["items"].append(line[2:].strip())
        else:
            current = {"name": line.strip(), "items": []}
            shops.append(current)
    return shops


def parse_trades(lines):
    trades = []
    trade_re = re.compile(r'^Trade\s+(\S+)\s+->\s+(\S+)\s+the\s+(\S+)\s+->\s+(\S+)\s+->\s+(\S+)\s+the\s+(\S+)')
    for line in lines:
        m = trade_re.match(line)
        if m:
            trades.append({"give": m.group(1), "receive_nick": m.group(2), "receive": m.group(3),
                           "give2": m.group(4), "receive_nick2": m.group(5), "receive2": m.group(6)})
    return trades


def parse_tms(lines):
    """Format: TM01 MOVE NAME (no 'is' keyword)"""
    tms = []
    tm_re = re.compile(r'^(TM\d+|HM\d+)\s+(.+)$')
    for line in lines:
        m = tm_re.match(line.strip())
        if m:
            tms.append({"tm": m.group(1), "move": m.group(2).strip()})
    return tms


def parse_tm_compat(lines):
    """Format: NUM NAME | - | TM04 MOVE | - | ..."""
    compat = []
    for line in lines:
        if '|' not in line:
            continue
        parts = line.split('|')
        header = parts[0].strip()
        m = re.match(r'^\d+\s+(.+?)\s*$', header)
        if not m:
            continue
        name = m.group(1).strip()
        tms = []
        for cell in parts[1:]:
            cell = cell.strip()
            if not cell or cell == '-':
                continue
            tm_m = re.match(r'^(TM\d+|HM\d+)', cell)
            if tm_m:
                tms.append(tm_m.group(1))
        if name:
            compat.append({"name": name, "tms": tms})
    return compat


def parse_evolutions(lines):
    """Format: POKEMON -> POKEMON at level N / using a ITEM"""
    evos = []
    evo_re = re.compile(r'^(\S+.*?)\s+->\s+(\S+.*?)\s+(at level (\d+)|using a (.+))\s*$')
    for line in lines:
        m = evo_re.match(line.strip())
        if m:
            method = f"Niveau {m.group(4)}" if m.group(4) else f"Pierre : {m.group(5)}"
            evos.append({"from": m.group(1).strip(), "to": m.group(2).strip(), "method": method})
    return evos


def _int(s):
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return 0
