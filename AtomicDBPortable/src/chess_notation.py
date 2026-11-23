"""
AtomicDB Portable - Chess & Atomic Chess Algebraic Notation + Opening Helper
Converts UCI PV move lists into algebraic notation (SAN) and identifies
authentic chess / Atomic chess openings without fabricating fake names.
"""

import hashlib
import html as _html
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

FILES = "abcdefgh"
RANKS = "12345678"
STANDARD_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
DEFAULT_ATOMICDB_SERVER = "https://belzedar.duckdns.org"


class _BoardState:
    """Lightweight board supporting Atomic & Standard FEN parsing and UCI->SAN."""

    def __init__(self, fen: str = STANDARD_START_FEN):
        self.grid: List[List[Optional[str]]] = [[None] * 8 for _ in range(8)]
        self.turn: str = "w"
        self.ep_sq: Optional[Tuple[int, int]] = None
        self.fullmove: int = 1
        self._load_fen(fen)

    def _load_fen(self, fen: str):
        parts = (fen or "").strip().split()
        if len(parts) < 2:
            parts = STANDARD_START_FEN.split()
        rows = parts[0].split("/")
        if len(rows) != 8:
            rows = STANDARD_START_FEN.split()[0].split("/")
        for fen_r, row_str in enumerate(rows):
            r, f = 7 - fen_r, 0
            for ch in row_str:
                if ch.isdigit():
                    f += int(ch)
                elif f < 8:
                    self.grid[r][f] = ch
                    f += 1
        self.turn = parts[1] if len(parts) > 1 and parts[1] in ("w", "b") else "w"
        ep_str = parts[3] if len(parts) > 3 else "-"
        if len(ep_str) == 2 and ep_str[0] in FILES and ep_str[1] in RANKS:
            self.ep_sq = (RANKS.index(ep_str[1]), FILES.index(ep_str[0]))
        else:
            self.ep_sq = None
        try:
            self.fullmove = max(1, int(parts[5])) if len(parts) > 5 else 1
        except ValueError:
            self.fullmove = 1

    def position_key(self) -> Tuple[str, str]:
        """Returns normalized (board_fen, turn) for opening matching."""
        rows = []
        for r in range(7, -1, -1):
            empty, row_s = 0, []
            for f in range(8):
                piece = self.grid[r][f]
                if piece is None:
                    empty += 1
                else:
                    if empty:
                        row_s.append(str(empty))
                        empty = 0
                    row_s.append(piece)
            if empty:
                row_s.append(str(empty))
            rows.append("".join(row_s))
        return ("/".join(rows), self.turn)

    @staticmethod
    def _same_color(piece: str, color: str) -> bool:
        return (piece.isupper() and color == "w") or (piece.islower() and color == "b")

    def _can_reach(self, from_sq: Tuple[int, int], to_sq: Tuple[int, int], ptype: str) -> bool:
        r1, f1 = from_sq
        r2, f2 = to_sq
        dr, df = r2 - r1, f2 - f1
        if dr == 0 and df == 0:
            return False
        adr, adf = abs(dr), abs(df)

        if ptype == "N":
            return (adr, adf) in ((1, 2), (2, 1))
        if ptype == "K":
            return max(adr, adf) == 1
        if ptype == "B" and adr != adf:
            return False
        if ptype == "R" and dr != 0 and df != 0:
            return False
        if ptype == "Q" and dr != 0 and df != 0 and adr != adf:
            return False
        if ptype not in ("B", "R", "Q"):
            return False

        step_r = 1 if dr > 0 else (-1 if dr < 0 else 0)
        step_f = 1 if df > 0 else (-1 if df < 0 else 0)
        cr, cf = r1 + step_r, f1 + step_f
        while (cr, cf) != (r2, f2):
            if self.grid[cr][cf] is not None:
                return False
            cr += step_r
            cf += step_f
        return True

    def _king_square(self, color: str) -> Optional[Tuple[int, int]]:
        target = "K" if color == "w" else "k"
        for r in range(8):
            for f in range(8):
                if self.grid[r][f] == target:
                    return (r, f)
        return None

    def _is_in_check_atomic(self, color: str) -> bool:
        ksq = self._king_square(color)
        if ksq is None:
            return False
        opp_color = "b" if color == "w" else "w"
        opp_king = self._king_square(opp_color)
        if opp_king is not None and max(abs(ksq[0] - opp_king[0]), abs(ksq[1] - opp_king[1])) <= 1:
            return False

        kr, kf = ksq
        pawn_dir = 1 if color == "w" else -1
        opp_pawn = "p" if color == "w" else "P"
        for df in (-1, 1):
            pr, pf = kr + pawn_dir, kf + df
            if 0 <= pr < 8 and 0 <= pf < 8 and self.grid[pr][pf] == opp_pawn:
                return True

        for r in range(8):
            for f in range(8):
                piece = self.grid[r][f]
                if piece is None or not self._same_color(piece, opp_color):
                    continue
                pt = piece.upper()
                if pt not in ("P", "K") and self._can_reach((r, f), ksq, pt):
                    return True
        return False

    def push_uci_to_san(self, uci: str) -> Optional[str]:
        """Converts a single UCI move to SAN and advances the board state."""
        u = uci.strip()
        if len(u) not in (4, 5) or u[0] not in FILES or u[1] not in RANKS or u[2] not in FILES or u[3] not in RANKS:
            return None
        f1, r1 = FILES.index(u[0]), RANKS.index(u[1])
        f2, r2 = FILES.index(u[2]), RANKS.index(u[3])
        promo = u[4].upper() if len(u) == 5 and u[4].lower() in "qrbn" else None

        piece = self.grid[r1][f1]
        if piece is None or not self._same_color(piece, self.turn):
            return None

        ptype = piece.upper()
        target_piece = self.grid[r2][f2]
        is_castle = ptype == "K" and (
            (r1 == r2 and abs(f2 - f1) == 2)
            or (target_piece is not None and self._same_color(target_piece, self.turn) and target_piece.upper() == "R")
        )
        is_ep = False
        is_capture = False

        if is_castle:
            san_base = "O-O" if f2 > f1 else "O-O-O"
        elif ptype == "P":
            is_ep = target_piece is None and f1 != f2
            is_capture = target_piece is not None or is_ep
            san_base = f"{FILES[f1]}x{FILES[f2]}{RANKS[r2]}" if is_capture else f"{FILES[f2]}{RANKS[r2]}"
            if promo:
                san_base += f"={promo}"
        else:
            is_capture = target_piece is not None
            others = [
                (r, f) for r in range(8) for f in range(8)
                if (r, f) != (r1, f1) and self.grid[r][f] == piece and self._can_reach((r, f), (r2, f2), ptype)
            ]
            disambig = ""
            if others:
                if not any(of == f1 for _, of in others):
                    disambig = FILES[f1]
                elif not any(orow == r1 for orow, _ in others):
                    disambig = RANKS[r1]
                else:
                    disambig = f"{FILES[f1]}{RANKS[r1]}"
            san_base = f"{ptype}{disambig}{'x' if is_capture else ''}{FILES[f2]}{RANKS[r2]}"

        next_ep: Optional[Tuple[int, int]] = None
        if is_castle:
            rook_char = "R" if self.turn == "w" else "r"
            self.grid[r1][f1] = None
            king_dest_f, rook_dest_f = (6, 5) if f2 > f1 else (2, 3)
            rook_from_f = f2 if (target_piece and target_piece.upper() == "R") else (7 if f2 > f1 else 0)
            self.grid[r1][rook_from_f] = None
            self.grid[r1][king_dest_f] = piece
            self.grid[r1][rook_dest_f] = rook_char
        else:
            self.grid[r1][f1] = None
            if is_ep:
                self.grid[r1][f2] = None
            self.grid[r2][f2] = (promo if self.turn == "w" else promo.lower()) if promo else piece
            if ptype == "P" and abs(r2 - r1) == 2:
                next_ep = ((r1 + r2) // 2, f1)
            if is_capture:
                self.grid[r2][f2] = None
                for dr in (-1, 0, 1):
                    for df in (-1, 0, 1):
                        nr, nf = r2 + dr, f2 + df
                        if 0 <= nr < 8 and 0 <= nf < 8:
                            adj = self.grid[nr][nf]
                            if adj is not None and adj.upper() != "P":
                                self.grid[nr][nf] = None

        self.ep_sq = next_ep
        opp_color = "b" if self.turn == "w" else "w"
        if self.turn == "b":
            self.fullmove += 1
        self.turn = opp_color

        if self._king_square(opp_color) is None:
            san_base += "#"
        elif self._is_in_check_atomic(opp_color):
            san_base += "+"
        return san_base

    def push_san_simple(self, san: str) -> Optional[str]:
        """Plays a clean opening SAN move (to index authentic opening positions)."""
        s = san.strip().rstrip("+#!?")
        if s in ("O-O", "O-O-O"):
            r = 0 if self.turn == "w" else 7
            uci = f"e{RANKS[r]}{'g' if s == 'O-O' else 'c'}{RANKS[r]}"
            self.push_uci_to_san(uci)
            return uci

        promo = ""
        if "=" in s:
            s, p = s.split("=", 1)
            promo = p[:1].lower()

        if len(s) < 2:
            return None
        to_str = s[-2:]
        if to_str[0] not in FILES or to_str[1] not in RANKS:
            return None
        r2, f2 = RANKS.index(to_str[1]), FILES.index(to_str[0])
        prefix = s[:-2].replace("x", "")
        ptype = prefix[0] if prefix and prefix[0] in "NBRQK" else "P"
        disambig = prefix[1:] if ptype != "P" else prefix
        dis_file = disambig[0] if disambig and disambig[0] in FILES else None
        dis_rank = disambig[-1] if disambig and disambig[-1] in RANKS else None

        for r1 in range(8):
            for f1 in range(8):
                piece = self.grid[r1][f1]
                if piece is None or not self._same_color(piece, self.turn) or piece.upper() != ptype:
                    continue
                if (dis_file and FILES[f1] != dis_file) or (dis_rank and RANKS[r1] != dis_rank):
                    continue
                if ptype == "P":
                    direction = 1 if self.turn == "w" else -1
                    target = self.grid[r2][f2]
                    if f1 == f2 and target is None:
                        start_rank = 1 if self.turn == "w" else 6
                        if not (
                            r2 == r1 + direction
                            or (r2 == r1 + 2 * direction and r1 == start_rank and self.grid[r1 + direction][f1] is None)
                        ):
                            continue
                    elif not (abs(f2 - f1) == 1 and r2 == r1 + direction and (target is not None or self.ep_sq == (r2, f2))):
                        continue
                elif not self._can_reach((r1, f1), (r2, f2), ptype):
                    continue

                uci = f"{FILES[f1]}{RANKS[r1]}{FILES[f2]}{RANKS[r2]}{promo}"
                self.push_uci_to_san(uci)
                return uci
        return None


_AUTHENTIC_OPENING_LINES: List[Tuple[Tuple[str, ...], str]] = [
    (("Nf3",), "Zukertort Opening"),
    (("Nf3", "f6"), "Atomic Defense"),
    (("Nf3", "f6", "e4"), "Center Attack"),
    (("Nf3", "f6", "e4", "d5"), "Center Attack"),
    (("Nf3", "f6", "e4", "d5", "Nc3"), "Center Attack"),
    (("Nf3", "f6", "e4", "e5"), "Center Attack"),
    (("Nf3", "f6", "e4", "Nc6"), "Center Attack"),
    (("Nf3", "f6", "e4", "c5"), "Center Attack"),
    (("Nf3", "f6", "d4"), "Queen's Pawn Atomic"),
    (("Nf3", "f6", "Nc3"), "Three Knights Atomic"),
    (("Nf3", "f6", "e3"), "Zukertort Atomic"),
    (("Nf3", "d5"), "Reti Gambit"),
    (("Nf3", "d5", "d4"), "Reti-Queen's Pawn"),
    (("Nf3", "Nc6"), "Black Knight Defense"),
    (("Nf3", "e5"), "King's Pawn Countergambit"),
    (("Nf3", "e6"), "French Atomic"),
    (("Nf3", "c5"), "Sicilian Atomic"),
    (("Nf3", "Nf6"), "Symmetrical Zukertort"),
    (("e4",), "King's Pawn Opening"),
    (("e4", "e5"), "Open Game"),
    (("e4", "e5", "Nf3"), "King's Knight Opening"),
    (("e4", "e5", "Nf3", "Nc6"), "Open Game"),
    (("e4", "e5", "Nf3", "Nc6", "Bb5"), "Ruy Lopez"),
    (("e4", "e5", "Nf3", "Nc6", "Bc4"), "Italian Game"),
    (("e4", "e5", "Nf3", "Nc6", "d4"), "Scotch Game"),
    (("e4", "e5", "Nf3", "Nf6"), "Petrov's Defense"),
    (("e4", "e5", "Bc4"), "Bishop's Opening"),
    (("e4", "e5", "Nc3"), "Vienna Game"),
    (("e4", "e5", "f4"), "King's Gambit"),
    (("e4", "e5", "Qh5"), "Wayward Queen Attack"),
    (("e4", "c5"), "Sicilian Defense"),
    (("e4", "c5", "Nf3", "d6"), "Sicilian Defense"),
    (("e4", "c5", "Nf3", "Nc6"), "Sicilian Defense"),
    (("e4", "c5", "c3"), "Sicilian Alapin"),
    (("e4", "e6"), "French Defense"),
    (("e4", "e6", "d4", "d5"), "French Defense"),
    (("e4", "c6"), "Caro-Kann Defense"),
    (("e4", "c6", "d4", "d5"), "Caro-Kann Defense"),
    (("e4", "d5"), "Scandinavian Defense"),
    (("e4", "d6"), "Pirc Defense"),
    (("e4", "g6"), "Modern Defense"),
    (("e4", "Nf6"), "Alekhine's Defense"),
    (("e4", "f6"), "Barnes Defense"),
    (("d4",), "Queen's Pawn Opening"),
    (("d4", "d5"), "Closed Game"),
    (("d4", "d5", "c4"), "Queen's Gambit"),
    (("d4", "d5", "c4", "e6"), "Queen's Gambit Declined"),
    (("d4", "d5", "c4", "c6"), "Slav Defense"),
    (("d4", "d5", "Bf4"), "London System"),
    (("d4", "Nf6"), "Indian Defense"),
    (("d4", "Nf6", "c4"), "Indian Defense"),
    (("d4", "Nf6", "c4", "g6"), "King's Indian Defense"),
    (("d4", "Nf6", "c4", "e6"), "Nimzo / Queen's Indian"),
    (("d4", "f5"), "Dutch Defense"),
    (("c4",), "English Opening"),
    (("Nc3",), "Dunst Opening"),
    (("f4",), "Bird's Opening"),
    (("b3",), "Nimzo-Larsen Attack"),
    (("g3",), "Benko's Opening"),
]


def _build_opening_position_index() -> Dict[Tuple[str, str], Tuple[str, Tuple[str, ...]]]:
    index: Dict[Tuple[str, str], Tuple[str, Tuple[str, ...]]] = {}
    for moves_tuple, name in _AUTHENTIC_OPENING_LINES:
        board = _BoardState(STANDARD_START_FEN)
        if all(board.push_san_simple(mv) is not None for mv in moves_tuple):
            index.setdefault(board.position_key(), (name, moves_tuple))
    return index


_OPENING_POSITION_INDEX = _build_opening_position_index()


def identify_opening_for_fen(fen: str) -> Optional[str]:
    if not fen or fen.strip().startswith("solve "):
        return None
    entry = _OPENING_POSITION_INDEX.get(_BoardState(fen).position_key())
    return entry[0] if entry else None


def _clean_task_fen(fen: Optional[str]) -> str:
    clean_fen = (fen or "").strip()
    if clean_fen.lower().startswith("solve "):
        rest = clean_fen[6:].strip()
        clean_fen = rest.split(" goal ", 1)[0].strip() if " goal " in rest else rest
    return clean_fen


def normalize_fen_for_atomicdb(fen: Optional[str]) -> Optional[str]:
    clean = _clean_task_fen(fen)
    parts = clean.split()
    if len(parts) < 4 or "/" not in parts[0]:
        return None
    return f"{parts[0]} {parts[1]} {parts[2]} {parts[3]} 0 1"


def compute_atomicdb_position_key(fen: Optional[str]) -> Optional[str]:
    norm = normalize_fen_for_atomicdb(fen)
    if not norm:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _is_uci_token(tok: str) -> bool:
    return (
        len(tok) in (4, 5)
        and tok[0] in FILES and tok[1] in RANKS
        and tok[2] in FILES and tok[3] in RANKS
        and (len(tok) == 4 or tok[4].lower() in "qrbn")
    )


def _tokenize_move_seq(moves: Optional[str]) -> List[str]:
    tokens: List[str] = []
    for raw in (moves or "").replace(",", " ").strip().split():
        cleaned = raw.strip()
        if not cleaned or (cleaned[0].isdigit() and (cleaned.endswith(".") or cleaned.endswith("..."))):
            continue
        if "." in cleaned and cleaned.split(".", 1)[0].isdigit():
            cleaned = cleaned.split(".", 1)[1].lstrip(".")
        if cleaned and cleaned not in ("*", "1-0", "0-1", "1/2-1/2"):
            tokens.append(cleaned)
    return tokens


def build_atomicdb_explore_url(
    fen: Optional[str],
    play_moves: Optional[str] = None,
    server_url: str = DEFAULT_ATOMICDB_SERVER,
) -> Optional[str]:
    key = compute_atomicdb_position_key(fen)
    if not key:
        return None
    base = (server_url or DEFAULT_ATOMICDB_SERVER).rstrip("/")
    url = f"{base}/atomicdb/explore/{key}/"
    uci_list = [tok for tok in _tokenize_move_seq(play_moves) if _is_uci_token(tok)]
    if uci_list:
        url += f"?play={urllib.parse.quote(','.join(uci_list), safe='')}"
    return url


def parse_atomicdb_explore_html(html_text: str) -> Dict[str, str]:
    text = html_text or ""
    opening = ""
    if m_oname := re.search(r'id="opening-name"[^>]*>(.*?)</h2>', text, re.S | re.I):
        raw_name = re.sub(r"<[^>]+>", "", m_oname.group(1))
        cleaned_name = " ".join(_html.unescape(raw_name).split()).strip()
        if cleaned_name and cleaned_name.lower() != "starting position":
            opening = cleaned_name
    elif m_op := re.search(r'Last named Atomic opening on this line"[^>]*>(.*?)</span>', text, re.S | re.I):
        cleaned_name = " ".join(_html.unescape(re.sub(r"<[^>]+>", "", m_op.group(1))).split()).strip()
        if cleaned_name and cleaned_name.lower() != "starting position":
            opening = cleaned_name

    play_uci = ""
    if m_play := re.search(r'name="play"[^>]*value="([^"]*)"', text, re.I):
        play_uci = urllib.parse.unquote(_html.unescape(m_play.group(1))).strip()
    elif m_cur := re.search(r'class="cur"[^>]*href="[^"]*\?play=([^"&]+)"', text, re.I):
        play_uci = urllib.parse.unquote(_html.unescape(m_cur.group(1))).strip()

    line_text = ""
    if m_crumbs := re.search(r'<div[^>]*class="[^"]*crumbs[^"]*"[^>]*>(.*?)</div>', text, re.S | re.I):
        crumb_plain = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", m_crumbs.group(1))).split()).strip()
        if "…" in crumb_plain or "deep line" in crumb_plain.lower():
            line_text = crumb_plain

    return {"opening_name": opening, "play_uci": play_uci, "line_text": line_text}


def _replay_san_line_to_uci(san_text: str) -> Tuple[str, str]:
    """Replays a full move-1 SAN line into comma-separated UCI moves and normalized board key tuple."""
    clean = (san_text or "").strip()
    if not clean or "…" in clean or "..." in clean or "deep line" in clean.lower():
        return "", ""
    tokens = _tokenize_move_seq(clean)
    if not tokens:
        return "", ""
    board = _BoardState(STANDARD_START_FEN)
    ucis: List[str] = []
    for tok in tokens:
        uci = board.push_uci_to_san(tok) if _is_uci_token(tok) else None
        if _is_uci_token(tok):
            if uci is None:
                return "", ""
            ucis.append(tok)
        else:
            mv_uci = board.push_san_simple(tok)
            if mv_uci is None:
                return "", ""
            ucis.append(mv_uci)
    return ",".join(ucis), "|".join(board.position_key())


def parse_atomicdb_queue_html(html_text: str) -> Dict[str, Dict[str, str]]:
    """Extracts live queue line titles, opening families, and playable UCI paths keyed by 64-hex position key."""
    entries: Dict[str, Dict[str, str]] = {}
    for item_html in re.findall(r"<li>.*?class=\"qline\".*?</li>", html_text or "", re.S | re.I):
        m_key = re.search(r'href="/atomicdb/explore/([0-9a-f]{64})/', item_html, re.I)
        if not m_key:
            continue
        key = m_key.group(1).lower()
        m_title = re.search(r'class="qline"[^>]*title="([^"]*)"', item_html, re.I)
        m_text = re.search(r'class="qline"[^>]*>(.*?)</a>', item_html, re.S | re.I)
        title_line = " ".join(_html.unescape(m_title.group(1)).split()).strip() if m_title else ""
        vis_line = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", m_text.group(1))).split()).strip() if m_text else ""
        best_line = title_line or vis_line

        opening = ""
        if m_op := re.search(r'Last named Atomic opening on this line"[^>]*>(.*?)</span>', item_html, re.S | re.I):
            opening = " ".join(_html.unescape(re.sub(r"<[^>]+>", "", m_op.group(1))).split()).strip()
            if opening.lower() == "starting position":
                opening = ""

        play_uci, _ = _replay_san_line_to_uci(best_line)
        entries[key] = {
            "key": key,
            "opening_name": opening,
            "play_uci": play_uci,
            "line_text": best_line,
        }
    return entries


def format_deep_or_elided_line(line_text: Optional[str], opening_name: Optional[str] = None) -> str:
    """Normalizes AtomicDB deep/elided lines so opening family comes first and depth prefix is clean."""
    text = " ".join((line_text or "").replace("\xa0", " ").split()).strip()
    opening = (
        opening_name.strip()
        if (opening_name and opening_name.strip() and opening_name.strip().lower() != "starting position")
        else ""
    )
    if not text:
        return opening

    # Handle AtomicDB deep lines like: "deep line, ply ≥69 · … Kg6 c8=B Bxd3 h4"
    m_deep = re.match(r"^(deep line[^·]*?)\s*·\s*(.+)$", text, re.I)
    if m_deep:
        depth_label = m_deep.group(1).strip()
        tail_moves = m_deep.group(2).strip()
        if opening:
            return f"{opening} ({depth_label}): {tail_moves}"
        return f"{depth_label}: {tail_moves}"

    return f"{opening}: {text}" if opening else text


_EXPLORE_CACHE_LOCK = threading.Lock()
_EXPLORE_CACHE: Dict[str, Dict[str, str]] = {}
_QUEUE_CACHE: Dict[str, Any] = {"ts": 0.0, "entries": {}}
_EXPLORE_429_UNTIL: float = 0.0


def _fetch_atomicdb_queue_index(server_url: str = DEFAULT_ATOMICDB_SERVER, timeout: float = 4.0) -> Dict[str, Dict[str, str]]:
    now = time.time()
    with _EXPLORE_CACHE_LOCK:
        if now - float(_QUEUE_CACHE["ts"]) < 15.0 and _QUEUE_CACHE["entries"]:
            return dict(_QUEUE_CACHE["entries"])
    base = (server_url or DEFAULT_ATOMICDB_SERVER).rstrip("/")
    try:
        req = urllib.request.Request(f"{base}/atomicdb/", headers={"User-Agent": "AtomicDBPortable/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        parsed = parse_atomicdb_queue_html(body)
        if parsed:
            with _EXPLORE_CACHE_LOCK:
                _QUEUE_CACHE["ts"] = time.time()
                _QUEUE_CACHE["entries"] = dict(parsed)
        return parsed
    except Exception:
        with _EXPLORE_CACHE_LOCK:
            return dict(_QUEUE_CACHE["entries"])


def fetch_atomicdb_explore_info(
    fen: Optional[str],
    server_url: str = DEFAULT_ATOMICDB_SERVER,
    timeout: float = 3.0,
) -> Optional[Dict[str, str]]:
    global _EXPLORE_429_UNTIL
    key = compute_atomicdb_position_key(fen)
    if not key:
        return None
    with _EXPLORE_CACHE_LOCK:
        cached = _EXPLORE_CACHE.get(key)
        in_cooldown = time.time() < _EXPLORE_429_UNTIL
    if cached is not None:
        return dict(cached)

    base = (server_url or DEFAULT_ATOMICDB_SERVER).rstrip("/")
    explore_url = f"{base}/atomicdb/explore/{key}/"
    info: Dict[str, str] = {"opening_name": "", "play_uci": "", "line_text": ""}

    if not in_cooldown:
        try:
            req = urllib.request.Request(explore_url, headers={"User-Agent": "AtomicDBPortable/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            info = parse_atomicdb_explore_html(body)
        except urllib.error.HTTPError as err:
            if err.code == 429:
                with _EXPLORE_CACHE_LOCK:
                    _EXPLORE_429_UNTIL = time.time() + 30.0
        except Exception:
            pass

    # Merge queue index metadata if explore lacked opening_name/play_uci (e.g. deep line ply >= 69) or hit 429
    if not info.get("play_uci") or not info.get("opening_name"):
        q_entry = _fetch_atomicdb_queue_index(server_url).get(key)
        if q_entry:
            if not info.get("opening_name") and q_entry.get("opening_name"):
                info["opening_name"] = q_entry["opening_name"]
            if not info.get("play_uci") and q_entry.get("play_uci"):
                info["play_uci"] = q_entry["play_uci"]
            if not info.get("line_text") and q_entry.get("line_text"):
                info["line_text"] = q_entry["line_text"]

    if not any(info.get(k) for k in ("opening_name", "play_uci", "line_text")):
        return None

    info["key"] = key
    info["url"] = build_atomicdb_explore_url(fen, info.get("play_uci"), server_url) or explore_url
    with _EXPLORE_CACHE_LOCK:
        _EXPLORE_CACHE[key] = dict(info)
    return info


def format_calculating_line(
    fen: Optional[str],
    pv_uci: str,
    prefix_moves: Optional[str] = None,
    max_moves: Optional[int] = 8,
    opening_name: Optional[str] = None,
) -> str:
    """Formats a line in chronological algebraic notation from the first move (+ opening family)."""
    raw_pv = (pv_uci or "").strip()
    clean_fen = _clean_task_fen(fen)
    if not clean_fen or len(clean_fen.split()) < 2:
        return raw_pv

    max_plies = (max(1, int(max_moves)) * 2) if max_moves is not None else None
    fen_key = _BoardState(clean_fen).position_key()
    opening_entry = _OPENING_POSITION_INDEX.get(fen_key)

    prefix_san: List[str] = []
    matched_opening: Optional[str] = (
        opening_name.strip()
        if (opening_name and opening_name.strip() and opening_name.strip().lower() != "starting position")
        else None
    )

    # 1. Prefer explicit chronological moves from move 1 leading to the task FEN
    explicit_tokens = _tokenize_move_seq(prefix_moves)
    if explicit_tokens:
        sim = _BoardState(STANDARD_START_FEN)
        replayed_san: List[str] = []
        valid_prefix = True
        for tok in explicit_tokens:
            san = sim.push_uci_to_san(tok) if _is_uci_token(tok) else (tok if sim.push_san_simple(tok) else None)
            if san is None:
                valid_prefix = False
                break
            replayed_san.append(san)
            if not matched_opening and (entry := _OPENING_POSITION_INDEX.get(sim.position_key())):
                matched_opening = entry[0]
        if valid_prefix and sim.position_key() == fen_key:
            prefix_san = replayed_san

    # 2. Otherwise recover known opening moves from move 1 if the task FEN matches an opening
    if not prefix_san and opening_entry is not None:
        if not matched_opening:
            matched_opening = opening_entry[0]
        prefix_san = list(opening_entry[1])

    # Replay chronologically from move 1 when prefix is known; else format PV from task FEN
    formatted_tokens: List[str] = []
    if prefix_san:
        board = _BoardState(STANDARD_START_FEN)
        for idx, mv_san in enumerate(prefix_san):
            if max_plies is not None and len(formatted_tokens) >= max_plies:
                break
            move_turn, move_num = board.turn, board.fullmove
            if board.push_san_simple(mv_san) is None:
                formatted_tokens = []
                board = _BoardState(clean_fen)
                break
            if not opening_name and (entry := _OPENING_POSITION_INDEX.get(board.position_key())):
                matched_opening = entry[0]
            if move_turn == "w":
                formatted_tokens.append(f"{move_num}. {mv_san}")
            elif idx == 0:
                formatted_tokens.append(f"{move_num}... {mv_san}")
            else:
                formatted_tokens.append(mv_san)
    else:
        board = _BoardState(clean_fen)

    for uci in raw_pv.split():
        if max_plies is not None and len(formatted_tokens) >= max_plies:
            break
        move_turn, move_num = board.turn, board.fullmove
        san = board.push_uci_to_san(uci)
        if san is None:
            if not formatted_tokens:
                return raw_pv
            break
        if not opening_name and (entry := _OPENING_POSITION_INDEX.get(board.position_key())):
            matched_opening = entry[0]
        if move_turn == "w":
            formatted_tokens.append(f"{move_num}. {san}")
        elif not formatted_tokens:
            formatted_tokens.append(f"{move_num}... {san}")
        else:
            formatted_tokens.append(san)

    if not formatted_tokens:
        return raw_pv
    san_line = " ".join(formatted_tokens)
    return f"{matched_opening}: {san_line}" if matched_opening else san_line


def format_task_start_line(
    fen_info: str,
    prefix_moves: Optional[str] = None,
    max_moves: Optional[int] = None,
    opening_name: Optional[str] = None,
) -> str:
    clean = (fen_info or "").strip()
    if not clean:
        return "Waiting for PV..."
    formatted = format_calculating_line(
        clean, "", prefix_moves=prefix_moves, max_moves=max_moves, opening_name=opening_name
    )
    if formatted:
        return formatted
    opening = opening_name or identify_opening_for_fen(clean)
    return f"{opening} ({clean})" if opening else clean
