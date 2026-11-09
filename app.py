from __future__ import annotations

import json
import html
import os
import re
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / ".gg_arena_data.json"
COLORS = ["#6654e8", "#258c73", "#e68c46", "#d6536c", "#4386c8", "#8c63c7", "#4d9eae", "#c26687"]
PAGES = ["Visão geral", "Campeonatos", "Equipes", "Partidas", "Classificação"]

st.set_page_config(page_title="GG Arena | Campeonatos", page_icon="🎮", layout="wide")
st.markdown(
    """
    <style>
    html, body, [class*="css"] { font-family: ui-sans-serif, system-ui, sans-serif; }
    .stApp { background: #f5f6fb; color: #20243a; }
    [data-testid="stSidebar"] { background: #fff; border-right: 1px solid #e9eaf1; }
    [data-testid="stMetric"] { background: #fff; border: 1px solid #e9eaf1; padding: 14px 16px; border-radius: 13px; box-shadow: 0 8px 24px #2225450d; }
    [data-testid="stMetricLabel"] { color: #85899d; }
    [data-testid="stMetricValue"] { color: #20243a; }
    div[data-testid="stVerticalBlockBorderWrapper"] { background: #fff; border-color: #e9eaf1; border-radius: 13px; }
    .arena-hero { padding: 25px 28px; margin: 4px 0 20px; border-radius: 16px; color: white; background: radial-gradient(ellipse at 87% 15%, #6254d4 0, transparent 37%), linear-gradient(110deg, #242840, #343357); }
    .arena-hero small { color: #c9ef71; font-weight: 800; letter-spacing: 1px; }
    .arena-hero h2 { margin: 7px 0; color: white; font-size: 24px; }
    .arena-hero p { margin: 0; color: #d0d0df; }
    .muted { color: #85899d; }
    .team-chip { display: inline-block; padding: 3px 8px; border-radius: 20px; background: #efedff; color: #6654e8; font-size: 12px; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def iso_day(offset: int = 0) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def round_robin(teams: list[dict[str, Any]]) -> list[list[tuple[dict[str, Any], dict[str, Any]]]]:
    entries: list[dict[str, Any] | None] = list(teams)
    if len(entries) % 2:
        entries.append(None)
    rounds: list[list[tuple[dict[str, Any], dict[str, Any]]]] = []
    for _ in range(max(0, len(entries) - 1)):
        fixtures = []
        for index in range(len(entries) // 2):
            home, away = entries[index], entries[-1 - index]
            if home is not None and away is not None:
                fixtures.append((home, away))
        rounds.append(fixtures)
        entries = [entries[0], entries[-1], *entries[1:-1]]
    return rounds


def create_demo() -> list[dict[str, Any]]:
    names = [
        ("Lobos do Norte", "LDN", "#6654e8"),
        ("Vortex", "VTX", "#258c73"),
        ("Pixel Force", "PXF", "#e68c46"),
        ("Nexus Five", "N5", "#d6536c"),
        ("Cloud 9 Lives", "C9L", "#4386c8"),
        ("Zero Gravity", "ZGR", "#8c63c7"),
    ]
    teams = [
        {"id": f"demo-team-{index}", "name": name, "tag": tag, "color": color, "players": []}
        for index, (name, tag, color) in enumerate(names)
    ]
    tournament: dict[str, Any] = {
        "id": "demo-tournament",
        "name": "Copa Nexus — Split 02",
        "game": "Valorant",
        "format": "league",
        "start_date": iso_day(-5),
        "status": "active",
        "teams": teams,
        "matches": [],
        "bye_advances": {},
    }
    for round_number, fixtures in enumerate(round_robin(teams), start=1):
        for match_number, (home, away) in enumerate(fixtures):
            played = round_number == 1 and match_number < 3
            tournament["matches"].append(
                {
                    "id": new_id("match"),
                    "round": round_number,
                    "home_id": home["id"],
                    "away_id": away["id"],
                    "date": iso_day(-1 if played else 1 + (round_number - 1) * 7),
                    "time": f"{18 + match_number}:00",
                    "status": "done" if played else "upcoming",
                    "home_score": [13, 13, 11][match_number] if played else None,
                    "away_score": [9, 7, 13][match_number] if played else None,
                }
            )
    return [tournament]


def validate_data(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise ValueError("O arquivo deve conter uma lista de campeonatos.")
    normalized = []
    tournament_ids: set[str] = set()
    for imported_item in data:
        if not isinstance(imported_item, dict):
            raise ValueError("Cada campeonato precisa ser um objeto válido.")
        item = dict(imported_item)
        item.setdefault("start_date", item.get("startDate"))
        item.setdefault("bye_advances", item.get("byeAdvances", {}))
        item["teams"] = [
            {**team, "players": team.get("players", [])}
            if isinstance(team, dict)
            else team
            for team in item.get("teams", [])
        ]
        item["matches"] = [
            {
                **match,
                "home_id": match.get("home_id", match.get("homeId")),
                "away_id": match.get("away_id", match.get("awayId")),
                "home_score": match.get("home_score", match.get("homeScore")),
                "away_score": match.get("away_score", match.get("awayScore")),
            }
            if isinstance(match, dict)
            else match
            for match in item.get("matches", [])
        ]
        if not isinstance(item, dict):
            raise ValueError("Cada campeonato precisa ser um objeto válido.")
        if (
            not isinstance(item.get("id"), str)
            or not item["id"]
            or item["id"] in tournament_ids
            or not isinstance(item.get("name"), str)
            or not item["name"].strip()
            or not isinstance(item.get("game"), str)
            or not isinstance(item.get("teams"), list)
            or not isinstance(item.get("matches"), list)
            or item.get("format") not in {"league", "knockout"}
            or item.get("status") not in {"active", "upcoming", "done"}
            or not isinstance(item.get("start_date"), str)
        ):
            raise ValueError("Um campeonato contém dados ausentes ou inválidos.")
        try:
            date.fromisoformat(item["start_date"])
        except ValueError as error:
            raise ValueError(f"A data de início de {item['name']} é inválida.") from error
        tournament_ids.add(item["id"])
        team_ids: set[str] = set()
        teams = []
        for team in item["teams"]:
            if (
                not isinstance(team, dict)
                or not isinstance(team.get("id"), str)
                or not team["id"]
                or team["id"] in team_ids
                or not isinstance(team.get("name"), str)
                or not team["name"].strip()
                or not isinstance(team.get("players", []), list)
                or not re.fullmatch(r"#[0-9a-fA-F]{6}", str(team.get("color", COLORS[0])))
            ):
                raise ValueError(f"Uma equipe de {item['name']} contém dados inválidos.")
            team_ids.add(team["id"])
            teams.append(
                {
                    "id": team["id"],
                    "name": team["name"].strip(),
                    "tag": str(team.get("tag", "")),
                    "color": str(team.get("color", COLORS[0])),
                    "players": [str(player) for player in team.get("players", [])],
                }
            )
        matches = []
        match_ids: set[str] = set()
        for match in item["matches"]:
            if (
                not isinstance(match, dict)
                or not isinstance(match.get("id"), str)
                or not match["id"]
                or match["id"] in match_ids
                or match.get("home_id") not in team_ids
                or match.get("away_id") not in team_ids
                or match.get("status") not in {"done", "upcoming"}
                or not isinstance(match.get("round"), int)
                or match["round"] < 1
            ):
                raise ValueError(f"Uma partida de {item['name']} contém dados inválidos.")
            match_ids.add(match["id"])
            home_score, away_score = match.get("home_score"), match.get("away_score")
            if match["status"] == "done":
                if (
                    not isinstance(home_score, int)
                    or isinstance(home_score, bool)
                    or not isinstance(away_score, int)
                    or isinstance(away_score, bool)
                    or home_score < 0
                    or away_score < 0
                    or (item["format"] == "knockout" and home_score == away_score)
                ):
                    raise ValueError(f"O placar de uma partida de {item['name']} é inválido.")
            matches.append({**match})
        normalized.append(
            {
                **item,
                "name": item["name"].strip(),
                "teams": teams,
                "matches": matches,
                "bye_advances": item.get("bye_advances", {}),
            }
        )
    return normalized


def load_data() -> list[dict[str, Any]]:
    if not DATA_FILE.exists():
        return create_demo()
    try:
        return validate_data(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        st.error(f"Não foi possível carregar os dados salvos: {error}")
        return []


def save_data(data: list[dict[str, Any]]) -> bool:
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".gg-arena-", suffix=".tmp", dir=DATA_FILE.parent
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
                json.dump(data, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, DATA_FILE)
        except Exception:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
            raise
        return True
    except OSError as error:
        st.error(f"Não foi possível salvar os dados: {error}")
        return False


if "tournaments" not in st.session_state:
    st.session_state.tournaments = load_data()
    if not DATA_FILE.exists() and st.session_state.tournaments:
        save_data(st.session_state.tournaments)
if "selected_tournament" not in st.session_state:
    st.session_state.selected_tournament = (
        st.session_state.tournaments[0]["id"] if st.session_state.tournaments else ""
    )


def persist() -> bool:
    return save_data(st.session_state.tournaments)


def get_tournament(tournament_id: str | None = None) -> dict[str, Any] | None:
    wanted_id = tournament_id or st.session_state.selected_tournament
    return next(
        (item for item in st.session_state.tournaments if item["id"] == wanted_id),
        None,
    )


def get_team(tournament: dict[str, Any], team_id: str) -> dict[str, Any] | None:
    return next((team for team in tournament["teams"] if team["id"] == team_id), None)


def match_count_done(tournament: dict[str, Any]) -> int:
    return sum(match["status"] == "done" for match in tournament["matches"])


def standings(tournament: dict[str, Any]) -> list[dict[str, Any]]:
    table = {
        team["id"]: {
            "team": team,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "scored": 0,
            "conceded": 0,
            "points": 0,
        }
        for team in tournament["teams"]
    }
    for match in tournament["matches"]:
        if match["status"] != "done":
            continue
        home, away = table.get(match["home_id"]), table.get(match["away_id"])
        if home is None or away is None:
            continue
        home_score, away_score = match["home_score"], match["away_score"]
        home["played"] += 1
        away["played"] += 1
        home["scored"] += home_score
        home["conceded"] += away_score
        away["scored"] += away_score
        away["conceded"] += home_score
        if home_score > away_score:
            home["wins"] += 1
            home["points"] += 3
            away["losses"] += 1
        elif home_score < away_score:
            away["wins"] += 1
            away["points"] += 3
            home["losses"] += 1
        else:
            home["draws"] += 1
            away["draws"] += 1
            home["points"] += 1
            away["points"] += 1
    return sorted(
        table.values(),
        key=lambda row: (
            -row["points"],
            -(row["scored"] - row["conceded"]),
            -row["scored"],
            row["team"]["name"].casefold(),
        ),
    )


def team_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("Nenhuma equipe inscrita neste campeonato.")
        return
    st.dataframe(
        [
            {
                "#": rank,
                "Equipe": row["team"]["name"],
                "J": row["played"],
                "V": row["wins"],
                "E": row["draws"],
                "D": row["losses"],
                "SG": row["scored"] - row["conceded"],
                "Pts": row["points"],
            }
            for rank, row in enumerate(rows, start=1)
        ],
        hide_index=True,
        use_container_width=True,
    )


def status_label(tournament: dict[str, Any]) -> str:
    champion = get_champion(tournament)
    if champion or tournament["status"] == "done":
        return "Finalizado"
    return "Inscrições abertas" if tournament["status"] == "upcoming" else "Em andamento"


def get_champion(tournament: dict[str, Any]) -> dict[str, Any] | None:
    if tournament["format"] != "knockout" or not tournament["matches"]:
        return None
    last_round = max(match["round"] for match in tournament["matches"])
    final = next(
        (
            match
            for match in tournament["matches"]
            if match["round"] == last_round and match["status"] == "done"
        ),
        None,
    )
    if final is None:
        return None
    winner_id = (
        final["home_id"]
        if final["home_score"] > final["away_score"]
        else final["away_id"]
    )
    return get_team(tournament, winner_id)


def format_match_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return "Data a definir"


def build_league_matches(tournament: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for round_number, fixtures in enumerate(round_robin(tournament["teams"]), start=1):
        match_date = date.fromisoformat(tournament["start_date"]) + timedelta(
            days=(round_number - 1) * 7
        )
        for index, (home, away) in enumerate(fixtures):
            matches.append(
                {
                    "id": new_id("match"),
                    "round": round_number,
                    "home_id": home["id"],
                    "away_id": away["id"],
                    "date": match_date.isoformat(),
                    "time": f"{18 + index}:00",
                    "status": "upcoming",
                    "home_score": None,
                    "away_score": None,
                }
            )
    return matches


def round_label(tournament: dict[str, Any], round_number: int) -> str:
    if tournament["format"] == "league":
        return f"Rodada {round_number}"
    matches_in_round = sum(
        match["round"] == round_number for match in tournament["matches"]
    )
    final_round = max((match["round"] for match in tournament["matches"]), default=1)
    if round_number == final_round and matches_in_round == 1:
        return "Final"
    if matches_in_round == 2 and (
        round_number == final_round - 1
        or (round_number == 1 and len(tournament["teams"]) == 4)
    ):
        return "Semifinal"
    if matches_in_round == 4 and (
        round_number == final_round - 2
        or (round_number == 1 and len(tournament["teams"]) == 8)
    ):
        return "Quartas de final"
    return f"Fase {round_number}"


def generate_matches(tournament: dict[str, Any]) -> None:
    if tournament["format"] == "league":
        tournament["matches"] = build_league_matches(tournament)
        tournament["bye_advances"] = {}
        return
    teams = list(tournament["teams"])
    tournament["bye_advances"] = {}
    if len(teams) % 2:
        tournament["bye_advances"] = {"1": [teams.pop()["id"]]}
    tournament["matches"] = [
        {
            "id": new_id("match"),
            "round": 1,
            "home_id": teams[index]["id"],
            "away_id": teams[index + 1]["id"],
            "date": tournament["start_date"],
            "time": f"{18 + index // 2}:00",
            "status": "upcoming",
            "home_score": None,
            "away_score": None,
        }
        for index in range(0, len(teams), 2)
    ]


def advance_knockout(tournament: dict[str, Any], completed_round: int) -> None:
    current_round = [
        match for match in tournament["matches"] if match["round"] == completed_round
    ]
    if not current_round or any(match["status"] != "done" for match in current_round):
        return
    winners = [
        match["home_id"]
        if match["home_score"] > match["away_score"]
        else match["away_id"]
        for match in current_round
    ]
    byes = tournament["bye_advances"].pop(str(completed_round), [])
    advancing = winners + byes
    if len(advancing) <= 1:
        return
    next_round = completed_round + 1
    if len(advancing) % 2:
        tournament["bye_advances"][str(next_round)] = [advancing.pop()]
    for index in range(0, len(advancing), 2):
        tournament["matches"].append(
            {
                "id": new_id("match"),
                "round": next_round,
                "home_id": advancing[index],
                "away_id": advancing[index + 1],
                "date": (date.today() + timedelta(days=next_round * 7)).isoformat(),
                "time": f"{18 + index // 2}:00",
                "status": "upcoming",
                "home_score": None,
                "away_score": None,
            }
        )


def render_sidebar() -> str:
    if "page" not in st.session_state:
        st.session_state.page = PAGES[0]
    with st.sidebar:
        st.markdown("## 🎮 GG Arena")
        st.caption("CAMPEONATOS & COMUNIDADE")
        st.divider()
        page = st.radio("Gerenciar", PAGES, key="page", label_visibility="visible")
        st.divider()
        st.caption("🏆 Organize sua comunidade e descubra quem domina a arena.")
        st.caption(f"📅 {date.today().strftime('%d/%m/%Y')}")
    return page


def navigate(page: str, tournament_id: str | None = None) -> None:
    st.session_state.page = page
    if tournament_id is not None:
        st.session_state.selected_tournament = tournament_id
        for key in ("team_tournament", "match_tournament", "standing_tournament"):
            st.session_state[key] = tournament_id


def sync_selected_tournament(widget_key: str) -> None:
    tournament_id = st.session_state[widget_key]
    st.session_state.selected_tournament = tournament_id
    for key in ("team_tournament", "match_tournament", "standing_tournament"):
        if key != widget_key:
            st.session_state[key] = tournament_id


def render_dashboard() -> None:
    tournaments = st.session_state.tournaments
    tournament = get_tournament()
    total_teams = sum(len(item["teams"]) for item in tournaments)
    total_done = sum(match_count_done(item) for item in tournaments)
    remaining = (
        sum(match["status"] != "done" for match in tournament["matches"])
        if tournament
        else 0
    )
    st.title("Visão geral")
    st.caption("Seu próximo campeonato está a uma jogada de distância.")
    st.button(
        "＋ Novo campeonato",
        type="primary",
        key="dashboard_new_tournament",
        on_click=navigate,
        args=("Campeonatos",),
    )

    champion = get_champion(tournament) if tournament else None
    headline = (
        f"{champion['name']} é a grande campeã!"
        if champion
        else f"A {tournament['name']} está rolando."
        if tournament
        else "Sua arena começa aqui."
    )
    detail = (
        f"Parabéns à equipe {champion['name']} pela vitória."
        if champion
        else f"{len(tournament['teams'])} equipes inscritas · {remaining} partidas aguardando."
        if tournament
        else "Crie seu primeiro campeonato, reúna equipes e deixe a disputa começar."
    )
    st.markdown(
        f'<div class="arena-hero"><small>GG ARENA · TEMPORADA EM ANDAMENTO</small>'
        f"<h2>{html.escape(headline)}</h2><p>{html.escape(detail)}</p></div>",
        unsafe_allow_html=True,
    )
    columns = st.columns(4)
    columns[0].metric("Campeonatos", len(tournaments))
    columns[1].metric("Equipes inscritas", total_teams)
    columns[2].metric("Partidas realizadas", total_done)
    columns[3].metric("Partidas restantes", remaining)
    left, right = st.columns([1.45, 1])
    with left:
        st.subheader("Próximas partidas")
        if not tournament or not tournament["matches"]:
            st.info("Adicione equipes e gere os confrontos.")
        else:
            upcoming = sorted(
                (match for match in tournament["matches"] if match["status"] != "done"),
                key=lambda match: (match["date"], match["time"]),
            )[:5]
            if not upcoming:
                st.success("Todas as partidas foram disputadas.")
            for match in upcoming:
                home = get_team(tournament, match["home_id"])
                away = get_team(tournament, match["away_id"])
                if home and away:
                    st.write(
                        f"**{format_match_date(match['date'])} · {match['time']}**  \n"
                        f"{home['name']}  **×**  {away['name']} · "
                        f"{round_label(tournament, match['round'])}"
                    )
        st.subheader("Classificação")
        if tournament:
            team_table(standings(tournament)[:5])
        else:
            st.info("Crie um campeonato para ver a tabela.")
    with right:
        st.subheader("Campeonato em destaque")
        if tournament:
            status = status_label(tournament)
            progress = (
                round(match_count_done(tournament) / len(tournament["matches"]) * 100)
                if tournament["matches"]
                else 0
            )
            st.markdown(f"### {tournament['name']}")
            st.write(f"🎮 {tournament['game']} · {status}")
            st.write(
                "Formato: "
                + ("Pontos corridos" if tournament["format"] == "league" else "Mata-mata")
            )
            st.progress(progress, text=f"Progresso da competição · {progress}%")
        else:
            st.info("Nenhum campeonato cadastrado.")
        st.subheader("Resultados recentes")
        if tournament:
            recent = sorted(
                (match for match in tournament["matches"] if match["status"] == "done"),
                key=lambda match: match["date"],
                reverse=True,
            )[:4]
            for match in recent:
                home = get_team(tournament, match["home_id"])
                away = get_team(tournament, match["away_id"])
                if home and away:
                    st.write(
                        f"{home['name']} **{match['home_score']} × "
                        f"{match['away_score']}** {away['name']}"
                    )
            if not recent:
                st.caption("Nenhum resultado registrado ainda.")


def render_tournaments() -> None:
    st.title("Campeonatos")
    st.caption("Crie competições e acompanhe cada temporada.")
    with st.expander("＋ Criar campeonato", expanded=not st.session_state.tournaments):
        with st.form("create_tournament", clear_on_submit=True):
            name = st.text_input("Nome do campeonato", max_chars=60)
            game = st.text_input("Jogo", max_chars=40, placeholder="Ex.: Valorant")
            format_label = st.selectbox("Formato", ["Pontos corridos", "Mata-mata"])
            start_date = st.date_input("Data de início", value=date.today())
            status_label_input = st.selectbox(
                "Status", ["Em andamento", "Inscrições abertas"]
            )
            submitted = st.form_submit_button("Criar campeonato", type="primary")
        if submitted:
            if not name.strip() or not game.strip():
                st.error("Informe o nome do campeonato e o jogo.")
            else:
                tournament = {
                    "id": new_id("tournament"),
                    "name": name.strip(),
                    "game": game.strip(),
                    "format": "league" if format_label == "Pontos corridos" else "knockout",
                    "start_date": start_date.isoformat(),
                    "status": "active" if status_label_input == "Em andamento" else "upcoming",
                    "teams": [],
                    "matches": [],
                    "bye_advances": {},
                }
                previous = list(st.session_state.tournaments)
                st.session_state.tournaments.insert(0, tournament)
                st.session_state.selected_tournament = tournament["id"]
                if persist():
                    st.success("Campeonato criado! Agora inscreva as equipes.")
                    st.rerun()
                st.session_state.tournaments = previous
    if not st.session_state.tournaments:
        st.info("Sua arena está vazia. Crie seu primeiro campeonato para começar.")
        return

    query = st.text_input("Buscar por campeonato ou jogo", key="tournament_search").casefold()
    status_filter = st.selectbox(
        "Filtrar por status",
        ["Todos", "Em andamento", "Inscrições abertas", "Finalizado"],
        key="tournament_filter",
    )
    for tournament in st.session_state.tournaments:
        if query and query not in f"{tournament['name']} {tournament['game']}".casefold():
            continue
        if status_filter != "Todos" and status_label(tournament) != status_filter:
            continue
        with st.container(border=True):
            details, actions = st.columns([4, 1])
            with details:
                st.markdown(f"### {tournament['name']}")
                st.write(
                    f"🎮 {tournament['game']} · "
                    f"{'Pontos corridos' if tournament['format'] == 'league' else 'Mata-mata'} · "
                    f"{len(tournament['teams'])} equipes · "
                    f"{match_count_done(tournament)}/{len(tournament['matches'])} partidas · "
                    f"{status_label(tournament)}"
                )
                st.caption(f"Início: {format_match_date(tournament['start_date'])}")
            with actions:
                st.button(
                    "Abrir",
                    key=f"open_{tournament['id']}",
                    on_click=navigate,
                    args=("Equipes", tournament["id"]),
                )
                if st.button("Excluir", key=f"delete_{tournament['id']}"):
                    previous = st.session_state.tournaments
                    st.session_state.tournaments = [
                        item for item in previous if item["id"] != tournament["id"]
                    ]
                    if st.session_state.selected_tournament == tournament["id"]:
                        st.session_state.selected_tournament = (
                            st.session_state.tournaments[0]["id"]
                            if st.session_state.tournaments
                            else ""
                        )
                    if persist():
                        st.rerun()
                    st.session_state.tournaments = previous

    st.divider()
    export_json = json.dumps(
        st.session_state.tournaments, ensure_ascii=False, indent=2
    ).encode("utf-8")
    st.download_button(
        "⇩ Exportar backup JSON",
        data=export_json,
        file_name=f"gg-arena-backup-{iso_day()}.json",
        mime="application/json",
    )
    uploaded_file = st.file_uploader("Importar backup JSON", type=["json"])
    if uploaded_file is not None and st.button("Restaurar backup", type="secondary"):
        try:
            imported = validate_data(json.loads(uploaded_file.getvalue()))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            st.error(f"Não foi possível importar o arquivo: {error}")
        else:
            previous = st.session_state.tournaments
            previous_selection = st.session_state.selected_tournament
            st.session_state.tournaments = imported
            st.session_state.selected_tournament = imported[0]["id"] if imported else ""
            if persist():
                st.success("Backup importado.")
                st.rerun()
            st.session_state.tournaments = previous
            st.session_state.selected_tournament = previous_selection


def selected_tournament_picker(key: str) -> dict[str, Any] | None:
    tournaments = st.session_state.tournaments
    if not tournaments:
        st.info("Crie um campeonato antes de continuar.")
        return None
    ids = [tournament["id"] for tournament in tournaments]
    current_id = st.session_state.selected_tournament
    default_index = ids.index(current_id) if current_id in ids else 0
    chosen_id = st.selectbox(
        "Campeonato",
        ids,
        index=default_index,
        format_func=lambda tournament_id: next(
            item["name"] for item in tournaments if item["id"] == tournament_id
        ),
        key=key,
        on_change=sync_selected_tournament,
        args=(key,),
    )
    st.session_state.selected_tournament = chosen_id
    return get_tournament(chosen_id)


def render_teams() -> None:
    st.title("Equipes")
    st.caption("Inscreva participantes e monte os elencos.")
    tournament = selected_tournament_picker("team_tournament")
    if not tournament:
        return
    with st.expander("＋ Adicionar equipe"):
        with st.form("create_team", clear_on_submit=True):
            name = st.text_input("Nome da equipe", max_chars=40)
            tag = st.text_input("Tag", max_chars=4, placeholder="Ex.: AG")
            color = st.color_picker(
                "Cor da equipe", value=COLORS[len(tournament["teams"]) % len(COLORS)]
            )
            players_text = st.text_input(
                "Jogadores (separe os nomes por vírgula)", max_chars=240
            )
            submitted = st.form_submit_button("Adicionar equipe", type="primary")
        if submitted:
            if not name.strip():
                st.error("Informe o nome da equipe.")
            elif any(
                team["name"].casefold() == name.strip().casefold()
                for team in tournament["teams"]
            ):
                st.error("Já existe uma equipe com esse nome neste campeonato.")
            elif any(match["status"] == "done" for match in tournament["matches"]):
                st.error("Não é possível adicionar equipes após o início da competição.")
            else:
                previous_teams = list(tournament["teams"])
                previous_matches = list(tournament["matches"])
                previous_byes = dict(tournament["bye_advances"])
                team = {
                    "id": new_id("team"),
                    "name": name.strip(),
                    "tag": tag.strip().upper()
                    or "".join(part[0] for part in name.split())[:3].upper(),
                    "color": color,
                    "players": [
                        player.strip()
                        for player in players_text.split(",")
                        if player.strip()
                    ],
                }
                tournament["teams"].append(team)
                if previous_matches:
                    generate_matches(tournament)
                if persist():
                    st.success(f"Equipe {team['name']} adicionada.")
                    st.rerun()
                tournament["teams"] = previous_teams
                tournament["matches"] = previous_matches
                tournament["bye_advances"] = previous_byes
    st.caption(f"{len(tournament['teams'])} equipe(s) inscrita(s)")
    if not tournament["teams"]:
        st.info("Adicione equipes para montar os confrontos.")
    columns = st.columns(3)
    for index, team in enumerate(tournament["teams"]):
        with columns[index % 3]:
            with st.container(border=True):
                st.markdown(
                    f'<span class="team-chip" style="background:{team["color"]};color:#fff">'
                    f'{team["tag"]}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{team['name']}**")
                st.caption(" · ".join(team["players"]) or "Elenco não informado")
                played = sum(
                    match["status"] == "done"
                    and team["id"] in (match["home_id"], match["away_id"])
                    for match in tournament["matches"]
                )
                st.caption(f"{played} partidas disputadas")
                if st.button("Remover equipe", key=f"remove_{team['id']}"):
                    if any(
                        match["status"] == "done"
                        and team["id"] in (match["home_id"], match["away_id"])
                        for match in tournament["matches"]
                    ):
                        st.error("Esta equipe já tem resultados; os dados foram preservados.")
                    else:
                        previous_teams = list(tournament["teams"])
                        previous_matches = list(tournament["matches"])
                        previous_byes = dict(tournament["bye_advances"])
                        tournament["teams"] = [
                            item for item in tournament["teams"] if item["id"] != team["id"]
                        ]
                        if previous_matches and len(tournament["teams"]) >= 2:
                            generate_matches(tournament)
                        else:
                            tournament["matches"] = []
                            tournament["bye_advances"] = {}
                        if persist():
                            st.rerun()
                        tournament["teams"] = previous_teams
                        tournament["matches"] = previous_matches
                        tournament["bye_advances"] = previous_byes


def render_matches() -> None:
    st.title("Partidas")
    st.caption("Agenda, resultados e histórico da competição.")
    tournament = selected_tournament_picker("match_tournament")
    if not tournament:
        return
    control, status_column = st.columns([1, 2])
    with control:
        if st.button("⚡ Gerar partidas", type="primary"):
            if len(tournament["teams"]) < 2:
                st.error("Adicione pelo menos 2 equipes antes de gerar partidas.")
            elif tournament["matches"]:
                st.warning("Gerar novamente substituirá as partidas e resultados existentes.")
                st.session_state.confirm_generate = tournament["id"]
            else:
                generate_matches(tournament)
                if persist():
                    st.success("Confrontos gerados!")
                    st.rerun()
    with status_column:
        if st.session_state.get("confirm_generate") == tournament["id"]:
            confirm, cancel = st.columns(2)
            with confirm:
                if st.button("Confirmar e substituir", type="primary"):
                    previous_matches = list(tournament["matches"])
                    previous_byes = dict(tournament["bye_advances"])
                    generate_matches(tournament)
                    if persist():
                        st.session_state.confirm_generate = ""
                        st.rerun()
                    tournament["matches"] = previous_matches
                    tournament["bye_advances"] = previous_byes
            with cancel:
                if st.button("Cancelar"):
                    st.session_state.confirm_generate = ""
                    st.rerun()

    if not tournament["matches"]:
        st.info("Ainda não há partidas. Adicione pelo menos duas equipes e gere os confrontos.")
        return
    status_filter = st.selectbox(
        "Mostrar partidas", ["Todas", "Agendadas", "Finalizadas"], key="match_filter"
    )
    query = st.text_input("Buscar equipe", key="match_search").casefold()
    matches = sorted(
        tournament["matches"], key=lambda match: (match["date"], match["round"], match["time"])
    )
    if status_filter != "Todas":
        wanted = "done" if status_filter == "Finalizadas" else "upcoming"
        matches = [match for match in matches if match["status"] == wanted]
    if query:
        matches = [
            match
            for match in matches
            if query
            in " ".join(
                (get_team(tournament, match[field]) or {}).get("name", "")
                for field in ("home_id", "away_id")
            ).casefold()
        ]
    if not matches:
        st.info("Nenhuma partida encontrada para esses filtros.")
    for match in matches:
        home = get_team(tournament, match["home_id"])
        away = get_team(tournament, match["away_id"])
        if not home or not away:
            continue
        with st.container(border=True):
            title, status_column = st.columns([4, 1])
            with title:
                score = (
                    f" · **{match['home_score']} × {match['away_score']}**"
                    if match["status"] == "done"
                    else ""
                )
                st.markdown(
                    f"**{home['name']} × {away['name']}**{score}  \n"
                    f"{round_label(tournament, match['round'])} · "
                    f"{format_match_date(match['date'])} · {match['time']}"
                )
            with status_column:
                st.caption("Finalizada" if match["status"] == "done" else "Agendada")
            locked = tournament["format"] == "knockout" and any(
                item["round"] > match["round"] for item in tournament["matches"]
            )
            if locked:
                st.caption("Resultado bloqueado: a próxima fase já começou.")
            with st.form(f"score_{match['id']}"):
                left, middle, right = st.columns([2, 1, 2])
                with left:
                    st.caption(home["name"])
                    home_score = st.number_input(
                        "Placar da equipe da casa",
                        min_value=0,
                        max_value=999,
                        value=int(match["home_score"] or 0),
                        key=f"home_score_{match['id']}",
                    )
                with middle:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("### ×")
                with right:
                    st.caption(away["name"])
                    away_score = st.number_input(
                        "Placar da equipe visitante",
                        min_value=0,
                        max_value=999,
                        value=int(match["away_score"] or 0),
                        key=f"away_score_{match['id']}",
                    )
                match_date = st.date_input(
                    "Data da partida",
                    value=date.fromisoformat(match["date"]),
                    key=f"match_date_{match['id']}",
                    disabled=locked,
                )
                submitted = st.form_submit_button(
                    "Salvar resultado" if match["status"] == "upcoming" else "Atualizar resultado",
                    disabled=locked,
                )
            if submitted:
                if tournament["format"] == "knockout" and home_score == away_score:
                    st.error("No mata-mata, informe um placar com uma equipe vencedora.")
                else:
                    previous_matches = [dict(item) for item in tournament["matches"]]
                    previous_byes = dict(tournament["bye_advances"])
                    was_done = match["status"] == "done"
                    match.update(
                        home_score=int(home_score),
                        away_score=int(away_score),
                        date=match_date.isoformat(),
                        status="done",
                    )
                    if tournament["format"] == "knockout" and not was_done:
                        advance_knockout(tournament, match["round"])
                    if persist():
                        st.success("Resultado salvo e classificação atualizada.")
                        st.rerun()
                    tournament["matches"] = previous_matches
                    tournament["bye_advances"] = previous_byes

    if tournament["format"] == "knockout":
        st.subheader("Chaveamento")
        rounds = sorted({match["round"] for match in tournament["matches"]})
        columns = st.columns(max(1, len(rounds)))
        for column, round_number in zip(columns, rounds):
            with column:
                st.markdown(f"**{round_label(tournament, round_number)}**")
                for match in (item for item in tournament["matches"] if item["round"] == round_number):
                    home = get_team(tournament, match["home_id"])
                    away = get_team(tournament, match["away_id"])
                    if home and away:
                        home_score = match["home_score"] if match["status"] == "done" else "—"
                        away_score = match["away_score"] if match["status"] == "done" else "—"
                        st.info(f"{home['name']}  **{home_score}**  \n{away['name']}  **{away_score}**")


def render_standings() -> None:
    st.title("Classificação")
    st.caption("Desempenho, pontuação e posição das equipes.")
    tournament = selected_tournament_picker("standing_tournament")
    if not tournament:
        return
    rows = standings(tournament)
    leader = rows[0] if rows else None
    metrics = st.columns(4)
    metrics[0].metric("Equipes", len(tournament["teams"]))
    metrics[1].metric("Partidas realizadas", match_count_done(tournament))
    metrics[2].metric("Líder", leader["team"]["tag"] if leader else "—")
    metrics[3].metric("Pontos do líder", leader["points"] if leader else 0)
    st.subheader(tournament["name"])
    st.caption("Pontos por vitória e desempate por saldo de gols e gols marcados.")
    team_table(rows)


page = render_sidebar()
if page == "Visão geral":
    render_dashboard()
elif page == "Campeonatos":
    render_tournaments()
elif page == "Equipes":
    render_teams()
elif page == "Partidas":
    render_matches()
else:
    render_standings()
