"""Copy the Amphoreus vault folder into the Quartz content folder for the public site.

Usage: python sync_site.py <vault Amphoreus folder> <quartz content folder>

What it does to the site copy (the vault itself is never changed):
- skips videos and canvases
- moves everything in "Lorekeeper Notes" up one level so the sidebar is shorter
- hides character secrets (Delmore's Norgorber lines, Mayuri's death-vision blurb)
- turns each Lorekeeper page's "# Heading" into its page title
- drops the portrait under the banner, since the banner already shows it
- splits Journal.md into one page per session, in Act / Arc folders
  (a third argument can point at a newer Journal.md, e.g. the one in personal notes)
- builds the Light Calendar page from each session's in-world date
- writes the home page
"""
import os, re, shutil, sys

sys.stdout.reconfigure(encoding='utf-8')
src, dst = sys.argv[1], sys.argv[2]
# optional: a newer Journal.md to use instead of the vault's copy (the user's personal notes)
JOURNAL = sys.argv[3] if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
SKIP_EXT = {'.mp4', '.canvas'}
TITLES = {'A_Travelers_Guide_to_the_Light_Calendar.md': "A Traveler's Guide to the Light Calendar"}


def scrub(rel, text):
    """Nothing is hidden from the site at the moment; add rules here if that changes."""
    return text


def set_title(text, title):
    title = title.replace('"', '\\"')
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not m:
        return f'---\ntitle: "{title}"\n---\n' + text
    if re.search(r'^title:', m.group(1), re.M):
        return text
    return f'---\n{m.group(1)}\ntitle: "{title}"\n---\n' + text[m.end():]


def lift_title(text):
    """Make the first '# Heading' the page title and remove it from the body."""
    m = re.match(r'(---\n.*?\n---\n)?\s*# ([^\n]+)\n', text, re.S)
    if not m:
        return text
    head = m.group(1) or ''
    return set_title(head + text[m.end():], m.group(2).strip())


def drop_portrait(text):
    if not re.search(r'^banner:', text, re.M):
        return text
    return re.sub(r'\n!\[\[[^\]|]+\.(png|jpe?g|webp)\|\d+\]\]\n', '\n', text, count=1)


# ---------- Journal ----------
NUMS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
        'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50}


def words_to_int(w):
    total = 0
    for part in w.lower().split('-'):
        if part.isdigit():
            return int(part)
        if part not in NUMS:
            return None
        total += NUMS[part]
    return total


def clean(s):
    return re.sub(r'\s+', ' ', s.replace('*', '')).strip()


def safe(s):
    return re.sub(r'[\\/:*?"<>|\[\]#^]', '', s).strip().rstrip('.')


def JOURNAL_ART(height):
    """Cyrene's book cover as the banner for journal pages (if the image exists)."""
    if not os.path.exists(os.path.join(src, 'Images', 'Cyrene Book-banner.png')):
        return []
    return ['banner: "![[Cyrene Book-banner.png]]"', f'banner-height: {height}', 'banner-y: 50',
            'icon-image: "![[Cyrene Book-icon.png]]"']


def split_journal(text, out):
    body = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)
    act = arc = None
    sessions = []  # dicts
    cur = None
    for line in body.split('\n'):
        if line.startswith('# '):
            act = clean(line[2:]); continue
        if line.startswith('## '):
            arc = clean(line[3:]); continue
        m = re.match(r'### (.*)', line)
        if m:
            h = clean(m.group(1))
            sm = re.match(r'Session ([\w-]+):\s*(.*?)\s*(\d{1,2}/\d{1,2}/\d{2,4})?\s*$', h, re.I)
            num = words_to_int(sm.group(1)) if sm else None
            name = sm.group(2).strip() if sm else h
            date = sm.group(3) if sm else None
            cur = dict(act=act, arc=arc, num=num, name=name, date=date, lines=[])
            sessions.append(cur)
            continue
        if cur is not None:
            cur['lines'].append(line)

    # drop placeholders for sessions not played yet (Session Thirty-Nine: [])
    sessions = [s for s in sessions if s['name'].replace('[]', '').strip()]
    for s in sessions:
        s['days'] = session_days(s['lines'])
        if s['num'] in SESSION_DAYS:
            s['days'] = [d for d in SESSION_DAYS[s['num']]]

    def folder(label):
        # "Act 0: The Prologue (Session 1-24)" -> "Act 0 - The Prologue"
        label = re.sub(r'\s*\(Session[^)]*\)', '', label)
        label = label.replace('[]', '').strip()
        label = re.sub(r':\s*', ' - ', label).strip(' -')
        return safe(label)

    for s in sessions:
        s['title'] = f"Session {s['num']}: {s['name']}" if s['num'] else s['name']
        s['file'] = f"Session {s['num']:02d} - {safe(s['name'])}" if s['num'] else safe(s['name'])
        s['path'] = '/'.join(['Journal', folder(s['act']), folder(s['arc']), s['file']])

    for i, s in enumerate(sessions):
        prev_s = sessions[i - 1] if i > 0 else None
        next_s = sessions[i + 1] if i + 1 < len(sessions) else None
        nav = []
        if prev_s:
            nav.append(f"← [[{prev_s['path']}|{prev_s['title']}]]")
        if next_s:
            nav.append(f"[[{next_s['path']}|{next_s['title']}]] →")
        fm = ['---', f'title: "{s["title"]}"'] + JOURNAL_ART(140)
        if s['date']:
            fm.append(f'played: "{s["date"]}"')
        fm += ['tags: [session]', '---']
        content = '\n'.join(s['lines']).strip('\n')
        # videos aren't copied to the site
        content = re.sub(r'!?\[\[[^\n]*?\.(mp4|webm|mov)(\|[^\n]*?)?\]\]', '*(video not included on the site)*', content)
        arc_label = re.sub(r':?\s*\[\]', '', s['arc'] or '')
        page = '\n'.join(fm) + f"\n*{arc_label}*\n\n" + content + '\n\n---\n' + ' · '.join(nav) + '\n'
        p = os.path.join(out, *s['path'].split('/')) + '.md'
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w', encoding='utf-8', newline='\n').write(page)

    # Journal landing page
    lines = ['---', 'title: "Session Journal"'] + JOURNAL_ART(280) + ['---',
             'Every session so far, newest at the bottom.', '']
    last_act = last_arc = None
    for s in sessions:
        if s['act'] != last_act:
            lines += ['', f"## {s['act']}"]; last_act = s['act']
        if s['arc'] != last_arc:
            arc_heading = re.sub(r':?\s*\[\]', '', s['arc'] or '')
            lines += ['', '### ' + arc_heading]; last_arc = s['arc']
        when = f" · *{lc_short(s['days'][0])}*" if s.get('days') else ''
        lines.append(f"- [[{s['path']}|{s['title']}]]" + (f" · {s['date']}" if s['date'] else '') + when)
    open(os.path.join(out, 'Journal', 'index.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    return sessions


# ---------- Light Calendar ----------
# From "A Traveler's Guide to the Light Calendar": 12 months of 31 days, 7-day weeks.
# Weeks run straight on across months and years; the journal fixes 1 Month of Joy, 4931 as an Eosdas.
LC_MONTHS = [  # (Amphorean, Astrean, season, patron)
    ('Gate', 'Eirostus', 'Fate', 'Janus'), ('Balance', 'Tharmion', 'Fate', 'Talanton'),
    ('Evernight', 'Elumir', 'Fate', 'Oronyx'), ('Cultivation', 'Ysil', 'Pillar', 'Georios'),
    ('Joy', 'Phareon', 'Pillar', 'Phagousa'), ('Everday', 'Calantheion', 'Pillar', 'Aquila'),
    ('Freedom', 'Velkris', 'Creation', 'Kephale'), ('Reaping', 'Dusmir', 'Creation', 'Cerces'),
    ('Weaving', 'Glymerion', 'Creation', 'Mnestia'), ('Strife', 'Nerastein', 'Calamity', 'Nikador'),
    ('Mourning', 'Selenir', 'Calamity', 'Thanatos'), ('Fortune', 'Thanareth', 'Calamity', 'Zagreus'),
]
LC_DAYS = ['Eosdas', 'Geodas', 'Hydadas', 'Pyrodas', 'Aerodas', 'Mnemodas', 'Selenodas']
LC_ASTREAN_DAYS = ['Mortdas', 'Musedas', 'Anardas', 'Middas', 'Horudas', 'Astardas', 'Wevdas']
LC_SEASONS = {
    'Fate': 'The year begins: quiet, new contracts and new starts. Evernight is the closest thing to winter.',
    'Pillar': "Planting, abundance and the year's brightest light. Everday is the hottest stretch.",
    'Creation': "The harvest months: Kephale's rest, Cerces' labor and Mnestia's festivals of memory.",
    'Calamity': "The year closes: storage, gladiatorial games, the burial of the dead and Zagreus' Spirit Day.",
}
LC_MONTH_NUM = {m[0].lower(): i for i, m in enumerate(LC_MONTHS)}
LC_DAYS_IN_MONTH = 31
DATE_RE = re.compile(r'(\d{1,2})\s+Month of\s+([A-Za-z]+),?\s*(\d{3,5})')


# Sessions that played out on more than one day (the rest happen on the last date
# in their date line). (year, month index, day); month 4 = Joy.
SESSION_DAYS = {
    11: [(4931, 4, 8), (4931, 4, 10)],
    21: [(4931, 4, 21), (4931, 4, 22)],
}


def session_days(lines):
    """The in-world day a session is played on: the last date in its date line.

    A range like "29 Month of Joy - 1 Month of Everday" only shows time passing;
    the session itself happens on the final day.
    """
    head = [l for l in lines if l.strip()][:3]
    found = []
    for l in head:
        for d, m, y in DATE_RE.findall(l):
            if m.lower() in LC_MONTH_NUM:
                found.append((int(y), LC_MONTH_NUM[m.lower()], int(d)))
    return [max(found)] if found else []


def session_weather(lines):
    for l in [l for l in lines if l.strip()][:5]:
        if re.search(r'humidity|precipitation|overcast', l, re.I):
            m = re.search(r'\(([^()]*overcast[^()]*)\)', l, re.I)
            return clean(m.group(1) if m else l)
    return ''


LC_ANCHOR = (4931, 4, 1)  # an Eosdas


def lc_ordinal(y, m, d):
    return y * 12 * LC_DAYS_IN_MONTH + m * LC_DAYS_IN_MONTH + (d - 1)


def lc_weekday(y, m, d):
    return (lc_ordinal(y, m, d) - lc_ordinal(*LC_ANCHOR)) % 7


def lc_name(day_tuple, astrean=False):
    y, m, d = day_tuple
    if astrean:
        return f'{LC_ASTREAN_DAYS[lc_weekday(y, m, d)]}, {d} {LC_MONTHS[m][1]}'
    return f'{LC_DAYS[lc_weekday(y, m, d)]}, {d} Month of {LC_MONTHS[m][0]}, {y}'


def lc_short(day_tuple):
    y, m, d = day_tuple
    return f'{d} {LC_MONTHS[m][0]}'


def lc_anchor(day_tuple):
    y, m, d = day_tuple
    return f'd-{y}-{LC_MONTHS[m][0].lower()}-{d}'


def session_url(s):
    return '/'.join(slugify_seg(p) for p in s['path'].split('/'))


def calendar_page(sessions):
    by_day = {}
    for s in sessions:
        for day in s.get('days', []):
            by_day.setdefault(day, []).append(s)
    if not by_day:
        return
    today = max(by_day)
    years = sorted({d[0] for d in by_day})
    H = []
    H.append('<div class="lc">')
    H.append('<div class="lc-today"><span>Today in Amphoreus</span>'
             f'<b>{lc_name(today)}</b><small>Astrean reckoning: {lc_name(today, True)}</small></div>')
    H.append('<div class="lc-legend"><span><i class="lc-key ev"></i>a day we played through</span>'
             '<span><i class="lc-key now"></i>where the story stands</span>'
             '<span><i class="lc-key rest"></i>Selenodas, the rest day</span></div>')
    for y in years:
        if len(years) > 1:
            H.append(f'<h2 class="lc-year">Year {y}</h2>')
        for season in ['Fate', 'Pillar', 'Creation', 'Calamity']:
            H.append(f'<div class="lc-season"><div class="lc-season-head"><b>Season of {season}</b>'
                     f'<span>{LC_SEASONS[season]}</span></div><div class="lc-months">')
            for mi, (am, ast, sea, patron) in enumerate(LC_MONTHS):
                if sea != season:
                    continue
                busy = any(k[0] == y and k[1] == mi for k in by_day)
                cells = ''.join(f'<span class="lc-wd{" rest" if i == 6 else ""}" title="{LC_DAYS[i]} ({LC_ASTREAN_DAYS[i]})">'
                                f'{LC_DAYS[i][:2]}</span>' for i in range(7))
                cells += '<span class="lc-pad"></span>' * lc_weekday(y, mi, 1)
                for d in range(1, LC_DAYS_IN_MONTH + 1):
                    key = (y, mi, d)
                    cls = ['lc-day']
                    if lc_weekday(y, mi, d) == 6:
                        cls.append('rest')
                    if key == today:
                        cls.append('now')
                    if key in by_day:
                        cls.append('ev')
                        nums = ', '.join(str(s['num']) for s in by_day[key])
                        tip = f'{lc_name(key)}: session{"s" if len(by_day[key]) > 1 else ""} {nums}'
                        cells += f'<a class="{" ".join(cls)}" href="#{lc_anchor(key)}" title="{tip}">{d}</a>'
                    else:
                        cells += f'<span class="{" ".join(cls)}" title="{lc_name(key)}">{d}</span>'
                H.append(f'<div class="lc-month{" busy" if busy else ""}"><div class="lc-mhead">'
                         f'<b>Month of {am}</b><small>{ast} · {patron}</small></div>'
                         f'<div class="lc-grid">{cells}</div></div>')
            H.append('</div></div>')
    # timeline of the days we have played
    H.append('<h2 id="the-days-so-far">The days so far</h2>')
    H.append('<div class="lc-timeline">')
    for key in sorted(by_day):
        y, m, d = key
        items = []
        for s in by_day[key]:
            extra = f' <small>{session_weather(s["lines"])}</small>' if session_weather(s['lines']) else ''
            items.append(f'<li><a class="internal" href="{session_url(s)}">{s["title"]}</a>{extra}</li>')
        H.append(f'<div class="lc-entry{" now" if key == today else ""}" id="{lc_anchor(key)}">'
                 f'<div class="lc-date"><b>{d}</b><span>{LC_MONTHS[m][0]}</span></div>'
                 f'<div class="lc-body"><div class="lc-dayname">{lc_name(key)}'
                 f'<small>{lc_name(key, True)}</small></div><ul>{"".join(items)}</ul></div></div>')
    H.append('</div></div>')
    page = ['---', 'title: "The Light Calendar"', 'banner: "![[Kephale.png]]"', 'banner-height: 220',
            'banner-y: 30', '---',
            'The year in Amphoreus runs on the Light Calendar, Kephale\'s gift to humanity: twelve months '
            'of 31 days, each kept by a Titan, in four divine seasons. The week starts on **Eosdas** and '
            'rests on **Selenodas**, running straight on from one month into the next. Gold days are the ones the party has lived through; click one to see '
            'which sessions happened then.',
            '',
            "For the hours of the day and the Astrean names, see [[A_Travelers_Guide_to_the_Light_Calendar|"
            "A Traveler's Guide to the Light Calendar]].",
            '',
            ''.join(H), '']
    open(os.path.join(dst, 'Calendar.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(page))
    print('calendar:', len(by_day), 'days, today is', lc_name(today))
    return today


# ---------- Home page ----------
def home(sessions, today=None):
    latest = sessions[-1] if sessions else None
    party = ['Caledor', 'Delmore', 'Franzen Bonotelli', 'Kenkai Ventura', 'Mayuri', 'Sir Caerwyn Kyrn',
             'Yuichi Highrose', 'Zuzros Rhiesis']
    heirs = ['Aglaea', 'Anaxagoras', 'Castorice', 'Cerydra', 'Cipher', 'Hyacinthia', 'Hysilens', 'Mydeimos',
             'Phainon', 'Terravox', 'Tribios']
    def slug(s):
        return s.replace(' ', '-')

    cards = []
    for n in party:
        has_icon = os.path.exists(os.path.join(src, 'Images', f'{n}-icon.png'))
        img = (f'<img src="Images/{slug(n)}-icon.png" alt="">' if has_icon
               else '<span class="party-card-blank"></span>')
        cards.append(f'<a class="party-card internal" href="Party/{slug(n)}">{img}<span>{n}</span></a>')
    rows = ['<div class="party-grid">' + ''.join(cards) + '</div>']
    out = [
        '---',
        'title: "Amphoreus — Twelve Coreflames"',
        'banner: "![[Kephale.png]]"',
        'banner-height: 300',
        'banner-y: 40',
        '---',
        'A record of our campaign in **Amphoreus**, a dying land of twelve Titans, where the Chrysos Heirs chase '
        'the coreflames to hold back the Black Tide.',
        '',
    ]
    if latest:
        out += ['> [!tip] Latest session',
                f"> [[{latest['path']}|{latest['title']}]]" + (f" · {latest['date']}" if latest['date'] else ''),
                '> ', '> [[Journal/index|Read the whole journal →]]', '']
    if today:
        out += ['> [!calendar] Today in Amphoreus',
                f'> **{lc_name(today)}** · [[Calendar|Open the Light Calendar →]]', '']
    out += ['## The Party', ''] + rows + ['', '[[Party/index|Skill points, paragon skills and former members →]]', '']
    out += ['## Quests', '', '- [[Party Quests]]: the Flame-Chase, the Descent Beneath the Temple, and the party\'s open leads.', '']
    out += ['## The World', '',
            '- **Places:** [[Amphoreus Info|Amphoreus]] · [[Okhema Info And Occupants|Okhema]] · '
            '[[Janusopolis Info and Occupants|Janusopolis]] · [[Philoxenion]]',
            '- **Chrysos Heirs:** ' + ' · '.join(f'[[{h}]]' for h in heirs),
            '- **Titans:** [[Cerces]] · [[Georios]] · [[Janus]] · [[Kephale]] · [[Talanton]]',
            '- **Skyfire Dragons:** [[Commander Deva]] · [[Ione Kalyx]] · [[Jossum]]',
            "- **Reference:** [[Calendar|The Light Calendar]] · "
            "[[A_Travelers_Guide_to_the_Light_Calendar|A Traveler's Guide to the Light Calendar]]", '']
    return '\n'.join(out)


# ---------- Party progress (skill points + paragon) ----------
FORMER = {'Ulixes'}
ALIASES = {'ulixies': 'Ulixes', 'ulixes': 'Ulixes', 'zurzros': 'Zuzros Rhiesis', 'zuzros': 'Zuzros Rhiesis',
           'sir caerwyn': 'Sir Caerwyn Kyrn', 'yuichi': 'Yuichi Highrose', 'kenkai': 'Kenkai Ventura',
           'franzen': 'Franzen Bonotelli', 'caledor': 'Caledor', 'delmore': 'Delmore', 'mayuri': 'Mayuri'}


def read_tracker(path):
    """Skill point tracker.md -> {name: {'points':..,'verse':..,'paragon':..}}"""
    data, section = {}, 'points'
    if not os.path.exists(path):
        return data
    for line in open(path, encoding='utf-8').read().split('\n'):
        l = line.strip()
        if not l:
            continue
        low = l.lower()
        if low.startswith('1st verse'):
            section = 'verse'; continue
        if low.startswith('paragon'):
            section = 'paragon'; continue
        if ':' in l:
            key, val = l.split(':', 1)
        else:
            m = re.match(r'([A-Za-z ]+?)\s+(\S.*)$', l)
            if not m:
                continue
            key, val = m.group(1), m.group(2)
        name = ALIASES.get(key.strip().lower())
        if name:
            data.setdefault(name, {})[section] = val.strip()
    return data


def add_progress(text, info):
    if not info:
        return text
    rows = ['> [!abstract] 📈 Progress', '> | | |', '> | :-- | :-- |']
    if 'points' in info:
        rows.append(f"> | **Skill points** | {info['points']} |")
    if 'verse' in info:
        rows.append(f"> | **1st Verse full price** | {info['verse']} |")
    if 'paragon' in info:
        rows.append(f"> | **Paragon skill** | {info['paragon']} |")
    block = '\n'.join(rows) + '\n\n'
    if '> [!tip] 🤝 Ties' in text:
        return text.replace('> [!tip] 🤝 Ties', block + '> [!tip] 🤝 Ties', 1)
    return text + '\n' + block


# ---------- Gallery pages ----------
def slugify_seg(s):
    return s.replace(' ', '-')


def url(from_dir, to_path):
    """Link to a target as a path from the site root.

    Quartz rewrites every link in a page as if it were written from the root of
    the notes, then makes it relative for the page itself, so a root path is
    the only form that comes out right on every page.
    """
    target = os.path.relpath(to_path, dst).replace('\\', '/')
    return '/'.join(slugify_seg(p) for p in target.split('/'))


def page_info(path):
    t = open(path, encoding='utf-8').read()
    fm = re.match(r'---\n(.*?)\n---\n', t, re.S)
    fmt = fm.group(1) if fm else ''
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', fmt, re.M)
    icon = re.search(r'^icon-image:\s*"?!?\[\[([^\]|]+)', fmt, re.M)
    summary = ''
    m = re.search(r'> \[!quote\][^\n]*\n> ([^\n]+)', t)
    if m:
        summary = m.group(1).strip()
    else:
        m = re.search(r'^\*([^*\n]+)\*\s*$', t[fm.end() if fm else 0:], re.M)
        if m:
            summary = m.group(1).strip()
    if 'party member' in summary.lower():
        anc = re.search(r'\| \*\*Ancestry\*\* \| ([^|]+) \|', t)
        cls = re.search(r'\| \*\*Class\*\* \| ([^|]+) \|', t)
        if anc or cls:
            summary = ' — '.join(x.group(1).strip() for x in (anc, cls) if x) + '.'
    first = re.match(r'(.+?[.!?])(\s|$)', summary)
    if first and len(first.group(1)) > 40:
        summary = first.group(1)
    if len(summary) > 160:
        summary = summary[:157].rsplit(' ', 1)[0] + '…'
    return dict(title=title.group(1) if title else os.path.splitext(os.path.basename(path))[0],
                icon=icon.group(1).strip() if icon else None, summary=summary)


def cards(folder_abs, pages):
    out = []
    for p in sorted(pages, key=lambda p: page_info(p)['title'].lower().removeprefix('the ')):
        info = page_info(p)
        href = url(folder_abs, os.path.splitext(p)[0])
        if info['icon'] and os.path.exists(os.path.join(dst, 'Images', info['icon'])):
            pic = f'<img src="{url(folder_abs, os.path.join(dst, "Images", info["icon"]))}" alt="">'
        else:
            pic = f'<span class="lore-card-blank">{info["title"][:1]}</span>'
        summ = info['summary'].replace('<', '&lt;').replace('[[', '').replace(']]', '').replace('**', '')
        out.append(f'<a class="lore-card internal" href="{href}">{pic}'
                   f'<span class="lore-card-text"><strong>{info["title"]}</strong><span>{summ}</span></span></a>')
    return '<div class="lore-grid">' + ''.join(out) + '</div>'


def md_pages(folder):
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.md') and f != 'index.md']


def write_index(folder, title, intro, body):
    open(os.path.join(folder, 'index.md'), 'w', encoding='utf-8', newline='\n').write(
        f'---\ntitle: "{title}"\nhide-listing: true\n---\n{intro}\n\n{body}\n')


SECTION_ORDER = ['Chrysos Heirs', 'Titans', 'Skyfire Dragons', 'Okhema', 'Helkolithists']


def galleries(tracker):
    ic = os.path.join(dst, 'Important Characters')
    if os.path.isdir(ic):
        subs = [d for d in os.listdir(ic) if os.path.isdir(os.path.join(ic, d))]
        subs.sort(key=lambda d: (SECTION_ORDER.index(d) if d in SECTION_ORDER else 99, d))
        parts = []
        for d in subs:
            sub = os.path.join(ic, d)
            parts.append(f'## {d}\n\n' + cards(ic, md_pages(sub)))
            write_index(sub, d, f'Everyone we know of among the {d}.', cards(sub, md_pages(sub)))
        loose = md_pages(ic)
        if loose:
            parts.append('## Others\n\n' + cards(ic, loose))
        write_index(ic, 'Important Characters', 'The people and powers of Amphoreus we have met or heard of.',
                    '\n\n'.join(parts))
    pl = os.path.join(dst, 'Places of Interest')
    if os.path.isdir(pl):
        write_index(pl, 'Places of Interest', 'Where the story has taken us.', cards(pl, md_pages(pl)))
    pa = os.path.join(dst, 'Party')
    if os.path.isdir(pa):
        current = [p for p in md_pages(pa)]
        former_dir = os.path.join(pa, 'Former Members')
        body = cards(pa, current)
        sheet_dir = os.path.join(pa, 'Character Sheets')
        if os.path.isdir(sheet_dir):
            body += '\n\n## Character sheets\n\n' + cards(pa, md_pages(sheet_dir))
        if os.path.isdir(former_dir):
            body += '\n\n## Former members\n\n' + cards(pa, md_pages(former_dir))
        rows = ['| Character | Skill points | 1st Verse full price | Paragon skill |', '| :-- | :-: | :-: | :-- |']
        for name in sorted(tracker):
            if name in FORMER:
                continue
            i = tracker[name]
            rows.append(f"| [[{name}]] | {i.get('points', '')} | {i.get('verse', '')} | {i.get('paragon', '')} |")
        body += '\n\n## Skill point tracker\n\n' + '\n'.join(rows)
        write_index(pa, 'The Party', 'Who is travelling together right now.', body)


# ---------- Character sheets (from the Foundry export macro) ----------
import glob, html, json

COMPANIONS = {'Vireloth': 'Sir Caerwyn Kyrn', 'Pantera': 'Mayuri'}
RANKS = ['Untrained', 'Trained', 'Expert', 'Master', 'Legendary']
COST = {1: '◆', 2: '◆◆', 3: '◆◆◆', '1': '◆', '2': '◆◆', '3': '◆◆◆', 'reaction': '⟲', 'free': '◇'}
FEAT_GROUPS = [('ancestryfeature', 'Ancestry features'), ('ancestry', 'Ancestry feats'), ('classfeature', 'Class features'),
               ('class', 'Class feats'), ('skill', 'Skill feats'), ('general', 'General feats'), ('bonus', 'Bonus feats'),
               ('calling', 'Mythic calling'), ('deityboon', 'Deity boons')]
SHEET_DIR = 'Party/Character Sheets'


def load_sheets():
    """Newest export of each character, from every .json in the vault's Character Sheets folder."""
    best = {}
    for f in glob.glob(os.path.join(src, 'Character Sheets', '*.json')):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        for a in d.get('actors', []):
            when = d.get('exported', '')
            if a['name'] not in best or when > best[a['name']][0]:
                a['_exported'] = when[:10]
                best[a['name']] = (when, a)
    sheets = {k: v[1] for k, v in best.items()}
    fill_from_foundry_files(sheets)
    return sheets


def fill_from_foundry_files(sheets):
    """Borrow formatted descriptions and traits from Foundry's own actor files
    (Character Sheets/Foundry files/*.json) wherever the export lacks them."""
    raw = {}
    for f in glob.glob(os.path.join(src, 'Character Sheets', 'Foundry files', '*.json')):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if d.get('name') and d.get('items'):
            raw[d['name']] = {it['name']: it for it in d['items']}
    for name, a in sheets.items():
        items = raw.get(name)
        if not items:
            continue
        entries = a.get('feats', []) + a.get('actions', []) + a.get('inventory', [])
        entries += [s for e in a.get('spellcasting', []) for s in e.get('spells', [])]
        for x in entries:
            it = items.get(x['name'])
            if not it or x.get('html'):
                continue
            s = it.get('system', {})
            x['html'] = (s.get('description') or {}).get('value', '')
            x.setdefault('traits', (s.get('traits') or {}).get('value', []))
            x.setdefault('rarity', (s.get('traits') or {}).get('rarity'))
            if it.get('type') == 'spell':
                for key, val in (('cast', (s.get('time') or {}).get('value')), ('range', (s.get('range') or {}).get('value')),
                                 ('target', (s.get('target') or {}).get('value')),
                                 ('duration', (s.get('duration') or {}).get('value')),
                                 ('defense', ((s.get('defense') or {}).get('save') or {}).get('statistic'))):
                    if val and not x.get(key):
                        x[key] = val
                area = s.get('area')
                if area and not x.get('area'):
                    x['area'] = f"{area.get('value')}-foot {area.get('type')}"


def sign(n):
    return '—' if n is None else (f'+{n}' if n >= 0 else f'−{-n}')


def clean_foundry(s):
    """Turn Foundry inline codes into plain text: [[/r 2d6]]{label} -> label, [[/act x]] -> x, @Check[...] -> ..."""
    s = str(s or '')
    s = re.sub(r'\[\[/\w+\s+([^\]]*?)\]\]\{([^}]*)\}', r'\2', s)
    s = re.sub(r'\[\[/\w+\s+([^\]]*?)\]\]', lambda m: m.group(1).split(' ')[0].replace('-', ' '), s)
    s = re.sub(r'@\w+\[[^\]]*\]\{([^}]*)\}', r'\1', s)
    s = re.sub(r'@(\w+)\[([^\]|]*)[^\]]*\]', lambda m: m.group(2).split(':')[-1].split('.')[-1], s)
    return s.replace('[[', '[').replace(']]', ']')


def esc(s):
    return html.escape(clean_foundry(s))


def details(title, body, open_=False):
    return f'<details{" open" if open_ else ""}><summary>{title}</summary>{body}</details>'


# --- Foundry description HTML -> clean, styled HTML ---
from html.parser import HTMLParser
from urllib.parse import quote

AON = 'https://2e.aonprd.com/Search.aspx?q='
GLYPHS = {'1': '◆', '2': '◆◆', '3': '◆◆◆', 'a': '◆', 'd': '◆◆', 't': '◆◆◆', 'r': '⟲', 'f': '◇'}


def _bracket(s, i):
    """Index just past the ']' that closes the '[' at s[i] (handles nesting)."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == '[':
            depth += 1
        elif s[j] == ']':
            depth -= 1
            if depth == 0:
                return j + 1
    return len(s)


def _label_after(s, j):
    if j < len(s) and s[j] == '{':
        k = s.find('}', j)
        if k != -1:
            return s[j + 1:k], k + 1
    return None, j


def _aon_link(text):
    return f'<a class="aon external" href="{AON}{quote(text)}" target="_blank" rel="noopener">{html.escape(text)}</a>'


def _check(params, label):
    if label:
        return f'<span class="roll">{html.escape(label)}</span>'
    parts = params.split('|')
    kind, dc, basic = '', '', False
    for p in parts:
        if ':' in p:
            k, v = p.split(':', 1)
            if k == 'type':
                kind = v
            elif k == 'dc':
                dc = v
        elif p == 'basic':
            basic = True
        elif not kind:
            kind = p
    kind = kind.replace('-', ' ').title()
    text = ' '.join(x for x in [f'DC {dc}' if dc and dc.lstrip('-').isdigit() else '', 'basic' if basic else '', kind] if x)
    return f'<span class="roll">{html.escape(text or "check")}</span>'


def _damage(formula, label):
    if label:
        return f'<span class="roll">{html.escape(label)}</span>'
    out, i = '', 0
    while i < len(formula):
        if formula[i] == '[':
            j = _bracket(formula, i)
            out += ' ' + formula[i + 1:j - 1].replace(',', ' ')
            i = j
        else:
            out += formula[i]
            i += 1
    out = re.sub(r'\s*,\s*', ', ', out).replace('  ', ' ').strip()
    return f'<span class="roll">{html.escape(out)}</span>'


def _template(params, label):
    if label:
        return html.escape(label)
    d = {}
    for p in params.split('|'):
        if ':' in p:
            k, v = p.split(':', 1)
            d[k] = v
        else:
            d.setdefault('type', p)
    shape, dist = d.get('type', 'area'), d.get('distance', '')
    return html.escape(f'{dist}-foot {shape}' if dist else shape)


def enrich(s):
    """Replace Foundry inline codes with HTML."""
    s = str(s or '')
    out, i = [], 0
    while i < len(s):
        m = re.compile(r'@(\w+)\[|\[\[/(\w+)\s').search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        if m.group(1):  # @Word[...]{label}
            kind = m.group(1)
            j = _bracket(s, m.end() - 1)
            inner = s[m.end():j - 1]
            label, k = _label_after(s, j)
            if kind in ('UUID', 'Compendium'):
                name = label or (inner.split('.')[-1] if not re.fullmatch(r'[A-Za-z0-9]{16}', inner.split('.')[-1]) else '')
                out.append(_aon_link(name) if name else '')
            elif kind == 'Check':
                out.append(_check(inner, label))
            elif kind == 'Damage':
                out.append(_damage(inner, label))
            elif kind == 'Template':
                out.append(_template(inner, label))
            else:
                out.append(html.escape(label) if label else '')
            i = k
        else:  # [[/r ...]]{label}
            end = s.find(']]', m.end())
            end = len(s) if end == -1 else end
            inner = s[m.end():end].strip()
            label, k = _label_after(s, end + 2)
            if m.group(2) == 'act':
                text = label or inner.split(' ')[0].replace('-', ' ').title()
                out.append(_aon_link(text))
            else:
                out.append(f'<span class="roll">{html.escape(label or inner.split(" #")[0])}</span>')
            i = k
    return ''.join(out)


class _Clean(HTMLParser):
    KEEP = {'p', 'strong', 'b', 'em', 'i', 'ul', 'ol', 'li', 'hr', 'br', 'blockquote', 'table', 'thead', 'tbody',
            'tr', 'td', 'th', 'h5', 'h6', 'div', 'span', 'a', 'sup', 'sub'}
    HEAD = {'h1': 'h5', 'h2': 'h5', 'h3': 'h5', 'h4': 'h6'}
    VOID = {'hr', 'br'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack, self.glyph, self.skip = [], [], False, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style'):
            self.skip += 1
            return
        tag = self.HEAD.get(tag, tag)
        if tag not in self.KEEP:
            self.stack.append(None)
            return
        if tag == 'span' and 'action-glyph' in (a.get('class') or ''):
            self.glyph = True
            self.stack.append('span')
            self.out.append('<span class="glyph">')
            return
        if tag == 'a':
            href = a.get('href') or ''
            if a.get('class', '').startswith('aon') or href.startswith('http'):
                self.out.append(f'<a class="external" href="{html.escape(href)}" target="_blank" rel="noopener">')
            else:
                self.stack.append(None)
                return
        else:
            self.out.append(f'<{tag}>')
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = self.HEAD.get(tag, tag)
        if tag in self.VOID:
            self.out.append(f'<{tag}>')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
            return
        if tag in self.VOID or not self.stack:
            return
        t = self.stack.pop()
        if t:
            self.out.append(f'</{t}>')
        if t == 'span' and self.glyph:
            self.glyph = False

    def handle_data(self, data):
        if self.skip:
            return
        if self.glyph:
            data = ''.join(GLYPHS.get(c.lower(), c) for c in data.strip())
        self.out.append(html.escape(data))


def render_desc(raw):
    if not raw:
        return ''
    p = _Clean()
    p.feed(enrich(raw))
    p.close()
    body = ''.join(p.out)
    body = re.sub(r'(<p>\s*</p>|<div>\s*</div>)', '', body)
    # one line, so a blank line inside a description can't end the page's HTML block
    body = re.sub(r'\s*\n\s*', ' ', body)
    return body.replace('[[', '[').replace(']]', ']')


def trait_chips(traits, rarity=None):
    chips = []
    if rarity and rarity != 'common':
        chips.append(f'<span class="trait trait-{esc(rarity)}">{esc(rarity)}</span>')
    chips += [f'<span class="trait">{esc(t)}</span>' for t in traits or []]
    return f'<div class="traits">{"".join(chips)}</div>' if chips else ''


def item_list(items):
    """items: list of dicts with name, meta, and optionally html/text, traits, rarity, facts."""
    out = []
    for it in items:
        body = trait_chips(it.get('traits'), it.get('rarity'))
        if it.get('facts'):
            body += '<p class="facts">' + ' · '.join(f'<b>{k}</b> {esc(v)}' for k, v in it['facts'] if v) + '</p>'
        if it.get('html'):
            body += f'<div class="desc">{render_desc(it["html"])}</div>'
        elif it.get('text'):
            body += f'<div class="desc"><p>{esc(it["text"])}</p></div>'
        meta = it.get('meta') or ''
        out.append(f'<details class="sheet-entry"><summary><strong>{esc(it["name"])}</strong>'
                   f'{f" <span class=sheet-meta>{meta}</span>" if meta else ""}</summary>{body}</details>')
    return ''.join(out)


def sheet_html(a, companion=False):
    lvl = a.get('level')
    sub = ' · '.join(x for x in [f'Level {lvl}' if lvl is not None else '', a.get('ancestry'),
                                  a.get('heritage') if a.get('heritage') and a.get('heritage') != a.get('ancestry') else None,
                                  a.get('background'), a.get('class'), a.get('deity')] if x)
    hp = a.get('hp') or {}
    speeds = (a.get('speed') or {}).get('speeds', {}) if isinstance(a.get('speed'), dict) else {}
    spd = ', '.join(f"{('' if k == 'land' else k + ' ')}{v.get('value')} ft" for k, v in speeds.items()
                    if isinstance(v, dict) and k != 'travel' and v.get('value'))
    res = a.get('resources') or {}
    pts = []
    for key, label in (('heroPoints', 'Hero'), ('mythicPoints', 'Mythic'), ('focus', 'Focus')):
        r = res.get(key) or {}
        if r.get('max'):
            pts.append(f'{label} {r.get("value", 0)}/{r["max"]}')
    stats = [('HP', f'{hp.get("value")}/{hp.get("max")}' + (f' (+{hp["temp"]})' if hp.get('temp') else '')),
             ('AC', a.get('ac')),
             ('Perception', f'{sign(a["perception"]["mod"])} <small>{RANKS[a["perception"]["rank"]]}</small>'),
             ('Speed', spd or '—')]
    if a.get('classDC') and a.get('class') not in ('Animal Companion', 'Eidolon'):
        stats.append(('Class DC', a['classDC']))
    for p in pts:
        label, value = p.split(' ', 1)
        stats.append((f'{label} points', value))
    out = [f'<div class="sheet{" sheet-companion" if companion else ""}">',
           f'<p class="sheet-sub">{esc(sub)}</p>',
           '<div class="sheet-stats">' + ''.join(f'<div><span>{k}</span><b>{v}</b></div>' for k, v in stats) + '</div>']
    saves = a.get('saves') or {}
    out.append('<div class="sheet-row"><h4>Saves</h4><div class="sheet-chips">' + ''.join(
        f'<div><span>{k.title()}</span><b>{sign(v["mod"])}</b><small>{RANKS[v["rank"]]}</small></div>' for k, v in saves.items()) + '</div></div>')
    attrs = a.get('attributes') or {}
    out.append('<div class="sheet-row"><h4>Attributes</h4><div class="sheet-chips">' + ''.join(
        f'<div><span>{k.upper()}</span><b>{sign(v)}</b></div>' for k, v in attrs.items()) + '</div></div>')

    skills = [s for s in a.get('skills', []) if not s.get('lore')]
    lores = [s for s in a.get('skills', []) if s.get('lore')]

    def skill_rows(lst):
        return ''.join(f'<div class="sk r{s["rank"]}"><span>{esc(s["label"])}</span><i>{RANKS[s["rank"]][0]}</i><b>{sign(s["mod"])}</b></div>' for s in lst)
    out.append('<div class="sheet-row"><h4>Skills</h4><div class="sheet-skills">' + skill_rows(skills) + '</div>'
               + (('<h4>Lore</h4><div class="sheet-skills">' + skill_rows(lores) + '</div>') if lores else '') + '</div>')

    strikes = []
    for s in a.get('strikes', []):
        bonus = ' / '.join(esc(v) for v in s.get('variants') or []) or sign(s.get('mod'))
        strikes.append(f'<div class="strike"><strong>{esc(s["name"])}</strong><span>{bonus}</span>'
                       f'<em>{esc(s.get("damage") or "")}</em></div>')
    if strikes:
        out.append('<div class="sheet-row"><h4>Strikes</h4><div class="sheet-strikes">' + ''.join(strikes) + '</div></div>')

    iwr = a.get('iwr') or {}
    defl = [(lbl, ', '.join(iwr.get(k) or [])) for k, lbl in (('immunities', 'Immune'), ('resistances', 'Resist'), ('weaknesses', 'Weak'))]
    defl = [(l, v) for l, v in defl if v]
    langs = ', '.join(x.title() for x in a.get('languages') or [])
    extra = ''.join(f'<p><b>{l}:</b> {esc(v)}</p>' for l, v in defl) + (f'<p><b>Languages:</b> {esc(langs)}</p>' if langs else '')
    ed, an = a.get('edicts') or [], a.get('anathema') or []
    if ed:
        extra += '<p><b>Edicts:</b> ' + esc(' '.join(ed).rstrip(',')) + '</p>'
    if an:
        extra += '<p><b>Anathema:</b> ' + esc(' '.join(an).rstrip(',')) + '</p>'
    if extra:
        out.append('<div class="sheet-row sheet-notes">' + extra + '</div>')

    acts = [dict(x, meta=COST.get(x.get('cost'), '')) for x in a.get('actions', [])]
    if acts:
        out.append(details(f'Actions & reactions ({len(acts)})', item_list(acts)))
    feats = a.get('feats', [])
    for cat, label in FEAT_GROUPS:
        group = sorted((f for f in feats if f.get('category') == cat), key=lambda f: (f.get('level') or 0, f['name']))
        if group:
            out.append(details(f'{label} ({len(group)})', item_list(
                [dict(f, meta=f'Lv {f["level"]}' if f.get('level') else '') for f in group])))
    for e in a.get('spellcasting', []):
        spells = sorted(e.get('spells', []), key=lambda s: (s.get('rank') or 0, s['name']))
        rows = []
        for s in spells:
            facts = [('Cast', COST.get(s.get('cast'), s.get('cast'))), ('Range', s.get('range')), ('Area', s.get('area')),
                     ('Targets', s.get('target')), ('Defense', (s.get('defense') or '').title() or None),
                     ('Duration', s.get('duration'))]
            rows.append(dict(s, meta='Cantrip' if 'cantrip' in (s.get('traits') or []) or not s.get('rank') else f'Rank {s["rank"]}',
                             facts=[f for f in facts if f[1]]))
        out.append(details(f'{esc(e["name"])} · DC {e.get("dc")} · attack {sign(e.get("attack"))}', item_list(rows)))
    inv = a.get('inventory', [])
    if inv:
        def inv_meta(i):
            bits = []
            if (i.get('qty') or 1) != 1:
                bits.append(f'×{i["qty"]}')
            if i.get('invested'):
                bits.append('invested')
            elif i.get('equipped'):
                bits.append('equipped')
            return ' · '.join(bits)
        order = sorted(inv, key=lambda i: (not i.get('equipped'), i.get('type', ''), i['name']))
        out.append(details(f'Inventory ({len(inv)})', item_list([dict(i, meta=inv_meta(i)) for i in order])))
    out.append('</div>')
    return '\n'.join(out)


def build_sheets():
    sheets = load_sheets()
    if not sheets:
        return []
    made = []
    pcs = [n for n in sheets if n not in COMPANIONS]
    folder = os.path.join(dst, *SHEET_DIR.split('/'))
    os.makedirs(folder, exist_ok=True)
    for name in sorted(pcs):
        comp = [c for c, owner in COMPANIONS.items() if owner == name and c in sheets]
        fm = ['---', f'title: "{name} — Character Sheet"', 'tags: [character-sheet]']
        if os.path.exists(os.path.join(src, 'Images', f'{name}.png')):
            fm += [f'banner: "![[{name}.png]]"', 'banner-height: 220', 'banner-y: 20', f'icon-image: "![[{name}-icon.png]]"']
        fm.append('---')
        body = [f'*Pathfinder 2e sheet, numbers straight from Foundry (exported {sheets[name].get("_exported", "?")}).*', '',
                f'[[{name}|← Back to {name}\'s page]]', '', sheet_html(sheets[name])]
        for c in comp:
            body += ['', f'## {c}', sheet_html(sheets[c], companion=True)]
        open(os.path.join(folder, f'{name} (Sheet).md'), 'w', encoding='utf-8', newline='\n').write(
            '\n'.join(fm) + '\n' + '\n'.join(body) + '\n')
        made.append(name)
    return made


def link_sheets(made):
    """Add a 'character sheet' link to each party page that has one."""
    for name in made:
        p = os.path.join(dst, 'Party', name + '.md')
        if not os.path.exists(p):
            continue
        t = open(p, encoding='utf-8').read()
        block = f'> [!example] 📜 Character sheet\n> [[{SHEET_DIR}/{name} (Sheet)|Open {name}\'s full Pathfinder sheet →]]\n\n'
        anchor = '> [!info] 📋 Identity'
        t = t.replace(anchor, block + anchor, 1) if anchor in t else t + '\n' + block
        open(p, 'w', encoding='utf-8', newline='\n').write(t)


# ---------- Pages for links that lead nowhere ----------
# What the notes already say about Titans that have no page yet.
TITANS = {
    'Nikador': ('Calamity', 'Strife', 'Mydeimos'),
    'Thanatos': ('Calamity', 'Death', 'Castorice'),
    'Zagreus': ('Calamity', 'Trickery', 'Cipher'),
    'Janus': ('Fate', 'Passage', 'Tribios'),
    'Talanton': ('Fate', 'Law', 'Cerydra'),
    'Oronyx': ('Fate', 'Time', None),
    'Georios': ('Foundation', 'Earth', 'Terravox'),
    'Phagousa': ('Foundation', 'Ocean', 'Hysilens'),
    'Aquila': ('Foundation', 'Sky', 'Hyacinthia'),
    'Kephale': ('Creation', 'Worldbearing', 'Phainon'),
    'Cerces': ('Creation', 'Reason', 'Anaxagoras'),
    'Mnestia': ('Creation', 'Romance', 'Aglaea'),
}
FORMER_MEMBERS = {'Ulixes'}


def all_pages():
    out = []
    for root, _, files in os.walk(dst):
        for f in files:
            if f.endswith('.md'):
                out.append(os.path.relpath(os.path.join(root, f), dst).replace('\\', '/'))
    return out


def missing_links():
    pages = all_pages()
    stems = {os.path.splitext(os.path.basename(p))[0].lower() for p in pages}
    paths = {os.path.splitext(p)[0].lower() for p in pages}
    found = {}
    for p in pages:
        t = open(os.path.join(dst, p), encoding='utf-8').read()
        for m in re.finditer(r'(?<!!)\[\[([^\]|#]+)', t):
            tgt = m.group(1).strip().rstrip('\\').strip()
            low = tgt.lower()
            if not tgt or low in paths or low.split('/')[-1] in stems or low.endswith('/index'):
                continue
            if os.path.splitext(tgt)[1].lower() in ('.mp4', '.png', '.jpg', '.jpeg', '.webp'):
                continue
            found.setdefault(tgt.split('/')[-1], set()).add(os.path.splitext(p)[0])
    return found


def stub(name, linked_from):
    seen = ', '.join(f'[[{os.path.basename(p)}]]' for p in sorted(linked_from)[:6])
    if name in TITANS:
        group, domain, heir = TITANS[name]
        folder = 'Important Characters/Titans'
        subtitle = f'Titan of {group} · ???'
        rows = [('Group', f'Titans of {group}'), ('Domain', domain), ('State', '???'),
                ('Coreflame', '???'), ('Chrysos Heir', f'[[{heir}]]' if heir else '???'),
                ('Where', '???'), ('Manifestation', '???')]
        questions = [f'Where is {name}, and what form does it take?', f'Is {name} dormant, corrupted, or dead?',
                     f'Who holds, or will hold, the coreflame of {domain}?']
        if not heir:
            questions.append(f'Who is the Chrysos Heir of {name}?')
    elif name in FORMER_MEMBERS:
        folder = 'Party/Former Members'
        subtitle = 'Former party member'
        rows = [('Status', 'No longer travelling with the party'), ('Last seen', '???'), ('Where now', '???')]
        questions = [f'Where did {name} go?', f'Will {name} return?']
    else:
        folder = 'Uncharted'
        subtitle = '???'
        rows = [('What', '???'), ('Where', '???'), ('First mentioned', '???')]
        questions = [f'Who or what is {name}?']
    body = [
        '---', f'title: "{name}"', 'tags: [unknown]', '---',
        f'*{subtitle}*', '',
        '> [!question] Not yet recorded',
        f'> The party knows very little about **{name}** so far. Anything marked ??? is still a mystery.', '',
        '> [!info] 📋 What we know', '> | | |', '> | :-- | :-- |'] + [f'> | **{k}** | {v} |' for k, v in rows] + [
        '',
        '> [!question] ❓ Open Questions'] + [f'> - {q}' for q in questions] + [
        '', f'*Mentioned in: {seen}*', '']
    p = os.path.join(dst, *folder.split('/'), name + '.md')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(body))
    return folder


def fill_missing():
    made = []
    for name, sources in sorted(missing_links().items()):
        made.append(f'{stub(name, sources)}/{name}')
    if any(m.startswith('Uncharted/') for m in made):
        write_index(os.path.join(dst, 'Uncharted'), 'Uncharted',
                    'Names that have come up but that we know almost nothing about.',
                    cards(os.path.join(dst, 'Uncharted'), md_pages(os.path.join(dst, 'Uncharted'))))
    return made


# ---------- main ----------
if os.path.isdir(dst):
    for name in os.listdir(dst):
        p = os.path.join(dst, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
os.makedirs(dst, exist_ok=True)

sessions = []
count = 0
tracker = read_tracker(os.path.join(src, 'Skill point tracker.md'))
for root, dirs, files in os.walk(src):
    for f in files:
        if os.path.splitext(f)[1].lower() in SKIP_EXT:
            continue
        s = os.path.join(root, f)
        rel = os.path.relpath(s, src).replace('\\', '/')
        if rel == 'Skill point tracker.md':
            continue  # shown on the Party page and each character page instead
        if rel.startswith('Character Sheets/'):
            continue  # turned into sheet pages by build_sheets()
        if rel == 'Journal.md':
            sessions = split_journal(open(JOURNAL or s, encoding='utf-8').read().replace('\r\n', '\n'), dst)
            count += 1
            continue
        out_rel = rel[len('Lorekeeper Notes/'):] if rel.startswith('Lorekeeper Notes/') else rel
        stem = os.path.splitext(f)[0]
        if out_rel.startswith('Party/') and stem in FORMER:
            out_rel = 'Party/Former Members/' + f
        d = os.path.join(dst, *out_rel.split('/'))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if f.endswith('.md'):
            t = open(s, encoding='utf-8').read().replace('\r\n', '\n')
            t = scrub(rel, t)
            if rel.startswith('Lorekeeper Notes/'):
                t = drop_portrait(lift_title(t))
            if out_rel.startswith('Party/'):
                t = add_progress(t, tracker.get(stem))
            if f in TITLES:
                t = set_title(t, TITLES[f])
            open(d, 'w', encoding='utf-8', newline='\n').write(t)
        else:
            shutil.copy2(s, d)
        count += 1

sheets_made = build_sheets()
link_sheets(sheets_made)
made = fill_missing()
galleries(tracker)
today = calendar_page(sessions)
open(os.path.join(dst, 'index.md'), 'w', encoding='utf-8', newline='\n').write(home(sessions, today))
if made:
    print('question-mark pages:', ', '.join(made))
print('copied', count, 'files;', len(sessions), 'journal sessions')
