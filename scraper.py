"""
Roco Kingdom wiki scraper.
Scrapes pokemon name, size range, weight range, and hatchability from:
https://wiki.biligame.com/rocom/精灵图鉴
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os
from typing import Optional, Tuple, List, Dict

BASE_URL = "https://wiki.biligame.com"
INDEX_URL = "https://wiki.biligame.com/rocom/%E7%B2%BE%E7%81%B5%E5%9B%BE%E9%89%B4"
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemon.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://wiki.biligame.com/",
}


def fetch(url: str, retries: int = 3, delay: float = 2.0) -> Optional[BeautifulSoup]:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
            print(f"  HTTP {resp.status_code} for {url}, attempt {attempt+1}/{retries}")
        except Exception as e:
            print(f"  Error fetching {url}: {e}, attempt {attempt+1}/{retries}")
        time.sleep(delay * (attempt + 1))
    return None


def get_pokemon_links(soup: BeautifulSoup) -> List[Dict]:
    """Extract pokemon names and links from the index page.
    Targets links inside wikitable rows (the pokemon dex table),
    falling back to KNOWN_POKEMON if the table can't be found.
    """
    links = []
    seen = set()

    # Strategy 1: look for a wikitable containing the pokemon dex
    # Pokemon entries are rows with a link that has title= attribute (wiki page title)
    tables = soup.find_all("table", class_="wikitable")
    source = []
    for table in tables:
        for a in table.find_all("a", href=re.compile(r"^/rocom/")):
            source.append(a)

    # Strategy 2: look inside the mw-parser-output content div
    if not source:
        content = soup.find("div", class_="mw-parser-output")
        if content:
            for a in content.find_all("a", href=re.compile(r"^/rocom/")):
                source.append(a)

    # Strategy 3: fall back to known list
    if not source:
        print("  Could not parse index page — using known pokemon list as fallback")
        return get_known_pokemon_links()

    # Filter: only include links that look like pokemon (Chinese characters in href)
    nav_skip = {
        "首页", "精灵筛选", "道具筛选", "技能筛选", "精灵蛋筛选", "邮件一览",
        "地图", "蛋组计算器", "阵容一览", "上传阵容", "伤害计算器", "克制计算器",
        "性格计算器", "升级经验表", "任务一览", "创建新页面", "测试页面",
        "分类", "模板", "帮助", "特殊", "Wiki", "WIKI",
    }

    for a in source:
        href = a.get("href", "")
        name = a.get_text(strip=True)

        if not name or len(name) < 2:
            continue
        if name in nav_skip:
            continue
        if any(kw in name for kw in ["筛选", "图鉴", "一览", "计算器", "经验表"]):
            continue
        if href in seen:
            continue
        seen.add(href)

        full_url = BASE_URL + href
        links.append({"name": name, "url": full_url, "path": href})

    # If still nothing useful (only nav links found), use fallback
    if len(links) < 10:
        print("  Index page links look like nav items — using known pokemon list as fallback")
        return get_known_pokemon_links()

    return links


def get_known_pokemon_links() -> List[Dict]:
    """Hardcoded full pokemon list scraped from 精灵图鉴 on 2025-04-04."""
    entries = [
        ("迪莫", "/rocom/%E8%BF%AA%E8%8E%AB"),
        ("喵喵", "/rocom/%E5%96%B5%E5%96%B5"),
        ("喵呜", "/rocom/%E5%96%B5%E5%91%9C"),
        ("魔力猫", "/rocom/%E9%AD%94%E5%8A%9B%E7%8C%AB"),
        ("火花", "/rocom/%E7%81%AB%E8%8A%B1"),
        ("焰火", "/rocom/%E7%84%B0%E7%81%AB"),
        ("火神", "/rocom/%E7%81%AB%E7%A5%9E"),
        ("水蓝蓝", "/rocom/%E6%B0%B4%E8%93%9D%E8%93%9D"),
        ("波波拉", "/rocom/%E6%B3%A2%E6%B3%A2%E6%8B%89"),
        ("水灵", "/rocom/%E6%B0%B4%E7%81%B5"),
        ("鸭吉吉", "/rocom/%E9%B8%AD%E5%90%89%E5%90%89%EF%BC%88%E8%93%AC%E6%9D%BE%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("板板壳", "/rocom/%E6%9D%BF%E6%9D%BF%E5%A3%B3%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("咔咔壳", "/rocom/%E5%92%94%E5%92%94%E5%A3%B3%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("水泡壳", "/rocom/%E6%B0%B4%E6%B3%A1%E5%A3%B3%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("锥尾羊", "/rocom/%E9%94%A5%E5%B0%BE%E7%BE%8A"),
        ("铃兰羊", "/rocom/%E9%93%83%E5%85%B0%E7%BE%8A"),
        ("花影羚羊", "/rocom/%E8%8A%B1%E5%BD%B1%E7%BE%9A%E7%BE%8A"),
        ("雪绒鸟", "/rocom/%E9%9B%AA%E7%BB%92%E9%B8%9F%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("冬羽雀", "/rocom/%E5%86%AC%E7%BE%BD%E9%9B%80%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("岚鸟", "/rocom/%E5%B2%9A%E9%B8%9F%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("小灵菇", "/rocom/%E5%B0%8F%E7%81%B5%E8%8F%87"),
        ("幻灵菇", "/rocom/%E5%B9%BB%E7%81%B5%E8%8F%87"),
        ("幻影灵菇", "/rocom/%E5%B9%BB%E5%BD%B1%E7%81%B5%E8%8F%87"),
        ("石肤蜥", "/rocom/%E7%9F%B3%E8%82%A4%E8%9C%A5%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("石刺蜥", "/rocom/%E7%9F%B3%E5%88%BA%E8%9C%A5%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("石冠王蜥", "/rocom/%E7%9F%B3%E5%86%A0%E7%8E%8B%E8%9C%A5%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("布是石", "/rocom/%E5%B8%83%E6%98%AF%E7%9F%B3"),
        ("布是岩", "/rocom/%E5%B8%83%E6%98%AF%E5%B2%A9"),
        ("布克棱岩", "/rocom/%E5%B8%83%E5%85%8B%E6%A3%B1%E5%B2%A9"),
        ("恶魔叮", "/rocom/%E6%81%B6%E9%AD%94%E5%8F%AE"),
        ("叮叮恶魔", "/rocom/%E5%8F%AE%E5%8F%AE%E6%81%B6%E9%AD%94"),
        ("毛毛", "/rocom/%E6%AF%9B%E6%AF%9B"),
        ("爬爬", "/rocom/%E7%88%AC%E7%88%AC"),
        ("化蝶", "/rocom/%E5%8C%96%E8%9D%B6%EF%BC%88%E5%B9%B3%E5%B8%B8%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("幽影树", "/rocom/%E5%B9%BD%E5%BD%B1%E6%A0%91"),
        ("小鼠獭", "/rocom/%E5%B0%8F%E9%BC%A0%E7%8D%AD"),
        ("燕尾獭", "/rocom/%E7%87%95%E5%B0%BE%E7%8D%AD"),
        ("卷胡巨獭", "/rocom/%E5%8D%B7%E8%83%A1%E5%B7%A8%E7%8D%AD"),
        ("矿晶虫", "/rocom/%E7%9F%BF%E6%99%B6%E8%99%AB"),
        ("晶石蜗", "/rocom/%E6%99%B6%E7%9F%B3%E8%9C%97%EF%BC%88%E8%A5%BF%E7%93%9C%E7%A2%A7%E7%8E%BA%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("奇丽草", "/rocom/%E5%A5%87%E4%B8%BD%E8%8D%89"),
        ("奇丽叶", "/rocom/%E5%A5%87%E4%B8%BD%E5%8F%B6"),
        ("奇丽花", "/rocom/%E5%A5%87%E4%B8%BD%E8%8A%B1"),
        ("丢丢", "/rocom/%E4%B8%A2%E4%B8%A2%EF%BC%88%E8%8D%89%E5%9C%B0%E9%99%84%E8%BF%91%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("卡卡虫", "/rocom/%E5%8D%A1%E5%8D%A1%E8%99%AB%EF%BC%88%E8%8D%89%E5%9C%B0%E9%99%84%E8%BF%91%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("卡瓦重", "/rocom/%E5%8D%A1%E7%93%A6%E9%87%8D%EF%BC%88%E8%8D%89%E5%9C%B0%E9%99%84%E8%BF%91%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("护主犬", "/rocom/%E6%8A%A4%E4%B8%BB%E7%8A%AC"),
        ("音速犬", "/rocom/%E9%9F%B3%E9%80%9F%E7%8A%AC"),
        ("绿耳松鼠", "/rocom/%E7%BB%BF%E8%80%B3%E6%9D%BE%E9%BC%A0"),
        ("抱枕松鼠", "/rocom/%E6%8A%B1%E6%9E%95%E6%9D%BE%E9%BC%A0"),
        ("蹦床松鼠", "/rocom/%E8%B9%A6%E5%BA%8A%E6%9D%BE%E9%BC%A0"),
        ("嘟嘟煲", "/rocom/%E5%98%9F%E5%98%9F%E7%85%B2"),
        ("嘟嘟锅", "/rocom/%E5%98%9F%E5%98%9F%E9%94%85"),
        ("小灵面", "/rocom/%E5%B0%8F%E7%81%B5%E9%9D%A2"),
        ("暗影灵面", "/rocom/%E6%9A%97%E5%BD%B1%E7%81%B5%E9%9D%A2%EF%BC%88%E7%9D%81%E7%9C%BC%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("幽冥眼", "/rocom/%E5%B9%BD%E5%86%A5%E7%9C%BC%EF%BC%88%E7%9D%81%E7%9C%BC%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("梦游", "/rocom/%E6%A2%A6%E6%B8%B8%EF%BC%88%E7%A9%BF%E6%97%A7%E7%9D%A1%E8%A1%A3%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("梦悠悠", "/rocom/%E6%A2%A6%E6%82%A0%E6%82%A0%EF%BC%88%E7%A9%BF%E6%97%A7%E7%9D%A1%E8%A1%A3%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("兽花蕾", "/rocom/%E5%85%BD%E8%8A%B1%E8%95%BE"),
        ("伏地兽", "/rocom/%E4%BC%8F%E5%9C%B0%E5%85%BD"),
        ("贪食鼹", "/rocom/%E8%B4%AA%E9%A3%9F%E9%BC%B9"),
        ("巨噬针鼹", "/rocom/%E5%B7%A8%E5%99%AC%E9%92%88%E9%BC%B9"),
        ("蹦蹦种子", "/rocom/%E8%B9%A6%E8%B9%A6%E7%A7%8D%E5%AD%90%EF%BC%88%E6%B5%B7%E7%A5%9E%E7%90%83%E5%BD%A2%E6%80%81%EF%BC%89"),
        ("蹦蹦草", "/rocom/%E8%B9%A6%E8%B9%A6%E8%8D%89%EF%BC%88%E6%B5%B7%E7%A5%9E%E7%90%83%E5%BD%A2%E6%80%81%EF%BC%89"),
        ("蹦蹦花", "/rocom/%E8%B9%A6%E8%B9%A6%E8%8A%B1%EF%BC%88%E6%B5%B7%E7%A5%9E%E7%90%83%E5%BD%A2%E6%80%81%EF%BC%89"),
        ("电咩咩", "/rocom/%E7%94%B5%E5%92%A9%E5%92%A9"),
        ("粉咩咩", "/rocom/%E7%B2%89%E5%92%A9%E5%92%A9"),
        ("电球咩咩", "/rocom/%E7%94%B5%E7%90%83%E5%92%A9%E5%92%A9"),
        ("蒲公英", "/rocom/%E8%92%B2%E5%85%AC%E8%8B%B1"),
        ("蒲公英娃娃", "/rocom/%E8%92%B2%E5%85%AC%E8%8B%B1%E5%A8%83%E5%A8%83"),
        ("伊贝儿", "/rocom/%E4%BC%8A%E8%B4%9D%E5%84%BF"),
        ("伊贝粉粉", "/rocom/%E4%BC%8A%E8%B4%9D%E7%B2%89%E7%B2%89"),
        ("白发懒人", "/rocom/%E7%99%BD%E5%8F%91%E6%87%92%E4%BA%BA"),
        ("动力猿", "/rocom/%E5%8A%A8%E5%8A%9B%E7%8C%BF"),
        ("瞌睡王", "/rocom/%E7%9E%8C%E7%9D%A1%E7%8E%8B"),
        ("海盔虫", "/rocom/%E6%B5%B7%E7%9B%94%E8%99%AB%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("刺盔虫", "/rocom/%E5%88%BA%E7%9B%94%E8%99%AB%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("千棘盔", "/rocom/%E5%8D%83%E6%A3%98%E7%9B%94%EF%BC%88%E6%9C%AC%E6%9D%A5%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("菊花梨", "/rocom/%E8%8F%8A%E8%8A%B1%E6%A2%A8"),
        ("小星光", "/rocom/%E5%B0%8F%E6%98%9F%E5%85%89%EF%BC%88%E6%98%9F%E5%85%89%E8%83%BD%E9%87%8F%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("星光狮", "/rocom/%E6%98%9F%E5%85%89%E7%8B%AE%EF%BC%88%E6%98%9F%E5%85%89%E8%83%BD%E9%87%8F%E7%9A%84%E6%A0%B7%E5%AD%90%EF%BC%89"),
        ("一窝蜂", "/rocom/%E4%B8%80%E7%AA%9D%E8%9C%82"),
        ("黄蜂后", "/rocom/%E9%BB%84%E8%9C%82%E5%90%8E"),
        ("女王蜂", "/rocom/%E5%A5%B3%E7%8E%8B%E8%9C%82"),
        ("小夜", "/rocom/%E5%B0%8F%E5%A4%9C"),
        ("紫夜", "/rocom/%E7%B4%AB%E5%A4%9C"),
        ("朔夜伊芙", "/rocom/%E6%9C%94%E5%A4%9C%E4%BC%8A%E8%8A%99"),
        ("乖乖鹄", "/rocom/%E4%B9%96%E4%B9%96%E9%B9%84"),
        ("蓝珠天鹅", "/rocom/%E8%93%9D%E7%8F%A0%E5%A4%A9%E9%B9%85"),
        ("翠顶夫人", "/rocom/%E7%BF%A0%E9%A1%B6%E5%A4%AB%E4%BA%BA"),
        ("黑羽夫人", "/rocom/%E9%BB%91%E7%BE%BD%E5%A4%AB%E4%BA%BA"),
        ("锤头鹳", "/rocom/%E9%94%A4%E5%A4%B4%E9%B9%B3"),
        ("绿草精灵", "/rocom/%E7%BB%BF%E8%8D%89%E7%B2%BE%E7%81%B5"),
        ("魔草巫灵", "/rocom/%E9%AD%94%E8%8D%89%E5%B7%AB%E7%81%B5"),
        ("记忆石", "/rocom/%E8%AE%B0%E5%BF%86%E7%9F%B3"),
        ("咔咔羽毛", "/rocom/%E5%92%94%E5%92%94%E7%BE%BD%E6%AF%9B"),
        ("咔咔雀", "/rocom/%E5%92%94%E5%92%94%E9%9B%80"),
        ("咔咔鸟", "/rocom/%E5%92%94%E5%92%94%E9%B8%9F"),
        ("小草虫", "/rocom/%E5%B0%8F%E8%8D%89%E8%99%AB"),
        ("草衣虫", "/rocom/%E8%8D%89%E8%A1%A3%E8%99%AB"),
        ("花衣蝶", "/rocom/%E8%8A%B1%E8%A1%A3%E8%9D%B6"),
    ]
    return [
        {"name": name, "url": BASE_URL + path, "path": path}
        for name, path in entries
    ]


def parse_range(text: str) -> Optional[Tuple[float, float]]:
    """Parse a range string like '0.54~0.78' into (min, max) floats."""
    text = text.strip()
    m = re.match(r"([\d.]+)\s*[~～]\s*([\d.]+)", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    # Single value
    m = re.match(r"^([\d.]+)$", text)
    if m:
        v = float(m.group(1))
        return v, v
    return None


def scrape_pokemon_page(url: str, expected_name: str) -> Optional[Dict]:
    """Scrape a single pokemon page and return structured data."""
    soup = fetch(url)
    if not soup:
        return None

    # --- Name ---
    # Try the page title / h1
    name = expected_name
    h1 = soup.find("h1", id="firstHeading")
    if h1:
        raw = h1.get_text(strip=True)
        # Strip number prefix like "NO001." if present
        raw = re.sub(r"^NO\d+\.\s*", "", raw)
        if raw:
            name = raw

    # --- Physique (size + weight) ---
    size_min = size_max = weight_min = weight_max = None

    physique_div = soup.find("div", class_="rocom_sprite_info_physique")
    if physique_div:
        items = physique_div.find_all("li")
        for item in items:
            # The icon img has alt text telling us if it's height or weight
            icon_img = item.find("img")
            is_height = False
            is_weight = False
            if icon_img:
                alt = icon_img.get("alt", "")
                is_height = "身高" in alt or "高" in alt
                is_weight = "体重" in alt or "重" in alt

            # The unit paragraph tells us too
            unit_texts = [p.get_text(strip=True) for p in item.find_all("p")]
            if "M" in unit_texts:
                is_height = True
            if "KG" in unit_texts:
                is_weight = True

            # Find the range value (the <p> that matches number~number pattern)
            for p in item.find_all("p"):
                txt = p.get_text(strip=True)
                parsed = parse_range(txt)
                if parsed:
                    if is_height:
                        size_min, size_max = parsed
                    elif is_weight:
                        weight_min, weight_max = parsed

    # Fallback: if we couldn't determine height vs weight from icon, use position
    if physique_div and (size_min is None or weight_min is None):
        all_ranges = []
        for p in physique_div.find_all("p"):
            txt = p.get_text(strip=True)
            parsed = parse_range(txt)
            if parsed:
                all_ranges.append(parsed)
        if len(all_ranges) >= 2:
            size_min, size_max = all_ranges[0]
            weight_min, weight_max = all_ranges[1]
        elif len(all_ranges) == 1:
            # Can't distinguish, skip
            pass

    if size_min is None or weight_min is None:
        print(f"  WARNING: Could not parse physique for {name} ({url})")
        return None

    # --- Evolution: determine if this is a base (hatchable) form ---
    is_hatchable = detect_base_form(soup, name)

    return {
        "name": name,
        "url": url,
        "size_min": size_min,
        "size_max": size_max,
        "weight_min": weight_min,
        "weight_max": weight_max,
        "is_hatchable": is_hatchable,
    }


def detect_base_form(soup: BeautifulSoup, pokemon_name: str) -> bool:
    """
    Return True if this pokemon is a base (first / only) form and can be hatched.

    Detection logic (based on actual wiki HTML):
      - <div class="rocom_sprite_grament_name font-mainfeiziti"><p>NO002.喵喵</p></div>
        gives us the canonical name of this page's pokemon.
      - <div class="rocom_spirit_evolution_1"> contains an <a title="…"> whose title
        attribute names the first pokemon in the evolution chain.
      If those two names match, this pokemon IS the first evolution → hatchable.
      If rocom_spirit_evolution_1 is absent (standalone with no chain), also hatchable.
    """
    # 1. Get canonical name from grament_name div (strip "NO001." prefix and form suffix)
    grament_div = soup.find("div", class_="rocom_sprite_grament_name")
    if grament_div:
        raw = grament_div.get_text(strip=True)
        page_name = re.sub(r"^NO\d+\.\s*", "", raw).strip()
        # Also strip any form variant suffix like （极昼的样子）
        page_name = re.sub(r"[（(][^）)]*[）)]", "", page_name).strip()
    else:
        page_name = re.sub(r"[（(][^）)]*[）)]", "", pokemon_name).strip()

    # 2. Find the evolution-1 div
    evo1_div = soup.find("div", class_="rocom_spirit_evolution_1")
    if evo1_div is None:
        # No evolution chain present → standalone pokemon → hatchable
        return True

    # 3. Get the title of the first-evolution link
    evo1_link = evo1_div.find("a")
    if evo1_link is None:
        return True

    evo1_name = evo1_link.get("title", "").strip()
    if not evo1_name:
        evo1_name = evo1_link.get_text(strip=True)
    # Strip form variant suffix from evo1 name too (e.g. 乌达（极昼的样子）→ 乌达)
    evo1_name = re.sub(r"[（(][^）)]*[）)]", "", evo1_name).strip()

    # 4. Match: if the page pokemon IS the first evolution, it's hatchable
    return page_name == evo1_name


def scrape_all(delay: float = 1.5) -> List[Dict]:
    """Scrape all pokemon and return the full list."""
    print("Fetching index page...")
    index_soup = fetch(INDEX_URL)

    if index_soup:
        links = get_pokemon_links(index_soup)
    else:
        print("Index page unavailable — using known pokemon list")
        links = get_known_pokemon_links()

    print(f"Found {len(links)} pokemon links")

    pokemon_list = []
    for i, link in enumerate(links):
        print(f"[{i+1}/{len(links)}] Scraping {link['name']} ...")
        data = scrape_pokemon_page(link["url"], link["name"])
        if data:
            pokemon_list.append(data)
            print(f"  ✓ {data['name']}: size {data['size_min']}~{data['size_max']}M, "
                  f"weight {data['weight_min']}~{data['weight_max']}KG, "
                  f"hatchable={data['is_hatchable']}")
        else:
            print(f"  ✗ Failed to scrape {link['name']}")
        time.sleep(delay)

    return pokemon_list


def main():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)

    print("=== Roco Kingdom Pokemon Scraper ===\n")
    pokemon_list = scrape_all()

    hatchable = [p for p in pokemon_list if p["is_hatchable"]]
    print(f"\n=== Done ===")
    print(f"Total scraped: {len(pokemon_list)}")
    print(f"Hatchable (base forms): {len(hatchable)}")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(pokemon_list, f, ensure_ascii=False, indent=2)

    print(f"Saved to {DATA_PATH}")


if __name__ == "__main__":
    main()
