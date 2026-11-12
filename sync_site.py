"""Copy the Amphoreus vault folder into the Quartz content folder for the public site.

Usage: python sync_site.py <vault Amphoreus folder> <quartz content folder>

What it does to the site copy (the vault itself is never changed):
- skips videos and canvases
- moves everything in "Lorekeeper Notes" up one level so the sidebar is shorter
- hides character secrets (Delmore's Norgorber lines, Mayuri's death-vision blurb)
- turns each Lorekeeper page's "# Heading" into its page title
- drops the portrait under the banner, since the banner already shows it
- splits Journal.md into one page per session, in Act / Arc folders
- writes the home page
"""
import os, re, shutil, sys

sys.stdout.reconfigure(encoding='utf-8')
src, dst = sys.argv[1], sys.argv[2]
SKIP_EXT = {'.mp4', '.canvas'}
TITLES = {'A_Travelers_Guide_to_the_Light_Calendar.md': "A Traveler's Guide to the Light Calendar"}


def scrub(rel, text):
    if rel.endswith('Party/Delmore.md'):
        text = '\n'.join(l for l in text.split('\n') if 'norgorber' not in l.lower()) + '\n'
    if rel.endswith('Party/Mayuri.md'):
        text = re.sub(r'> \[!quote\] At a glance\n> [^\n]*\n\n', '', text)
        text = text.replace(' Mayuri set out to find it anyway, whether it killed her or cured her.',
                            ' Mayuri set out to find it anyway.')
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
        lines.append(f"- [[{s['path']}|{s['title']}]]" + (f" · {s['date']}" if s['date'] else ''))
    open(os.path.join(out, 'Journal', 'index.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    return sessions


# ---------- Home page ----------
def home(sessions):
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
    out += ['## The Party', ''] + rows + ['', '[[Party/index|Skill points, paragon skills and former members →]]', '']
    out += ['## Quests', '', '- [[Party Quests]]: the Flame-Chase, the Descent Beneath the Temple, and the party\'s open leads.', '']
    out += ['## The World', '',
            '- **Places:** [[Amphoreus Info|Amphoreus]] · [[Okhema Info And Occupants|Okhema]] · '
            '[[Janusopolis Info and Occupants|Janusopolis]] · [[Philoxenion]]',
            '- **Chrysos Heirs:** ' + ' · '.join(f'[[{h}]]' for h in heirs),
            '- **Titans:** [[Cerces]] · [[Georios]] · [[Janus]] · [[Kephale]] · [[Talanton]]',
            '- **Skyfire Dragons:** [[Commander Deva]] · [[Ione Kalyx]] · [[Jossum]]',
            "- **Reference:** [[A_Travelers_Guide_to_the_Light_Calendar|A Traveler's Guide to the Light Calendar]]", '']
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
        if rel == 'Journal.md':
            sessions = split_journal(open(s, encoding='utf-8').read().replace('\r\n', '\n'), dst)
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

made = fill_missing()
galleries(tracker)
open(os.path.join(dst, 'index.md'), 'w', encoding='utf-8', newline='\n').write(home(sessions))
if made:
    print('question-mark pages:', ', '.join(made))
print('copied', count, 'files;', len(sessions), 'journal sessions')
