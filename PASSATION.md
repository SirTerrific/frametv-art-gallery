# Passation — frametv-art-gallery, blocage des vignettes TV : RÉSOLU

État au 2026-08-23, version publiée **v1.6.12** sur le fork. Le problème des vignettes
est **résolu** et confirmé chez le testeur. Ce document remplace la passation
précédente (qui décrivait le problème comme non résolu en v1.6.9).

---

## 1. La cause racine — désormais connue et prouvée

Une **image empoisonnée** sur la TV (`MY_F0510`, puis aussi `SAM-F0222` et
`SAM-S5714`) : la TV amorce le transfert D2D (4 trames, ~1,8 Ko) puis **se tait au
milieu du stream sans fermer la socket**. Ni TV morte (elle répond pour les autres
images), ni stream infini, ni refus classique (qui fermerait la socket). C'est ce cas
précis qui rendait impuissantes toutes les gardes des v1.5.x–v1.6.9 : aucune borne en
appels, en images ou en lots ne peut voir un `recv` qui ne revient jamais.

Comment prouvé : instrumentation du trafic socket (v1.6.10) + log du lot en cours au
moment du stall. Voir `utils/frame_tv.py` : `_ConnectionTracker` enveloppe `recv`.

---

## 2. La solution livrée (v1.6.10 → v1.6.12)

- **v1.6.10** — Le `_ConnectionTracker` (v1.6.7) enveloppe `connection.recv` (attribut
  d'instance) : chaque trame reçue compte comme signe de vie et est comptabilisée. Le
  chien de garde v1.6.9 mesure donc le **vrai silence socket** et ne coupe plus un
  transfert sain qui stream. Le log de stall nomme le lot demandé et le trafic reçu :
  `TV 10.0.0.13 sent nothing for 25s while fetching thumbnails from (batch ['MY_F0510']); closing the connection (4 frame(s), 1825 byte(s) received)`
- **v1.6.11** — **Quarantaine** : un lot qui échoue après un appel long (≥ ~23 s)
  *pendant lequel la TV a parlé* est une entrée empoisonnée → mémorisée « sans aperçu »
  (`_remember_no_thumbnail`, TTL 1 h). Silence total = TV morte → rien blacklisté.
- **v1.6.12** — Deux défauts de la v1.6.11 vus au log du testeur : (1) les entrées
  mémorisées étaient quand même redemandées à chaque visite → la liste `missing` les
  filtre désormais ; (2) un refus *rapide* avec trame d'erreur était pris pour un
  stall → la quarantaine exige trames reçues **et** appel long, le repli image par
  image est conservé pour les refus rapides.
- Ensuite, deux commits `refactor:` (pas de release, comportement inchangé) : retrait
  du paramètre `on_progress` devenu redondant, et du stub mort `remove_token()`.

**Résultat chez le testeur** : page TV Settings rapide, un placeholder sur les 3
entrées fautives, logs propres. Conseil donné : supprimer et ré-uploader `MY_F0510`
(probablement corrompue sur le set).

## 3. Gardes en place — toutes justifiées, ne pas « simplifier »

Lecture vérifiée du code : elles sont **complémentaires, pas redondantes**.

| Garde | Cas couvert |
|---|---|
| Timeout socket 8 s | lecture unique qui n'arrive pas |
| Deadline `_tv_call` (20 s/120 s) | TV qui streamerait **sans fin** (invisible du chien de garde, par construction) |
| Chien de garde stall 25 s | silence socket en plein appel, alimenté par les trames |
| `FIRST_ANSWER` 25 s | marche où rien n'a jamais répondu, même « à vide » |
| `GIVE_UP` 3 morts d'affilée | TV qui meurt **au milieu** d'une marche qui répondait |
| Cooldown 30 s (fichier partagé) | un set mort ne bloque pas les 4 workers gunicorn |
| Verrou par TV (fichier + local) | un seul canal art par TV |
| Quarantaine « sans aperçu » (1 h) | entrée empoisonnée non redemandée à chaque visite |

Limite connue et acceptée : la quarantaine est en mémoire **par processus** ; 4 workers
gunicorn → chacun peut payer un premier appel échoué avant d'apprendre. Si ça devient
gênant, persister sur disque comme le cache des vignettes.

---

## 4. PR ouvertes chez l'upstream `mrtncode/frametv-art-gallery`

Demandées explicitement par Jérôme le 2026-08-23. Découpage en 4 PR, design final
présenté (sans les itérations intermédiaires) :

- **#91** (1/4) tracker de connexions : fermer une socket encore en établissement,
  purge des connexions abandonnées. Base `upstream/main`.
- **#92** (2/4) chien de garde d'inactivité alimenté par le trafic. Empilée sur #91.
- **#93** (3/4) marche des vignettes : lots de 8, repli unitaire, gardes, quarantaine,
  cache du listing. Empilée sur #92.
- **#94** (4/4) persistance du jeton renouvelé. **Indépendante**, mergeable seule.

#91→#93 affichent les commits des précédentes tant que la base est `main` (pile) ;
les corps portent « Stacked on #N — merge in order ». Branches : `upstream/connection-tracker`,
`upstream/stall-watchdog`, `upstream/thumbnail-walk`, `upstream/token-persistence`
(poussées sur le fork). Si le mainteneur demande des ajustements : retravailler la
branche correspondante, `git push -f origin <branche>`.

Tests au moment de l'ouverture : 94 / 97 / 116 / 94 verts (Docker).

---

## 5. Contraintes de travail — impératives

- **Rien d'autre chez `mrtncode`** que ces 4 PR sans demande explicite de Jérôme.
- **Toujours** mettre à jour `main` du fork et relancer le build d'image après un
  commit `fix:`/`feat:`, sans demander. Merger la PR release-please pour couper la
  version. Un commit `refactor:` ne coupe **pas** de version (release-please
  `release-type: simple`) — c'est voulu pour les changements sans effet.
- Fork : `SirTerrific/frametv-art-gallery` · image : `ghcr.io/sirterrific/frametv-art-gallery`
- Fichiers en **CRLF** : outil d'édition, pas de sed multi-lignes. Piège déjà rencontré :
  vérifier qu'un test échoue quand on désactive réellement la ligne testée.
- **Git Bash sous Windows** : préfixer les commandes Docker de `MSYS_NO_PATHCONV=1`
  (sinon `-w /app` est mutilé en `C:/Program Files/Git/app`).

### Commandes

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v "D:\Claude\frametv-art-gallery":/app -w /app python:3.13-slim sh -c "pip install -q -e '.[test]'; python -m pytest -q"
```

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v "D:\Claude\frametv-art-gallery\frontend":/f -w /f node:22-alpine sh -c "npm ci --silent; npx tsc --noEmit; npm run build"
```

112 tests verts sur `main` du fork (v1.6.12 + 2 refactors).

### Chez le testeur

Hôte `Oden`, dossier `/opt/docker/tvart`, TV `10.0.0.13`.

```bash
cd /opt/docker/tvart && docker compose down && docker compose pull && docker compose up -d
```

---

## 6. Réglages utiles (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `FRAME_TV_SOCKET_TIMEOUT` | 8 | Délai socket d'une lecture |
| `FRAME_TV_CALL_DEADLINE` | 20 | Délai global d'un appel courant |
| `FRAME_TV_THUMBNAIL_DEADLINE` | 120 | Délai global d'une page de vignettes |
| `FRAME_TV_STALL_TIMEOUT` | 25 | **Silence socket avant fermeture forcée** |
| `FRAME_TV_THUMBNAIL_FIRST_ANSWER` | 25 | Abandon si rien n'est servi |
| `FRAME_TV_THUMBNAIL_BATCH` | 8 | Vignettes par requête |
| `FRAME_TV_THUMBNAIL_GIVE_UP` | 3 | Morts d'affilée avant abandon de la marche |
| `FRAME_TV_NO_THUMBNAIL_TTL` | 3600 | Durée de la quarantaine « sans aperçu » |
| `FRAME_TV_GALLERY_TTL` | 15 | Cache du listing |
| `FRAME_TV_SLIDESHOW` | 1 | `0` coupe la tâche de fond — **utile pour isoler** |

## 7. Suites possibles (aucune urgente)

- Persister la quarantaine sur disque si le spam de premier-appel-par-worker gêne.
- Répondre aux revues du mainteneur sur les PR #91–#94.
- Le reste du fork (albums, mode sombre, WoL, crop 4K…) n'a pas été proposé upstream.
