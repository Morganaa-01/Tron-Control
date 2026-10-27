TRON CONTROL 1.4.8 — Jenna — Magyar / English — 2026-10-27

AKTUÁLIS VERZIÓ
Három fül: Robot • térképezés; Adatok • ellenőrzés; Szimuláció • Gazebo.
A korábbi verziójegyzetek a dokumentum végén történeti információk.
A 1.3-as megjegyzésben szereplő nyers bag hiánya az 1.4-re már nem igaz.

ÚJ FUNKCIÓK ÉS HASZNÁLAT
• Gazebo üres világ, saját .world, illetve mellékelt akadályos tesztvilág.
  A tesztvilág szintetikus, nem a Campus Heart pontos modellje.
• TRON1 modell: a helyi limx_ws workspace és a már működő Gazebo .launch
  fájl kiválasztása egyszer szükséges. A program nem találja ki a nevét.
  A kiválasztott világfájl az üres világ indítójához használható; a TRON1
  saját launch fájlja a saját világát tölti be.
• Szimuláció: külön helyi ROS master 11321 és Gazebo master 11355.
  A program nem indít robotkapcsolatot a szimulációs gombokkal.
  Leállítás a Szimuláció leállítása gombbal; csak a saját folyamatcsoportot
  kapja SIGINT. A Gazebo sikere az ablakában és a naplóban ellenőrizhető.
• Mentett pontfelhő: válassz egy vagy több .pcd fájlt. Több rész egyszerre
  betölthető a pcl_viewer-be, de nagy felvételnél sok laptopmemória kellhet.
• Nyers rögzítés: ROS és LiDAR indítása után, a térképezés ELŐTT indítsd.
  /livox/lidar és /livox/imu kötelező; /tf, /tf_static és /Odometry akkor
  kerül bele, ha publikálják. 1 GiB-os részek, 256 MiB puffer, 5 GiB
  lemezhely-küszöb. A puffer túlcsordulási figyelmeztetéseit nézd a naplóban.
• Befejezés: előbb térképezés leállítása/mentése, majd Nyers rögzítés
  lezárása. A két funkció külön folyamat. A bag lezárás ellenőrzi az
  olvasható indexet és a LiDAR/IMU üzenetszámokat, nem ígér veszteségmentességet.
• Nyers felvétel másolása: külön gomb; minden lezárt rész SHA-256 ellenőrzött.
• Indulási ellenőrzés: óraeltérés, memória, tárhely, ROS és szenzorüzenetek.
  A térképezés 5 másodpercnél nagyobb óraeltérés, 5 GiB-nál kevesebb
  tárhely vagy 2 GiB-nál kevesebb elérhető memória esetén nem indul.
  Ez nem javítja automatikusan az órát. A lekapcsolás utáni időmegőrzés
  a roboton még külön ellenőrizendő.
• A HU/EN váltás a fülekre és az új funkciókra is kiterjed.

ELLENŐRZÉS
Helyi automatizált tesztek: PCD integritás, részfájlok archiválása,
ellenőrzött többfájlos másolás, hibás SHA-256 visszautasítása, parancsok
idézése, szimulációs címek, bag hibautak, nyelvváltás, Python 3.8 szintaxis.
A ROS/Gazebo/robot hardveres integrációja itt nem futott. Először rövid
laborpróba szükséges: 25–30 s rögzítés, mentés, másolás és megnyitás.
Autonóm navigációt, motorparancsot, vészleállítót, bag-visszajátszást,
PCD-összevonást vagy térképes lokalizációt ez a verzió még nem tartalmaz.

FRISSÍTÉS
Ments és állíts le minden korábban indított rögzítést, majd zárd be a régi
TRON Controlt. Csomagold ki az új ZIP-et a Dellre. A kicsomagolt
TRON-Control mappában nyiss terminált és futtasd:
    bash install.sh
A meglévő SSH-kulcs és beállítások megmaradnak.

KORÁBBI ÚTMUTATÓ ÉS VERZIÓJEGYZETEK
TRON CONTROL — Jenna • 1.0 • 2026-10-26

HELYI ASZTALI ALKALMAZÁS A DELL UBUNTU GÉPRE
Ez a program a roboton már meglévő ROS Noetic / Livox / FAST-LIO
programokat indítja SSH-n. Nem telepít semmit a robotra a külön
SSH-nyilvános kulcs beállításán kívül. Nem ad mozgásparancsot.

TELEPÍTÉS
1. Csomagold ki a ZIP-et a Dell gépen.
2. Nyisd meg a TRON-Control mappát, jobb klikk → Open in Terminal.
3. Írd be: bash install.sh
4. Ha python3-tk hiányzik: sudo apt install python3-tk
   Ezután ismét: bash install.sh
5. Az alkalmazások között keresd: TRON Control.
   Az asztali ikon jobb klikk → Allow Launching, ha szükséges.

ELSŐ CSATLAKOZÁS
Csatlakozz a robot Wi-Fi-jére. Robot IP: 10.192.1.3.
Kattints: SSH beállítása. A terminálban ellenőrizd a robot gépazonosítóját,
majd add meg az SSH-jelszót. A program külön SSH-kulcsot hoz létre a
Dell ~/.ssh/tron_control_ed25519 útvonalán, üres kulcsjelszóval, és a
nyilvános kulcsot a robot guest felhasználójához adja. A robot jelszavát
nem tárolja. A Dell felhasználói fiókját és a privát kulcsot védd.
Utána: Kapcsolat ellenőrzése → Állapot frissítése.

JELENLEGI JENNA_TEST_MAP MÁSOLÁSA
A már mentett PCD/Jenna_test_map.pcd fájlhoz nem kell új térképezés!
Válaszd a 7. gombot, a név mezőben hagyd: Jenna_test_map.
A másolat alapértelmezett helye: ~/Documents/TRON_maps/.
A 3,4 GB-os fájl több percig másolódhat. A program a másolatot SHA-256
ellenőrzőösszeggel igazolja. Ezalatt a folyamatjelző mozog, százalékot
az első verzió nem mutat. Meglévő célfájlt nem ír felül.

ÚJ RÖVID PRÓBAMÉRÉS
1. Kapcsolat ellenőrzése.
2. ROS központ indítása. Ha már fut, felismeri.
3. LiDAR indítása. Ha már fut, felismeri.
4. Adj egyedi nevet (angol betű, szám, _ vagy -; kiterjesztés nélkül).
5. Térképezés indítása.
6. Állapot frissítése: ellenőrzi a node-ok válaszát és az adatérkezést.
7. RViz-beállítás…: válaszd ki a korábbi THOR-lidar-mapping.rviz fájlt.
   Élő térkép megnyitása. Alapértelmezett RViz esetén a Fixed Frame:
   camera_init; PointCloud2 topic: /cloud_registered.
8. Rövid felvétel után Leállítás és mentés. Várj a kész jelzésig.
9. Mentett térkép másolása.

Az alkalmazás csak a saját indítású FAST-LIO folyamatát állítja le.
Ha az már másik terminálban fut, ott Ctrl+C-vel állítsd le, és ellenőrizd
a mentését. Nem használ széles körű pkill parancsot.
Indulás előtt a scans.pcd fájl jelenléte blokkolja az új mérést: előbb
őrizd meg egyedi néven, hogy az új felvétel ne írhassa felül.
A program pcd_save_en: true és interval: -1 beállítást követel meg.
A beállításokat maga nem módosítja.

MEMÓRIA ÉS TÉRKÉPMINŐSÉG
Az interval:-1 minden felvétel pontjait memóriában gyűjti. Hosszú
felvétel nagy fájlt és memóriahiányt okozhat; kezdd rövid próbával.
A fájlmentés ellenőrzése nem igazolja a térkép geometriai pontosságát.
A robot órája korábban 1970-et mutatott. A program az órát kijelzi,
de nem állítja át. A két gép órájának rendezése külön feladat.
A teljes Campus Heart mérés és az autonóm navigáció nincs ebben a verzióban.

BEZÁRÁS
Először állítsd le és mentsd a térképezést. Az ablak bezárásakor külön
felajánlja a saját LiDAR/ROS folyamatainak szabályos leállítását.
Külső folyamatokat nem állít le. Aktív műveletnél nem zárja be az ablakot.
A robot fizikai kikapcsolását továbbra is a szokásos módon végezd.

NAPLÓK ÉS BEÁLLÍTÁSOK
~/.local/state/tron-control/session_*.log
~/.config/tron-control/settings.json

ELLENŐRZÉS / KORLÁTOK
Python- és shell-szintaxis, parancsépítés és PCD-fájlméret-ellenőrzés
helyi tesztekkel ellenőrizve. A valódi robot és a Dell grafikus
környezetének elérése itt nem volt lehetséges. Az első robothoz kapcsolt
próbát együtt végezzük; a program nem tekinthető még roboton teszteltnek.

MAGYAR / ANGOL — 1.1 VERZIÓ
Az ablak felső részében a Nyelv / Language listában válassz:
Magyar vagy English. A feliratok, alkalmazásüzenetek és állapotok
azonnal váltanak. A választás megmarad a következő indításra is.
A ROS, SSH és más külső programok eredeti naplója nem fordul le.
Frissítéskor zárd be az előző verziót, majd futtasd az új install.sh-t.
Aktív mérés közben előbb szabályosan ments és állítsd le a folyamatokat.
A telepítés nem törli a térképeidet, az SSH-kulcsodat vagy a beállításaidat.

KÜLÖN TERMINÁLOK — 1.2 VERZIÓ
A ROS, a LiDAR és a FAST-LIO indításakor külön naplóterminál nyílik.
Ezekben párhuzamosan követheted a kimeneteket. A Napló gombbal újra
megnyithatók. Ezek megfigyelőablakok: a Ctrl+C vagy az ablak bezárása
csak a napló követését állítja le. A FAST-LIO mentéséhez mindig a
vezérlőablak Leállítás és mentés gombját használd.
A Robot terminál gomb külön, interaktív SSH terminált nyit kézi
parancsokhoz. Többször megnyitható. Az ott kézzel indított folyamatok
nem az alkalmazás által kezelt folyamatok.
Jelszó: az SSH beállítása terminálban a password: kérdés után írd be.
Gépeléskor sem csillag, sem pont nem jelenik meg: ez normális. Enterrel
küldd el. Az interaktív Robot terminál is kérhet jelszót, amíg a kulcs
nincs beállítva. A gombos indítás előtt végezd el az SSH beállítását.
A korábban külső terminálban indított ROS/LiDAR naplója továbbra is ott
látszik; az alkalmazás nem indít belőlük újabb példányt.

1.4.8 – Egyfájlos kontrollmérés
A mentési intervallum ismét -1: az összegyűjtött pontfelhő a szabályos
leállításkor egy scans.pcd fájlba kerül. Addig a pontok RAM-ban gyűlnek;
megszakadáskor a még ki nem írt pontfelhő elveszhet.
Minden futás külön PCD/<felvételnév> mappát kap, saját recording.launch
fájllal. Az eredeti mapping_mid360.launch és mid360.yaml nem változik.
A manifest.json és a SHA-256 ellenőrzött másolás megmarad. Korábbi,
darabolt felvételek továbbra is másolhatók. A nyers bag rögzítés külön
indítható és leállítható a Data fülön.
A változtatás nem bizonyítja és nem javítja automatikusan a torzulás okát.
Először rövid álló, majd lassan mozgó kontrollmérés és vizuális ellenőrzés.
Élő folyamatok alatt ne frissíts: ments, állítsd le őket, zárd be az appot.
Csomagold ki az új ZIP-et, majd a TRON-Control mappában: bash install.sh
A robot fájljait és a régi felvételeket a telepítő nem módosítja.

1.4.8: Sync robot clock / Ora szinkronizalasa: stop LiDAR, mapping and bag first.
Requires SSH key setup and robot sudo password in the terminal.
Uses the Dell clock as reference; verify laptop time first.
One-shot system clock correction, not persistent NTP/RTC configuration.

1.4.8: Confirmed status text is green; pending amber; unverified/stopped grey.

1.4.8 – Live health / Elo allapotfigyeles
Automatic probes after connection: 2.5 s message sampling, approximately
5–10 s refresh when idle. Probes pause during app operations; displayed
status during a long save/copy is the last checked state, not a guarantee.
Green sensor/mapping labels require new messages; missing messages or
unexpected process exit are red. Intentional stops are grey.
Stop LiDAR button targets the known Livox node, refuses active mapping/bag.
Clock sync now displays instructions while its terminal waits for input.
Live proximity tab is READ ONLY. No movement/stop commands are published.
Range is radial from LiDAR center, all directions, ignoring points <0.5m.
A 1.5m amber indication is a diagnostic threshold, NOT a stopping distance.
Floor, body, occlusion, glass and missing points are not resolved; this is
not an obstacle avoidance or safety system. Calibrate frame, ground filter,
footprint and drive interface before adding any motion control.
Hardware/GUI integration testing is still required.

1.4.8: Stop all and save button. Closes managed mapping and bag with normal
validation, then stops Livox, managed ROS master and managed Gazebo.
Save errors or unknown/external recording state abort remaining shutdown.
No SIGKILL. Not a robot motion emergency stop or power-off. External ROS
masters, standalone RViz/viewers, log terminals are not killed.
Unavailable during another operation; finish clock terminal/password first.

1.4.8 – RViz / Gazebo launch review
RViz uses bundled live_mapping.rviz when no custom config is selected.
It requires fresh /cloud_registered and uses its actual header frame_id.
Reset RViz live view clears an old custom selection. Install includes config.
Gazebo world-only buttons explicitly say WITHOUT ROBOT. TRON1 requires a
verified installed robot launch, offered by Find installed Gazebo launches.
Candidates are not guaranteed robot launch entry points; inspect selection.
Custom world selection applies only to world-only mode, not the robot launch.
Fixed log-window title lookup for Gazebo and raw bag recording.
Live GUI/ROS integration remains to be checked on the Dell and robot.
