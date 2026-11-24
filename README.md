# WGN Instagram + Facebook autopost

Post automatisch de grootste headlines van worldgolfnews.org op Instagram én op de Facebook-pagina (met klikbare artikellink). Eigen visual in WGN-huisstijl (fairwaygroen + goud, Fraunces + Figtree), caption met "link in bio" en tour-hashtags. Volledig gratis: GitHub Actions + de officiële Meta Graph API + een Google Apps Script-klok.

Afgeleid van `finnkops-code/wbn-instagram`; zelfde werking, vertaald naar golf.

## Hoe het werkt

Elk uur start een Google Apps Script-klok (`apps-script/trigger.gs`) de workflow **Instagram autopost**. De bot leest de RSS-feed + de WordPress REST API van de site (alle artikelen tot **72 uur** oud) en geeft elk artikel een **nieuwswaarde-score van 0–100**:

| Onderdeel | Punten |
|---|---|
| Tour | elke tour start gelijk: +20 |
| Onderwerp (sterkste telt, elk extra onderwerp +5) | majorzege (Masters, US Open, The Open, PGA Championship, vrouwenmajors) +45 · seizoenstitel/teamevent (FedExCup, Race to Dubai, CME, Ryder/Solheim/Presidents Cup, Olympische Spelen) +40 · historisch (record, hole-in-one, albatross, 59, wire-to-wire) +35 · grote stap (tekent bij LIV, stopt, schorsing, captain) +28 · toernooizege +26 · slotronde-drama (play-off, comeback, leiding) +20 · topronde (eagle, baanrecord, 62–64) +12 · rondeverslag +6 |
| Aftrek | junioren/college −10 · service (tee times, how to watch, odds, schema) −12 · preview −6 · ouderdom −0,6 per uur |
| Lezers | staat in "Most read" op de homepage +10 |
| Variatie | zelfde verhaal als eerdere post vandaag −35 · elke eerdere post van dezelfde tour vandaag −12 · elke post van die tour eerder deze week −3 |
| Toeval | +0 tot 8, vast per artikel per dag |

**Wanneer gaat er iets live?** Maximaal **3 artikelposts per dag**, minstens 1 uur ertussen, belangrijkste nieuws eerst.
- De dag (NL) is verdeeld in 3 blokken van 8 uur; per blok gaat het waardevolste artikel live, bij voorkeur in de prime time van het thuispubliek van die tour (PGA/LPGA/LIV/Korn Ferry/Champions op New Yorkse tijd, DP World Tour en LET op Britse tijd, Japan Tour op Japanse, Asian Tour op Singaporese tijd; zie `league_timezones` in `config.json`).
- Score ≥ 70 gaat direct live zodra het daar overdag is. Weekposts (Player of the Week, ranglijsten) tellen niet mee voor de 3.

Elke run zet de volledige ranking met uitleg in de samenvatting van de GitHub Action. Alle punten, woorden en tijden staan in `config.json`.

**Visual**: 1080×1350, artikelfoto bovenaan (staande/vierkante foto's uitgelijnd op **centrum-boven**, zodat hoofden niet worden afgesneden), daaronder tour-label, datum en de kop in Fraunces. Geen logo op de visuals (`design_variant` = `A` in `config.json`); alleen WORLDGOLFNEWS.ORG in de footer.

**Facebook**: dezelfde visual op de WGN Facebook-pagina, met de artikellink klikbaar in de tekst (Facebook-route met page token, zie setup).

**Collabs**: uitnodigingen van accounts in `auto_accept_collaborators` (`config.json`) worden elke run automatisch geaccepteerd.

## Eenmalige setup (± 25 minuten) — dit doe jij, de bot voert nooit zelf tokens of wachtwoorden in

### 1. Accounts
1. Maak het Instagram-account voor WGN aan en zet het om naar professioneel: Instagram-app → *Instellingen* → *Accounttype en tools* → *Overstappen naar professioneel account* → **Bedrijf** (categorie *Media/nieuwsbedrijf*).
2. Maak een Facebook-pagina *World Golf News* (facebook.com/pages/create).
3. Koppel ze: Facebook-pagina → *Instellingen* → *Gekoppelde accounts* → *Instagram* → *Account koppelen*.

### 2. Meta-app en page token (Facebook-route)
1. [developers.facebook.com](https://developers.facebook.com) → *My Apps* → *Create app* → use case *Other* → type *Business* → naam "WGN autopost". Development-modus is genoeg (je post alleen naar je eigen account).
2. *Tools* → **Graph API Explorer** → kies rechts je app → *User or Page*: **Get User Access Token** met permissies `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `business_management` → *Generate Access Token* en log in.
3. *Tools* → **Access Token Debugger** → plak de token → *Extend Access Token* (long-lived).
4. Terug in de Graph API Explorer met die long-lived token: vraag `me/accounts?fields=name,access_token,instagram_business_account` op. Kopieer bij *World Golf News* de **access_token** (= page token, verloopt niet) en het **instagram_business_account.id**.

### 3. GitHub-repo `finnkops-code/wgn-instagram` (publiek)
Publiek is nodig omdat Instagram de visual zelf ophaalt via een openbare URL; tokens staan veilig in Secrets. Actions-minuten zijn onbeperkt gratis voor publieke repo's.
1. *Settings → Secrets and variables → Actions → New repository secret*:
   - `IG_ACCESS_TOKEN` — de page token uit stap 2.4
   - `IG_USER_ID` — het instagram_business_account.id
2. Zelfde scherm, tab *Variables* → *New repository variable*: `IG_API_ROUTE` = `facebook`.
3. *Settings → Actions → General → Workflow permissions* → **Read and write permissions** → *Save*.

### 4. Klok (Google Apps Script)
1. [script.google.com](https://script.google.com) → *Nieuw project* → naam "WGN Instagram klok" → plak `apps-script/trigger.gs`.
2. Maak een [fine-grained GitHub-token](https://github.com/settings/personal-access-tokens/new): alleen repo `wgn-instagram`, permissie **Actions: Read and write**.
3. Tandwiel (*Projectinstellingen*) → *Scripteigenschappen* → `GITHUB_TOKEN` = die token.
4. Kies `setup` → *Uitvoeren* → toestemming geven.

### 5. Testen en live
1. *Actions* → **Check connection** → *Run workflow*: toont pagina, Instagram-account en permissies (post niets).
2. *Actions* → **Instagram autopost** → *Run workflow* met **dry_run** aangevinkt: caption in de samenvatting, visual in `posts/`.
3. Goed? Run zonder dry_run: eerste post gaat live op Instagram én Facebook.
4. Instagram-bio: `https://worldgolfnews.org`.

## Wekelijkse posts (staan uit tot akkoord)

- **World Golf Player of the Week** (donderdag 17:00 NL): beste prestatie van de vorige week (ma–zo) op PGA Tour, LIV, DP World Tour, LPGA, Korn Ferry en Champions (gratis ESPN-data, dezelfde als de site). Alleen met de officiële ESPN-portretfoto van precies die speler; geen foto → volgende kandidaat.
- **Ranglijstoverzicht** (maandag 17:00 NL): carrousel; databronnen worden gekozen na akkoord.

Aanzetten: `config.json` → `weekly` → `enabled: true`. Handmatig: *Run workflow* met `weekly` = `potw` of `rankings`. Concepten renderen: `python tools/concepts.py` (map `preview/concepts/`).

## Handig om te weten
- **Lokaal previewen**: `pip install -r requirements.txt` en `python bot.py preview` of `python bot.py preview <artikel-url>`.
- **Losse post**: *Run workflow* met `url` (optioneel `collaborators`, max 3).
- **Fout bij posten?** GitHub mailt je; de volgende run probeert het opnieuw.
- **Opruimen**: visuals ouder dan 14 dagen gaan automatisch uit de repo.
- **Fonts**: Fraunces en Figtree (SIL Open Font License, zie `fonts/`).
