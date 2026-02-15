"""
OddsPortal Prva NL Scraper - Complete Version
Scrapes all seasons & matches for Croatia Prva NL (1. HNL). Outputs CSV per season.
Scrapes markets: 1X2, O/U, AH, BTTS, HT/FT with opening and closing odds
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
import csv
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

# Target league configuration
LEAGUE_NAME = "Croatia Prva NL"
LEAGUE_SLUG = "croatia/prva-nl"
OUTPUT_PREFIX = LEAGUE_SLUG.replace('/', '-')


def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.page_load_strategy = 'eager'
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    return driver


def accept_cookies(driver):
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        btn.click()
        time.sleep(0.3)
    except:
        pass


def click_tab(driver, tab_name):
    try:
        tabs = driver.find_elements(By.XPATH, f"//*[contains(text(), '{tab_name}')]")
        for t in tabs:
            if t.is_displayed():
                driver.execute_script("arguments[0].click();", t)
                time.sleep(0.3)
                return True
    except:
        pass
    return False


def click_more_menu(driver, option_name):
    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.2)
        more = driver.find_element(By.XPATH, "//button[contains(., 'More') or contains(., 'MORE')]")
        driver.execute_script("arguments[0].click();", more)
        time.sleep(0.3)
        opt = driver.find_element(By.XPATH, f"//*[contains(text(), '{option_name}')]")
        driver.execute_script("arguments[0].click();", opt)
        time.sleep(0.5)
        return True
    except:
        return False


def hover_get_opening(driver, actions, element):
    """Hover and get opening odds (single)."""
    if not element:
        return ''
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.1)
        actions.move_to_element(element).perform()
        time.sleep(0.3)
        body = driver.find_element(By.TAG_NAME, 'body').text
        
        m = re.search(r'Opening odds:\s*\n\s*\d+\s+\w+,?\s*\d+:\d+\s*\n\s*(\d+\.\d+)', body, re.I)
        if m:
            return m.group(1)
    except:
        pass
    return ''


def hover_get_pair_opening(driver, actions, element):
    """Hover on grandparent and get PAIR of opening odds (Over/Home, Under/Away)."""
    if not element:
        return '', ''
    try:
        grandparent = element.find_element(By.XPATH, "./../..")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", grandparent)
        time.sleep(0.3)
        actions.move_to_element(grandparent).perform()
        time.sleep(1.0)
        body = driver.find_element(By.TAG_NAME, 'body').text
        
        m = re.search(r'Opening odds:\s*\n\s*\d+\s+\w+,?\s*\d+:\d+\s*\n\s*(\d+\.\d+)\s*\n\s*\([^)]*\)\s*\n\s*(\d+\.\d+)', body, re.I)
        if m:
            return m.group(1), m.group(2)
    except:
        pass
    return '', ''


def expand_and_get_opening_single(driver, actions, element):
    """Hover on div.odds-cell element and get SINGLE opening odd."""
    if not element:
        return ''
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.2)
        actions.move_to_element(element).perform()
        time.sleep(1.0)
        body = driver.find_element(By.TAG_NAME, 'body').text
        
        m = re.search(r'Opening odds:\s*\n\s*\d+\s+\w+,?\s*\d+:\d+\s*\n\s*(\d+\.\d+)', body, re.I)
        if m:
            return m.group(1)
    except:
        pass
    return ''


def expand_and_get_ou_opening_pair(driver, actions, label_element):
    """For O/U: Expand row, find div.odds-cell elements, hover on each for opening."""
    if not label_element:
        return '', ''
    
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label_element)
        time.sleep(0.2)
        
        row = label_element.find_element(By.XPATH, "./../..")
        label_y = label_element.location['y']
        driver.execute_script("arguments[0].click();", row)
        time.sleep(1.2)
        
        all_odds_cells = driver.find_elements(By.XPATH, "//div[contains(@class, 'odds-cell')]")
        expanded_cells = []
        for el in all_odds_cells:
            try:
                t = el.text.strip()
                if re.match(r'^\d+\.\d{2}$', t) and el.is_displayed():
                    loc = el.location
                    if loc['y'] > label_y + 30:
                        expanded_cells.append({'v': t, 'e': el, 'x': loc['x'], 'y': loc['y']})
            except:
                pass
        
        if not expanded_cells:
            return '', ''
        
        expanded_cells.sort(key=lambda x: (x['y'], x['x']))
        
        y_groups = {}
        for o in expanded_cells:
            y_key = (o['y'] // 30) * 30
            if y_key not in y_groups:
                y_groups[y_key] = []
            y_groups[y_key].append(o)
        
        for y in sorted(y_groups.keys()):
            row_cells = y_groups[y]
            row_cells.sort(key=lambda x: x['x'])
            
            unique = []
            last_x = -100
            for o in row_cells:
                if o['x'] - last_x > 40:
                    unique.append(o)
                    last_x = o['x']
            
            if len(unique) >= 2:
                over_open = expand_and_get_opening_single(driver, actions, unique[0]['e'])
                under_open = expand_and_get_opening_single(driver, actions, unique[1]['e'])
                return over_open, under_open
        
        return '', ''
        
    except Exception as e:
        return '', ''


def find_all_odds_elements(driver, y_min=200, y_max=900):
    """Find all odds elements on page."""
    elements = driver.find_elements(By.XPATH, "//p | //div")
    odds = []
    seen = set()
    
    for el in elements:
        try:
            if not el.is_displayed():
                continue
            t = el.text.strip()
            if re.match(r'^\d+\.\d{2}$', t):
                loc = el.location
                size = el.size
                if y_min < loc['y'] < y_max and size.get('width', 999) < 150:
                    key = (round(loc['x'], -1), round(loc['y'], -1))
                    if key not in seen:
                        seen.add(key)
                        odds.append({'v': t, 'e': el, 'x': loc['x'], 'y': loc['y']})
        except:
            pass
    
    odds.sort(key=lambda x: (x['y'], x['x']))
    return odds


def find_rows_with_n_odds(odds, n, max_rows=20):
    """Find rows with exactly n odds."""
    if not odds:
        return []
    
    y_values = sorted(set(round(o['y'], -1) for o in odds))
    rows = []
    
    for y in y_values[:max_rows]:
        row = [o for o in odds if abs(o['y'] - y) < 30]
        row.sort(key=lambda x: x['x'])
        if len(row) >= n:
            filtered_row = []
            last_x = -100
            for o in row:
                if o['x'] - last_x > 40:
                    filtered_row.append(o)
                    last_x = o['x']
            if len(filtered_row) >= n:
                rows.append(filtered_row[:n])
    
    return rows


def parse_closing_from_body(body, pattern):
    """Parse closing odds from body text."""
    m = re.search(rf'{re.escape(pattern)}\s*\n\s*\d+\s*\n\s*(\d+\.\d{{2}})\s*\n\s*(\d+\.\d{{2}})', body)
    if m:
        return m.group(1), m.group(2)
    return '', ''


def expand_and_get_opening_pair(driver, actions, label_element):
    """Expand row by clicking, find first bookmaker row, hover for opening."""
    if not label_element:
        return '', ''
    
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label_element)
        time.sleep(0.2)
        
        row = label_element.find_element(By.XPATH, "./../..")
        label_y = label_element.location['y']
        driver.execute_script("arguments[0].click();", row)
        time.sleep(1.0)
        
        all_odds = driver.find_elements(By.XPATH, "//p[contains(@class, 'height-content')]")
        expanded_odds = []
        for el in all_odds:
            try:
                t = el.text.strip()
                if re.match(r'^\d+\.\d{2}$', t) and el.is_displayed():
                    loc = el.location
                    if loc['y'] > label_y + 50:
                        expanded_odds.append({'v': t, 'e': el, 'x': loc['x'], 'y': loc['y']})
            except:
                pass
        
        if not expanded_odds:
            return '', ''
        
        expanded_odds.sort(key=lambda x: (x['y'], x['x']))
        
        y_groups = {}
        for o in expanded_odds:
            y_key = (o['y'] // 30) * 30
            if y_key not in y_groups:
                y_groups[y_key] = []
            y_groups[y_key].append(o)
        
        for y in sorted(y_groups.keys()):
            row_odds = y_groups[y]
            row_odds.sort(key=lambda x: x['x'])
            
            unique = []
            last_x = -100
            for o in row_odds:
                if o['x'] - last_x > 40:
                    unique.append(o)
                    last_x = o['x']
            
            if len(unique) >= 2:
                return hover_get_pair_opening(driver, actions, unique[0]['e'])
        
        return '', ''
        
    except Exception as e:
        return '', ''


def scrape_match(url, season, worker_id=1):
    """Scrape match."""
    driver = None
    t0 = time.time()
    
    try:
        driver = create_driver()
        driver.get(url)
        time.sleep(1.5)
        
        accept_cookies(driver)
        actions = ActionChains(driver)
        
        data = {}
        data['League'] = LEAGUE_NAME
        data['Season'] = season
        data['URL'] = url
        
        body = driver.find_element(By.TAG_NAME, 'body').text
        
        # Info
        try:
            title = driver.title
            m = re.search(r'^([^-|]+?)\s*[-–]+\s*([^-|]+?)(?:\s*[-|]|$)', title)
            if m:
                data['Home'] = m.group(1).strip()
                away = m.group(2).strip()
                away = re.sub(r'\s*(Odds|Predictions|H2H|Results|OddsPortal).*$', '', away, flags=re.I).strip()
                data['Away'] = away
        except:
            pass
        
        m = re.search(r'(\d{1,2}\s+\w{3,}\s+\d{4})', body)
        if m: data['Date'] = m.group(1)
        
        m = re.search(r'Final result\s*(\d+)\s*[-–:]\s*(\d+)', body, re.I)
        if m: data['Final_Result'] = f"{m.group(1)}:{m.group(2)}"
        
        m = re.search(r'\((\d+)\s*[-–:,]\s*(\d+)', body)
        if m: data['HT_Result'] = f"{m.group(1)}:{m.group(2)}"
        
        print(f"  [{worker_id}] {data.get('Home', '?')} vs {data.get('Away', '?')}", end=" | ", flush=True)
        
        # === 1X2 ===
        click_tab(driver, '1X2')
        driver.execute_script("window.scrollBy(0, 200);")
        time.sleep(0.3)
        
        all_odds = find_all_odds_elements(driver)
        rows_3 = find_rows_with_n_odds(all_odds, 3)
        
        if rows_3:
            row = rows_3[0]
            data['1X2_Close_1'] = row[0]['v']
            data['1X2_Close_X'] = row[1]['v']
            data['1X2_Close_2'] = row[2]['v']
            data['1X2_Open_1'] = hover_get_opening(driver, actions, row[0]['e'])
            data['1X2_Open_X'] = hover_get_opening(driver, actions, row[1]['e'])
            data['1X2_Open_2'] = hover_get_opening(driver, actions, row[2]['e'])
        print("1X2✓", end=" ", flush=True)
        
        # === O/U ===
        ou_lines = [2, 2.25, 2.5, 2.75, 3]
        
        for line in ou_lines:
            click_tab(driver, 'Over/Under')
            driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(0.4)
            
            body = driver.find_element(By.TAG_NAME, 'body').text
            
            pattern = f"Over/Under +{line}"
            over_c, under_c = parse_closing_from_body(body, pattern)
            
            line_str = str(line).replace('.', '_')
            data[f'OU_{line_str}_Over_Close'] = over_c
            data[f'OU_{line_str}_Under_Close'] = under_c
            data[f'OU_{line_str}_Over_Open'] = ''
            data[f'OU_{line_str}_Under_Open'] = ''
            
            if over_c and under_c:
                label_els = driver.find_elements(By.XPATH, f"//p[contains(text(), 'Over/Under +{line}')]")
                for label in label_els:
                    if label.is_displayed():
                        over_open, under_open = expand_and_get_ou_opening_pair(driver, actions, label)
                        if over_open and under_open:
                            data[f'OU_{line_str}_Over_Open'] = over_open
                            data[f'OU_{line_str}_Under_Open'] = under_open
                        break
        
        print("O/U✓", end=" ", flush=True)
        
        # === AH ===
        ah_lines = [0, -0.25, -0.5, -0.75, -1, -1.25, 0.25, 0.5, 0.75, 1, 1.25]
        
        for line in ah_lines:
            click_tab(driver, 'Asian Handicap')
            driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(0.4)
            
            body = driver.find_element(By.TAG_NAME, 'body').text
            
            if line == 0:
                pattern = "Asian Handicap 0"
                search_text = "Asian Handicap 0"
            elif line > 0:
                pattern = f"Asian Handicap +{line}"
                search_text = f"Asian Handicap +{line}"
            else:
                pattern = f"Asian Handicap {line}"
                search_text = f"Asian Handicap {line}"
            
            home_c, away_c = parse_closing_from_body(body, pattern)
            
            if line > 0:
                line_str = f"plus_{str(line).replace('.', '_')}"
            elif line < 0:
                line_str = f"minus_{str(abs(line)).replace('.', '_')}"
            else:
                line_str = "0"
            
            data[f'AH_{line_str}_Home_Close'] = home_c
            data[f'AH_{line_str}_Away_Close'] = away_c
            data[f'AH_{line_str}_Home_Open'] = ''
            data[f'AH_{line_str}_Away_Open'] = ''
            
            if home_c and away_c:
                label_els = driver.find_elements(By.XPATH, f"//p[contains(text(), '{search_text}')]")
                for label in label_els:
                    if label.is_displayed():
                        home_open, away_open = expand_and_get_opening_pair(driver, actions, label)
                        if home_open and away_open:
                            data[f'AH_{line_str}_Home_Open'] = home_open
                            data[f'AH_{line_str}_Away_Open'] = away_open
                        break
        
        print("AH✓", end=" ", flush=True)
        
        # === BTTS ===
        click_tab(driver, 'Both Teams')
        driver.execute_script("window.scrollBy(0, 200);")
        time.sleep(0.5)
        
        btts_cells = driver.find_elements(By.XPATH, "//div[contains(@class, 'odds-cell')]")
        btts_odds = []
        for el in btts_cells:
            try:
                t = el.text.strip()
                if re.match(r'^\d+\.\d{2}$', t) and el.is_displayed():
                    loc = el.location
                    if 200 < loc['y'] < 900:
                        btts_odds.append({'v': t, 'e': el, 'x': loc['x'], 'y': loc['y']})
            except:
                pass
        
        if btts_odds:
            btts_odds.sort(key=lambda x: (x['y'], x['x']))
            y_groups = {}
            for o in btts_odds:
                y_key = (o['y'] // 30) * 30
                if y_key not in y_groups:
                    y_groups[y_key] = []
                y_groups[y_key].append(o)
            
            rows_with_2 = []
            for y in sorted(y_groups.keys()):
                row = y_groups[y]
                row.sort(key=lambda x: x['x'])
                if len(row) >= 2:
                    rows_with_2.append(row[:2])
            
            if rows_with_2:
                data['BTTS_Yes_Close'] = rows_with_2[0][0]['v']
                data['BTTS_No_Close'] = rows_with_2[0][1]['v']
                
                data['BTTS_Yes_Open'] = ''
                data['BTTS_No_Open'] = ''
                
                # Hover na svaki element zasebno za opening odds
                for row in rows_with_2[:5]:
                    yes_open = expand_and_get_opening_single(driver, actions, row[0]['e'])
                    no_open = expand_and_get_opening_single(driver, actions, row[1]['e'])
                    if yes_open and no_open:
                        data['BTTS_Yes_Open'] = yes_open
                        data['BTTS_No_Open'] = no_open
                        break
                    elif yes_open:
                        data['BTTS_Yes_Open'] = yes_open
                    elif no_open:
                        data['BTTS_No_Open'] = no_open
        
        print("BTTS✓", end="", flush=True)
        
        elapsed = time.time() - t0
        print(f" | {elapsed:.1f}s")
        
        return data
        
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        if driver:
            driver.quit()


def collect_urls_from_page(driver, season):
    """Collect all match URLs from current page."""
    urls = set()
    links = driver.find_elements(By.XPATH, f"//a[contains(@href, '/{LEAGUE_SLUG}-{season}/')]")
    for link in links:
        try:
            href = link.get_attribute('href')
            if href:
                parts = href.rstrip('/').split('/')
                if len(parts) >= 7:
                    match_id = parts[-1]
                    if len(match_id) > 5 and '-' in match_id:
                        urls.add(href)
        except:
            continue
    return urls


def expand_page_content(driver):
    """Scroll and click 'Show more' to expand page content."""
    clicks = 0
    for i in range(50):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.4)
        try:
            show_more = driver.find_elements(By.XPATH, "//a[contains(text(), 'Show more')]")
            for btn in show_more:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    clicks += 1
                    time.sleep(1.5)
                    break
        except:
            pass
    
    if clicks > 0:
        print(f"({clicks} show more)", end=" ")


def get_available_seasons(league_slug):
    """Return list of available season strings for a league (e.g. '2024-2025')."""
    driver = None
    try:
        driver = create_driver()
        url = f"https://www.oddsportal.com/football/{league_slug}/results/"
        driver.get(url)
        accept_cookies(driver)
        time.sleep(2)
        seasons = set()
        # look for season-specific links on the page
        anchors = driver.find_elements(By.XPATH, f"//a[contains(@href, '/{league_slug}') and contains(@href, 'results')]")
        for a in anchors:
            try:
                href = a.get_attribute('href') or ''
                m = re.search(rf"{re.escape(league_slug)}[-/](\d{{4}}(?:-\d{{4}})?)", href)
                if m:
                    seasons.add(m.group(1))
            except:
                pass
        # try dropdown options as fallback
        try:
            opts = driver.find_elements(By.CSS_SELECTOR, "select[id*='season'] option")
            for o in opts:
                v = (o.get_attribute('value') or o.text or '').strip()
                if re.match(r'\d{4}(?:-\d{4})?', v):
                    seasons.add(v)
        except:
            pass
        if not seasons:
            # last-resort fallback: current season and previous season
            cy = time.localtime().tm_year
            seasons = {f"{cy-1}-{cy}", f"{cy}-{cy+1}"}
        return sorted(seasons, reverse=True)
    finally:
        if driver:
            driver.quit()


def get_season_match_urls(season):
    """Get all match URLs for season - including all pagination pages."""
    driver = None
    try:
        driver = create_driver()
        base_url = f"https://www.oddsportal.com/football/{LEAGUE_SLUG}-{season}/results/"
        driver.get(base_url)
        accept_cookies(driver)
        time.sleep(4)
        
        all_urls = set()
        
        # === PAGE 1 ===
        print(f"  Page 1...", end=" ", flush=True)
        
        # Scroll before expanding to load initial content
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        expand_page_content(driver)
        
        # Final scroll to ensure everything is loaded
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.4)
        
        urls = collect_urls_from_page(driver, season)
        all_urls.update(urls)
        print(f"{len(urls)} matches")
        
        # Find all page numbers in pagination
        pagination_items = driver.find_elements(By.CSS_SELECTOR, ".pagination-link")
        page_numbers = []
        for item in pagination_items:
            text = item.text.strip()
            if text.isdigit():
                page_numbers.append(int(text))
        
        max_page = max(page_numbers) if page_numbers else 1
        print(f"  Found {max_page} pages total")
        
        # === OTHER PAGES ===
        for page_num in range(2, max_page + 1):
            print(f"  Page {page_num}...", end=" ", flush=True)
            try:
                # Scroll to top before clicking pagination
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.3)
                
                pagination_items = driver.find_elements(By.CSS_SELECTOR, ".pagination-link")
                clicked = False
                for item in pagination_items:
                    if item.text.strip() == str(page_num):
                        driver.execute_script("arguments[0].click();", item)
                        time.sleep(3)
                        clicked = True
                        break
                
                if not clicked:
                    print("skip")
                    continue
                
                # Scroll to load content
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.5)
                
                expand_page_content(driver)
                
                # Final scroll
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.4)
                
                urls = collect_urls_from_page(driver, season)
                new_urls = urls - all_urls
                all_urls.update(urls)
                print(f"{len(new_urls)} new matches (total on page: {len(urls)})")
                
            except Exception as e:
                print(f"error: {e}")
        
        print(f"  Total: {len(all_urls)} match URLs")
        return list(all_urls)
        
    finally:
        if driver:
            driver.quit()


def scrape_season(season, num_workers=8):
    """Scrape entire season with multiprocessing and save results continuously."""
    import threading
    
    print(f"\n{'='*60}")
    print(f"Scraping {LEAGUE_NAME} - Season {season}")
    print("="*60)
    
    # Get all match URLs
    print("Getting match URLs...")
    urls = get_season_match_urls(season)
    print(f"Found {len(urls)} matches")
    
    if not urls:
        print("No matches found!")
        return
    
    # Output file (use absolute path and robust header creation)
    output_file = os.path.abspath(f"{OUTPUT_PREFIX}_{season}.csv")
    
    # Define fixed fieldnames in correct order
    fieldnames = [
        'League', 'Season', 'URL', 'Home', 'Away', 'Date', 'Final_Result', 'HT_Result',
        '1X2_Close_1', '1X2_Close_X', '1X2_Close_2', '1X2_Open_1', '1X2_Open_X', '1X2_Open_2',
        'OU_2_Over_Close', 'OU_2_Under_Close', 'OU_2_Over_Open', 'OU_2_Under_Open',
        'OU_2_25_Over_Close', 'OU_2_25_Under_Close', 'OU_2_25_Over_Open', 'OU_2_25_Under_Open',
        'OU_2_5_Over_Close', 'OU_2_5_Under_Close', 'OU_2_5_Over_Open', 'OU_2_5_Under_Open',
        'OU_2_75_Over_Close', 'OU_2_75_Under_Close', 'OU_2_75_Over_Open', 'OU_2_75_Under_Open',
        'OU_3_Over_Close', 'OU_3_Under_Close', 'OU_3_Over_Open', 'OU_3_Under_Open',
        'AH_0_Home_Close', 'AH_0_Away_Close', 'AH_0_Home_Open', 'AH_0_Away_Open',
        'AH_minus_0_25_Home_Close', 'AH_minus_0_25_Away_Close', 'AH_minus_0_25_Home_Open', 'AH_minus_0_25_Away_Open',
        'AH_minus_0_5_Home_Close', 'AH_minus_0_5_Away_Close', 'AH_minus_0_5_Home_Open', 'AH_minus_0_5_Away_Open',
        'AH_minus_0_75_Home_Close', 'AH_minus_0_75_Away_Close', 'AH_minus_0_75_Home_Open', 'AH_minus_0_75_Away_Open',
        'AH_minus_1_Home_Close', 'AH_minus_1_Away_Close', 'AH_minus_1_Home_Open', 'AH_minus_1_Away_Open',
        'AH_minus_1_25_Home_Close', 'AH_minus_1_25_Away_Close', 'AH_minus_1_25_Home_Open', 'AH_minus_1_25_Away_Open',
        'AH_plus_0_25_Home_Close', 'AH_plus_0_25_Away_Close', 'AH_plus_0_25_Home_Open', 'AH_plus_0_25_Away_Open',
        'AH_plus_0_5_Home_Close', 'AH_plus_0_5_Away_Close', 'AH_plus_0_5_Home_Open', 'AH_plus_0_5_Away_Open',
        'AH_plus_0_75_Home_Close', 'AH_plus_0_75_Away_Close', 'AH_plus_0_75_Home_Open', 'AH_plus_0_75_Away_Open',
        'AH_plus_1_Home_Close', 'AH_plus_1_Away_Close', 'AH_plus_1_Home_Open', 'AH_plus_1_Away_Open',
        'AH_plus_1_25_Home_Close', 'AH_plus_1_25_Away_Close', 'AH_plus_1_25_Home_Open', 'AH_plus_1_25_Away_Open',
        'BTTS_Yes_Close', 'BTTS_No_Close', 'BTTS_Yes_Open', 'BTTS_No_Open'
    ]
    
    # Create or resume CSV (skip already scraped matches)
    print(f"\nSaving results to: {output_file}")
    print("Each match will be saved immediately after scraping.\n")

    existing_count = 0
    scraped_urls = set()
    if os.path.exists(output_file):
        try:
            with open(output_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    u = (row.get('URL') or '').strip()
                    if u:
                        scraped_urls.add(u)
            existing_count = len(scraped_urls)
            if existing_count:
                print(f"Found {existing_count} already-scraped matches in {output_file}; will resume.")
        except Exception as e:
            print(f"Warning: could not read existing file {output_file}: {e}")
            scraped_urls = set()
            existing_count = 0

    # Filter out already-scraped URLs
    remaining_urls = [u for u in urls if u not in scraped_urls]
    print(f"{len(remaining_urls)} matches remaining to scrape (out of {len(urls)})")

    if not remaining_urls:
        print("All matches already scraped — nothing to do.")
        return

    # Ensure header exists (create if missing)
    if not os.path.exists(output_file):
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
            print(f"CSV header written -> {output_file}")
        except Exception as e:
            print(f"ERROR: cannot create output file {output_file}: {e}")
            raise
    else:
        print(f"Appending to existing file -> {output_file}")
    
    # Lock for thread-safe file writing
    file_lock = threading.Lock()
    results_count = existing_count if 'existing_count' in locals() else 0
    
    # Scrape matches
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(scrape_match, url, season, i % num_workers + 1): url for i, url in enumerate(remaining_urls)}
        for i, future in enumerate(as_completed(futures)):
            url = futures[future]
            try:
                data = future.result()
                if data:
                    # Ensure all fields exist with default empty string
                    for field in fieldnames:
                        if field not in data:
                            data[field] = ''
                    
                    # Save immediately to CSV
                    with file_lock:
                        with open(output_file, 'a', newline='', encoding='utf-8') as f:
                            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                            writer.writerow(data)
                        
                        results_count += 1
                        print(f"[{results_count}/{len(urls)}] ✓ {data.get('Home', '?')} vs {data.get('Away', '?')}")
                        
            except Exception as e:
                print(f"[{i+1}/{len(urls)}] ✗ Error: {e}")
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"SUCCESS: Saved {results_count} matches to {output_file}")
    print("="*60)
    
    return results_count


if __name__ == "__main__":
    import sys
    
    # CLI overrides
    cli_league_slug = None
    cli_league_name = None
    
    if len(sys.argv) > 1:
        seasons = []
        num_workers = 8
        run_all = False
        
        for arg in sys.argv[1:]:
            if arg.startswith('--workers='):
                num_workers = int(arg.split('=')[1])
            elif arg.startswith('--league='):
                cli_league_slug = arg.split('=', 1)[1]
            elif arg.startswith('--league-name='):
                cli_league_name = arg.split('=', 1)[1]
            elif arg in ('all', '--all'):
                run_all = True
            else:
                seasons.append(arg)
        
        # Apply CLI league override if provided
        if cli_league_slug:
            LEAGUE_SLUG = cli_league_slug
            OUTPUT_PREFIX = LEAGUE_SLUG.replace('/', '-')
            if cli_league_name:
                LEAGUE_NAME = cli_league_name
            else:
                # Derive readable league name from slug
                try:
                    part = LEAGUE_SLUG.split('/')[1]
                    LEAGUE_NAME = ' '.join(p.capitalize() for p in part.split('-'))
                except Exception:
                    LEAGUE_NAME = LEAGUE_SLUG
            print(f"Overriding league -> {LEAGUE_NAME} ({LEAGUE_SLUG})")
        
        if run_all:
            seasons = get_available_seasons(LEAGUE_SLUG)
            if not seasons:
                print("No seasons found on the site; aborting.")
                sys.exit(1)
        
        for season in seasons:
            scrape_season(season, num_workers=num_workers)
    else:
        # Default: scrape the latest known season for the configured league
        latest = None
        try:
            s = get_available_seasons(LEAGUE_SLUG)
            latest = s[0] if s else "2024-2025"
        except:
            latest = "2024-2025"
        scrape_season(latest, num_workers=3)
