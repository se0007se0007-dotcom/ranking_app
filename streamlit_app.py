import base64
import io
import os
from datetime import date, datetime

import requests
import streamlit as st
import pandas as pd
from pandas.errors import EmptyDataError
import streamlit.components.v1 as components

st.set_page_config(page_title="JS 테니스 랭킹포인트", layout="wide")

# ✅ 올해 연도(자동)
THIS_YEAR = date.today().year

# ✅ 한글 입력 친화: 브라우저 자동변환/자동완성 차단 + IME 힌트
#    - MutationObserver로 selectbox 검색창처럼 "동적으로 생기는" 입력창에도 즉시 적용
#    - autocorrect/autocapitalize/autocomplete가 한글 입력을 영문으로 바꾸는 현상 방지
components.html(
    """
    <script>
      const doc = window.parent.document;
      doc.documentElement.setAttribute("lang", "ko");

      const fix = (el) => {
        if (el.dataset && el.dataset.koFixed === "1") return;
        el.setAttribute("lang", "ko");
        el.setAttribute("autocomplete", "off");
        el.setAttribute("autocorrect", "off");
        el.setAttribute("autocapitalize", "none");
        el.setAttribute("spellcheck", "false");
        el.setAttribute("inputmode", "text");
        if (el.dataset) el.dataset.koFixed = "1";
      };

      const applyAll = (root) => {
        if (!root || !root.querySelectorAll) return;
        root.querySelectorAll("input, textarea").forEach(fix);
      };

      applyAll(doc);

      // 동적으로 추가되는 입력창(드롭다운 검색창 등)에 즉시 적용
      const obs = new MutationObserver((muts) => {
        for (const m of muts) {
          for (const n of m.addedNodes) {
            if (n.nodeType !== 1) continue;
            if (n.matches && n.matches("input, textarea")) fix(n);
            applyAll(n);
          }
        }
      });
      obs.observe(doc.body, { childList: true, subtree: true });

      // 포커스 순간에도 한 번 더 보정 (일부 브라우저 대응)
      doc.addEventListener("focusin", (e) => {
        const t = e.target;
        if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) fix(t);
      }, true);

      // ✅ selectbox에서 이름 입력 후 Tab을 눌러도 값이 유지되도록:
      //    입력값이 있으면 Tab 시 Enter를 먼저 보내 하이라이트된(필터된) 항목을 확정
      doc.addEventListener("keydown", (e) => {
        if (e.key !== "Tab") return;
        const t = e.target;
        if (!t || t.tagName !== "INPUT") return;
        if (!t.closest || !t.closest('[data-baseweb="select"]')) return;
        if (!t.value || !t.value.trim()) return;  // 검색어 없으면 일반 Tab
        const enterEv = new KeyboardEvent("keydown", {
          key: "Enter", code: "Enter", keyCode: 13, which: 13,
          bubbles: true, cancelable: true
        });
        t.dispatchEvent(enterEv);
      }, true);

      // ✅ 영타 → 한글 자동 변환 (이름 선택창 전용, 두벌식 기준)
      //    한/영 전환을 잊고 영어 모드로 쳐도 자동으로 한글로 변환됨 (rla → 김)
      const ENG2JAMO = {
        r:"ㄱ",R:"ㄲ",s:"ㄴ",e:"ㄷ",E:"ㄸ",f:"ㄹ",a:"ㅁ",q:"ㅂ",Q:"ㅃ",t:"ㅅ",T:"ㅆ",
        d:"ㅇ",w:"ㅈ",W:"ㅉ",c:"ㅊ",z:"ㅋ",x:"ㅌ",v:"ㅍ",g:"ㅎ",
        k:"ㅏ",o:"ㅐ",i:"ㅑ",O:"ㅒ",j:"ㅓ",p:"ㅔ",u:"ㅕ",P:"ㅖ",
        h:"ㅗ",y:"ㅛ",n:"ㅜ",b:"ㅠ",m:"ㅡ",l:"ㅣ"
      };
      const CHO  = [..."ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"];
      const JUNG = [..."ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"];
      const JONGS = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ";
      const COMBINE_JUNG = {"ㅗㅏ":"ㅘ","ㅗㅐ":"ㅙ","ㅗㅣ":"ㅚ","ㅜㅓ":"ㅝ","ㅜㅔ":"ㅞ","ㅜㅣ":"ㅟ","ㅡㅣ":"ㅢ"};
      const COMBINE_JONG = {"ㄱㅅ":"ㄳ","ㄴㅈ":"ㄵ","ㄴㅎ":"ㄶ","ㄹㄱ":"ㄺ","ㄹㅁ":"ㄻ","ㄹㅂ":"ㄼ","ㄹㅅ":"ㄽ","ㄹㅌ":"ㄾ","ㄹㅍ":"ㄿ","ㄹㅎ":"ㅀ","ㅂㅅ":"ㅄ"};
      const SPLIT_JONG = {};
      for (const k in COMBINE_JONG) SPLIT_JONG[COMBINE_JONG[k]] = k;

      const isJung = (c) => JUNG.includes(c);
      const isCho = (c) => CHO.includes(c);
      const jongIdx = (c) => JONGS.indexOf(c);

      function decomposeStr(str) {
        const out = [];
        for (const ch of str) {
          const code = ch.charCodeAt(0);
          if (code >= 0xAC00 && code <= 0xD7A3) {
            const idx = code - 0xAC00;
            out.push(CHO[Math.floor(idx / 588)]);
            out.push(JUNG[Math.floor((idx % 588) / 28)]);
            const jo = idx % 28;
            if (jo) out.push(JONGS[jo]);
          } else if (ENG2JAMO[ch]) {
            out.push(ENG2JAMO[ch]);
          } else if (ENG2JAMO[ch.toLowerCase()]) {
            out.push(ENG2JAMO[ch.toLowerCase()]);
          } else {
            out.push(ch);
          }
        }
        return out;
      }

      function assembleJamos(jamos) {
        let res = "";
        let cho = null, jung = null, jong = null;
        const flush = () => {
          if (cho !== null && jung !== null) {
            const ji = jong ? jongIdx(jong) : 0;
            res += String.fromCharCode(0xAC00 + CHO.indexOf(cho) * 588 + JUNG.indexOf(jung) * 28 + ji);
          } else if (cho !== null) {
            res += cho;
          }
          cho = null; jung = null; jong = null;
        };
        for (const ch of jamos) {
          if (isJung(ch)) {
            if (cho !== null && jung === null) {
              jung = ch;
            } else if (cho !== null && jung !== null && jong === null) {
              const comb = COMBINE_JUNG[jung + ch];
              if (comb) { jung = comb; } else { flush(); res += ch; }
            } else if (jong !== null) {
              let moved;
              if (SPLIT_JONG[jong]) {
                const pair = SPLIT_JONG[jong];
                jong = pair[0]; moved = pair[1];
              } else {
                moved = jong; jong = null;
              }
              flush();
              cho = moved; jung = ch;
            } else {
              res += ch;
            }
          } else if (isCho(ch) || jongIdx(ch) > 0) {
            if (jung === null) {
              if (cho !== null) flush();
              if (isCho(ch)) { cho = ch; } else { res += ch; }
            } else if (jong === null) {
              if (jongIdx(ch) > 0) { jong = ch; } else { flush(); cho = ch; }
            } else {
              const comb = COMBINE_JONG[jong + ch];
              if (comb) { jong = comb; }
              else { flush(); if (isCho(ch)) { cho = ch; } else { res += ch; } }
            }
          } else {
            flush(); res += ch;
          }
        }
        flush();
        return res;
      }

      const nativeSetter = Object.getOwnPropertyDescriptor(
        doc.defaultView.HTMLInputElement.prototype, "value"
      ).set;

      doc.addEventListener("input", (e) => {
        const t = e.target;
        if (!t || t.tagName !== "INPUT") return;
        if (e.isComposing) return;  // 한글 IME 조합 중이면 건드리지 않음
        if (!t.closest || !t.closest('[data-baseweb="select"]')) return;
        const v = t.value;
        if (!v || !/[a-zA-Z]/.test(v)) return;
        const converted = assembleJamos(decomposeStr(v));
        if (converted === v) return;
        nativeSetter.call(t, converted);
        t.dispatchEvent(new Event("input", { bubbles: true }));
      }, true);
    </script>
    """,
    height=0,
)

# =========================
# 경로/폴더
# =========================
DATA_DIR = "."
PLAYERS_PATH = os.path.join(DATA_DIR, "players.csv")
MATCHES_PATH = os.path.join(DATA_DIR, "matches.csv")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
PROMO_LOG_PATH = os.path.join(DATA_DIR, "promotion_log.csv")
PROMO_STATE_PATH = os.path.join(DATA_DIR, "promo_state.csv")  # ✅ 추가: 승급/강등 상태 저장
SUMMARY_XLSX_PATH = os.path.join(DATA_DIR, "rank_summary.xlsx")  # ✅ 추가: 전체 요약 엑셀

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# =========================
# ✅ 저장소 추상화 (로컬 CSV ↔ GitHub)
#    - Streamlit Cloud 배포 시: Secrets의 [github] 설정으로 CSV를 GitHub에 저장(영구 보존)
#    - 로컬 PC 실행 시: 기존처럼 폴더의 CSV 파일 사용 (설정 없으면 자동으로 로컬 모드)
# =========================
def _github_cfg():
    try:
        cfg = st.secrets["github"]
        if cfg.get("token") and cfg.get("repo"):
            return cfg
    except Exception:
        pass
    return None

GH_CFG = _github_cfg()

def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GH_CFG['token']}",
        "Accept": "application/vnd.github+json",
    }

def _gh_url(filename: str) -> str:
    return f"https://api.github.com/repos/{GH_CFG['repo']}/contents/{filename}"

@st.cache_data(show_spinner=False, ttl=300)
def _gh_read_text(filename: str) -> str | None:
    r = requests.get(
        _gh_url(filename),
        headers=_gh_headers(),
        params={"ref": GH_CFG.get("branch", "main")},
        timeout=15,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return base64.b64decode(r.json()["content"]).decode("utf-8-sig")

def _gh_write_text(filename: str, text: str, message: str) -> None:
    branch = GH_CFG.get("branch", "main")
    r = requests.get(_gh_url(filename), headers=_gh_headers(), params={"ref": branch}, timeout=15)
    sha = r.json().get("sha") if r.status_code == 200 else None
    payload = {
        "message": message,
        "content": base64.b64encode(text.encode("utf-8")).decode(),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r2 = requests.put(_gh_url(filename), headers=_gh_headers(), json=payload, timeout=20)
    r2.raise_for_status()
    _gh_read_text.clear()  # 읽기 캐시 무효화

def storage_read_csv(filename: str) -> pd.DataFrame | None:
    """CSV 읽기: GitHub 설정이 있으면 GitHub에서, 없으면 로컬 파일에서. 없으면 None."""
    if GH_CFG:
        text = _gh_read_text(filename)
        if text is None or not text.strip():
            return None
        try:
            return pd.read_csv(io.StringIO(text))
        except EmptyDataError:
            return None
    p = os.path.join(DATA_DIR, filename)
    if not os.path.exists(p):
        return None
    try:
        df = pd.read_csv(p, encoding="utf-8-sig")
        return None if df.shape[1] == 0 else df
    except (EmptyDataError, FileNotFoundError):
        return None

def storage_write_csv(filename: str, df: pd.DataFrame) -> None:
    """CSV 저장: GitHub 설정이 있으면 GitHub에 커밋, 없으면 로컬 파일에 저장."""
    if GH_CFG:
        _gh_write_text(filename, df.to_csv(index=False), f"data: update {filename}")
    else:
        df.to_csv(os.path.join(DATA_DIR, filename), index=False, encoding="utf-8-sig")

# =========================
# ✅ (선택) 간단 비밀번호 보호
#    - Secrets에 app_password = "..." 를 넣으면 접속 시 비밀번호를 요구
# =========================
def _check_password() -> None:
    try:
        app_pw = st.secrets.get("app_password", None)
    except Exception:
        app_pw = None
    if not app_pw:
        return
    if st.session_state.get("_authed_ok"):
        return
    st.markdown("### 🔒 JS 테니스 랭킹")
    pw = st.text_input("비밀번호를 입력하세요", type="password", key="_app_pw")
    if pw == str(app_pw):
        st.session_state["_authed_ok"] = True
        st.rerun()
    elif pw:
        st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

_check_password()

# =========================
# 급수/점수 매핑
# =========================
GRADE_LADDER = [
    "9급","8급","7급","6급","5급","4급","3급","2급","1급",
    "1단","2단","3단","4단","5단","6단","7단","8단","9단"
]

def grade_to_points(g: str) -> int:
    g = str(g).strip()
    if g.endswith("급"):
        n = int(g[:-1])
        return 10 - n   # 1급=9 ... 9급=1
    if g.endswith("단"):
        n = int(g[:-1])
        return 9 + n    # 1단=10 ... 9단=18
    raise ValueError(f"급수 형식 오류: {g}")

# =========================
# 점수 상/하한
# =========================
WIN_MIN, WIN_MAX = 0.25, 3.0
LOSE_MIN_MAGNITUDE = 0.25   # 패자는 최소 -0.25
LOSE_MAX_MAGNITUDE = 2.5    # 패자는 최대 -2.5

def clamp_points(win_pt: float, lose_pt: float) -> tuple[float, float]:
    """
    승자: +0.25 ~ +3.0  (항상 +)
    패자: -2.5  ~ -0.25 (항상 -)
    """
    win_pt = max(WIN_MIN, min(WIN_MAX, float(win_pt)))
    win_pt = abs(win_pt)

    lose_pt = float(lose_pt)
    lose_pt = min(-LOSE_MIN_MAGNITUDE, lose_pt)
    lose_pt = max(-LOSE_MAX_MAGNITUDE, lose_pt)
    lose_pt = -abs(lose_pt)

    return round(win_pt, 2), round(lose_pt, 2)

def fmt2(x) -> str:
    """표시용: 항상 소수점 2자리"""
    try:
        return f"{float(x):.2f}"
    except Exception:
        return ""

def format_2dp_columns_for_display(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """표시 전용: 지정 컬럼을 무조건 소수점 2자리 문자열로 변환(Streamlit 6자리 표시 방지)"""
    if df is None or df.empty:
        return df
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).map(lambda v: f"{v:.2f}")
    return out

# =========================
# 점수 계산
# =========================
def compute_points(w1g, w2g, l1g, l2g, wg: int, lg: int):
    w_team = grade_to_points(w1g) + grade_to_points(w2g)
    l_team = grade_to_points(l1g) + grade_to_points(l2g)

    diff = abs(w_team - l_team)
    handicap = diff * 0.25

    # 기본 점수
    if w_team >= l_team:
        base_win = 1.5 - handicap
        base_lose = -1.0 + handicap
    else:
        base_win = 1.5 + handicap
        base_lose = -1.0 - handicap

    # 스코어 보너스(음수도 가능) - 기준 6-3(3게임차)=0
    margin = int(wg) - int(lg)
    score_bonus_win = (margin - 3) * 0.1
    score_bonus_lose = -score_bonus_win

    final_win = base_win + score_bonus_win
    final_lose = base_lose + score_bonus_lose

    final_win, final_lose = clamp_points(final_win, final_lose)

    return {
        "winner_team_points": int(w_team),
        "loser_team_points": int(l_team),
        "team_diff": int(diff),
        "base_win_pt": round(float(base_win), 2),
        "base_lose_pt": round(float(base_lose), 2),
        "score_bonus": round(float(score_bonus_win), 2),
        "final_win_pt": round(float(final_win), 2),
        "final_lose_pt": round(float(final_lose), 2),
    }

# =========================
# CSV 로드/세이브
# =========================
def load_players() -> pd.DataFrame:
    df = storage_read_csv("players.csv")
    if df is None:
        st.error("players.csv가 없습니다. players.csv를 먼저 만들어주세요.")
        st.stop()

    if "name" not in df.columns or "grade" not in df.columns:
        st.error("players.csv 컬럼은 name, grade가 필요합니다.")
        st.stop()

    df["name"] = df["name"].astype(str).str.strip()
    df["grade"] = df["grade"].astype(str).str.strip()
    df = df[df["name"] != ""].drop_duplicates(subset=["name"]).reset_index(drop=True)

    df.loc[~df["grade"].isin(GRADE_LADDER), "grade"] = "9급"
    return df

def save_players(df: pd.DataFrame):
    storage_write_csv("players.csv", df)

def load_matches() -> pd.DataFrame:
    cols = [
        "date","venue",
        "winner1","winner2","loser1","loser2",
        "winner_games","loser_games",
        "winner_team_points","loser_team_points","team_diff",
        "base_win_pt","base_lose_pt","score_bonus",
        "final_win_pt","final_lose_pt"
    ]
    df = storage_read_csv("matches.csv")
    if df is None:
        return pd.DataFrame(columns=cols)

    for c in cols:
        if c not in df.columns:
            df[c] = None

    # 점수 컬럼은 숫자로 (저장/집계용)
    for c in ["base_win_pt","base_lose_pt","score_bonus","final_win_pt","final_lose_pt"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).round(2)

    return df[cols]

def save_matches(df: pd.DataFrame):
    df2 = df.copy()
    for c in ["base_win_pt","base_lose_pt","score_bonus","final_win_pt","final_lose_pt"]:
        if c in df2.columns:
            df2[c] = pd.to_numeric(df2[c], errors="coerce").fillna(0).round(2)
    storage_write_csv("matches.csv", df2)

def append_promo_log(rows: list[dict]):
    if not rows:
        return
    log_df = pd.DataFrame(rows)
    old = storage_read_csv("promotion_log.csv")
    if old is not None:
        log_df = pd.concat([old, log_df], ignore_index=True)
    storage_write_csv("promotion_log.csv", log_df)

# =========================
# ✅ 승급/강등 상태(promo_state.csv)
# =========================
def load_promo_state() -> pd.DataFrame:
    cols = ["name", "rule_mode", "rule_window", "last_bucket"]
    df = storage_read_csv("promo_state.csv")
    if df is None:
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df["name"] = df["name"].astype(str).str.strip()
    df["rule_mode"] = df["rule_mode"].astype(str).str.strip()
    df["rule_window"] = df["rule_window"].astype(str).str.strip()
    df["last_bucket"] = pd.to_numeric(df["last_bucket"], errors="coerce").fillna(0).astype(int)
    return df[cols]

def save_promo_state(df: pd.DataFrame):
    storage_write_csv("promo_state.csv", df)

def points_to_bucket(metric: float, step: float) -> int:
    """
    점수 -> 10점(또는 step) 단위 버킷.
    0~9.99 => 0, 10~19.99 => 1, ...
    -0~-9.99 => 0, -10~-19.99 => -1, ...
    """
    step = float(step)
    if step <= 0:
        step = 10.0
    m = float(metric)
    if m >= 0:
        return int(m // step)
    return -int((-m) // step)

# =========================
# ✅ 전체 요약 엑셀 생성(rank_summary.xlsx)
# =========================
def build_and_save_summary(players_df: pd.DataFrame, matches_df: pd.DataFrame):
    # 선수 요약
    if matches_df is None or matches_df.empty:
        player_summary = players_df.copy()
        player_summary["matches"] = 0
        player_summary["wins"] = 0
        player_summary["losses"] = 0
        player_summary["winrate"] = 0.0
        player_summary["total_points"] = 0.0
        player_summary["last_date"] = ""
    else:
        dfm = normalize_date_col(matches_df)
        t = explode_player_rows(dfm)

        if t.empty:
            player_summary = players_df.copy()
            player_summary["matches"] = 0
            player_summary["wins"] = 0
            player_summary["losses"] = 0
            player_summary["winrate"] = 0.0
            player_summary["total_points"] = 0.0
            player_summary["last_date"] = ""
        else:
            agg = t.groupby("name", as_index=False).agg(
                matches=("name", "count"),
                total_points=("points", "sum"),
                wins=("win", "sum"),
                losses=("loss", "sum"),
                last_date=("date", "max"),
            )
            agg["winrate"] = (agg["wins"] / (agg["wins"] + agg["losses"])).fillna(0)
            agg["total_points"] = pd.to_numeric(agg["total_points"], errors="coerce").fillna(0).round(2)

            player_summary = players_df.merge(agg, on="name", how="left")
            for c in ["matches", "wins", "losses"]:
                player_summary[c] = pd.to_numeric(player_summary[c], errors="coerce").fillna(0).astype(int)
            player_summary["winrate"] = pd.to_numeric(player_summary["winrate"], errors="coerce").fillna(0).round(4)
            player_summary["total_points"] = pd.to_numeric(player_summary["total_points"], errors="coerce").fillna(0).round(2)
            player_summary["last_date"] = player_summary["last_date"].fillna("").astype(str)

    player_summary = player_summary.rename(columns={
        "name": "이름",
        "grade": "급수",
        "matches": "경기수",
        "wins": "승",
        "losses": "패",
        "winrate": "승률",
        "total_points": "누적승점",
        "last_date": "최근경기일",
    })
    player_summary["승률"] = (pd.to_numeric(player_summary["승률"], errors="coerce").fillna(0) * 100).round(1).astype(str) + "%"

    # 날짜별 요약(간단 관리용)
    if matches_df is None or matches_df.empty:
        daily_summary = pd.DataFrame(columns=["date", "venue", "games", "participants"])
    else:
        dfm = normalize_date_col(matches_df).copy()
        if dfm.empty:
            daily_summary = pd.DataFrame(columns=["date", "venue", "games", "participants"])
        else:
            def _participants_count(r):
                s = set()
                for k in ["winner1", "winner2", "loser1", "loser2"]:
                    v = r.get(k, "")
                    if isinstance(v, str) and v.strip():
                        s.add(v.strip())
                return len(s)

            dfm["participants"] = dfm.apply(_participants_count, axis=1)
            daily_summary = dfm.groupby(["date", "venue"], as_index=False).agg(
                games=("date", "count"),
                participants=("participants", "sum"),
            ).sort_values(["date", "venue"], ascending=[False, True])

    # 엑셀 저장
    try:
        with pd.ExcelWriter(SUMMARY_XLSX_PATH, engine="openpyxl") as writer:
            player_summary.to_excel(writer, sheet_name="PlayerSummary", index=False)
            daily_summary.to_excel(writer, sheet_name="DailySummary", index=False)
    except Exception as e:
        # 엑셀 저장 실패해도 앱은 계속 동작하도록
        st.warning(f"요약 엑셀 저장 실패: {e}")

# =========================
# 공통 집계
# =========================
def normalize_date_col(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    return df

def explode_player_rows(matches_df: pd.DataFrame) -> pd.DataFrame:
    if matches_df.empty:
        return pd.DataFrame(columns=["date","name","points","win","loss","venue"])
    rows = []
    for _, m in matches_df.iterrows():
        win_pt = float(m["final_win_pt"])
        lose_pt = float(m["final_lose_pt"])
        d = m["date"]
        v = m.get("venue", "")
        for p in [m["winner1"], m["winner2"]]:
            rows.append({"date": d, "name": p, "points": win_pt, "win": 1, "loss": 0, "venue": v})
        for p in [m["loser1"], m["loser2"]]:
            rows.append({"date": d, "name": p, "points": lose_pt, "win": 0, "loss": 1, "venue": v})
    return pd.DataFrame(rows)

def make_rankboard(players_df: pd.DataFrame, matches_df: pd.DataFrame) -> pd.DataFrame:
    grade_map_local = dict(zip(players_df["name"], players_df["grade"]))
    t = explode_player_rows(matches_df)

    if t.empty:
        out = players_df.copy()
        out["승점"] = 0.0
        out["승"] = 0
        out["패"] = 0
        out["승률"] = "0%"
        out = out.rename(columns={"name":"이름","grade":"급수"})[["이름","급수","승점","승","패","승률"]]
        out = out.sort_values("이름", ascending=False).reset_index(drop=True)
        out.insert(0, "Rank", range(1, len(out)+1))
        out["승점"] = out["승점"].astype(float).round(2)
        return out

    agg = t.groupby("name", as_index=False).agg(
        승점=("points","sum"),
        승=("win","sum"),
        패=("loss","sum"),
    )
    agg["승률"] = (agg["승"] / (agg["승"] + agg["패"])).fillna(0)
    agg["급수"] = agg["name"].map(grade_map_local)
    agg["승점"] = agg["승점"].astype(float).round(2)

    agg = agg.sort_values(["승점","승률","승"], ascending=[False, False, False]).reset_index(drop=True)
    agg.insert(0, "Rank", agg.index + 1)

    out = agg.rename(columns={"name":"이름"})[["Rank","이름","급수","승점","승","패","승률"]]
    out["승률"] = (out["승률"] * 100).round(0).astype(int).astype(str) + "%"
    return out

def quarter_of(d: date) -> int:
    return ((d.month - 1) // 3) + 1

def filter_by_quarter(matches_df: pd.DataFrame, year: int, q: int) -> pd.DataFrame:
    if matches_df.empty:
        return matches_df
    df = normalize_date_col(matches_df)
    return df[(pd.to_datetime(df["date"]).dt.year == year) & (pd.to_datetime(df["date"]).dt.quarter == q)].copy()

# =========================
# 랭킹 테이블 스타일
# =========================
def style_rankboard(df: pd.DataFrame):
    if df is None or df.empty:
        return df

    df2 = df.copy().reset_index(drop=True)

    def _row_color(row):
        try:
            r = int(row.get("Rank", 0))
        except Exception:
            r = 0

        if r == 1:
            bg = "background-color: #fff3b0;"
        elif r == 2:
            bg = "background-color: #cfe8ff;"
        elif r == 3:
            bg = "background-color: #ffd1e8;"
        else:
            bg = ""
        return [bg] * len(row)

    styler = df2.style.apply(_row_color, axis=1)

    bold_cols = []
    if "Rank" in df2.columns:
        bold_cols.append("Rank")
    if "승점" in df2.columns:
        bold_cols.append("승점")
    if bold_cols:
        styler = styler.set_properties(subset=bold_cols, **{"font-weight": "700"})

    try:
        styler = styler.hide(axis="index")
    except Exception:
        pass

    return styler

# =========================
# ✅ 랭킹보드 이미지 생성(서버 측 PNG 렌더링)
#    - 화면에 표시된 보드 데이터(전체 누적/특정 날짜)를 그대로 이미지로 생성
#    - 브라우저/iframe 의존 없음 → 옵션 변경 즉시 반영, 모바일에서도 다운로드 OK
# =========================
def _load_kr_font(size: int, bold: bool = False):
    """한글 지원 폰트 로드 (Windows 맑은고딕 우선, 없으면 대체 폰트)."""
    from PIL import ImageFont

    candidates = []
    if bold:
        candidates += [
            r"C:\Windows\Fonts\malgunbd.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        ]
    candidates += [
        r"C:\Windows\Fonts\malgun.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def board_to_png(board_disp: pd.DataFrame, title_text: str) -> tuple[bytes, int]:
    """랭킹보드 DataFrame을 PNG 바이트로 변환. (png_bytes, 표시용 너비) 반환."""
    from PIL import Image, ImageDraw

    scale = 2  # 고해상도(2배)
    f_title = _load_kr_font(20 * scale, bold=True)
    f_sub = _load_kr_font(12 * scale)
    f_head = _load_kr_font(13 * scale, bold=True)
    f_cell = _load_kr_font(13 * scale)

    cols = [str(c) for c in board_disp.columns]
    rows = [["" if v is None else str(v) for v in row] for row in board_disp.values]

    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    pad_x = 14 * scale
    col_w = []
    for j, c in enumerate(cols):
        w = tmp.textlength(c, font=f_head)
        for r in rows:
            w = max(w, tmp.textlength(r[j], font=f_cell))
        col_w.append(int(w) + pad_x * 2)

    row_h = 34 * scale
    head_h = 38 * scale
    margin = 24 * scale
    title_h = 34 * scale
    sub_h = 26 * scale

    table_w = sum(col_w)
    W = table_w + margin * 2
    H = margin + title_h + sub_h + 8 * scale + head_h + row_h * len(rows) + margin

    img = Image.new("RGB", (W, H), "#ffffff")
    draw = ImageDraw.Draw(img)

    # 제목/부제
    draw.text((margin, margin), "JS 테니스 랭킹 포인트", font=f_title, fill="#111111")
    sub = f"{title_text} · 생성일 {date.today().strftime('%Y-%m-%d')}"
    draw.text((margin, margin + title_h + 2 * scale), sub, font=f_sub, fill="#555555")

    top = margin + title_h + sub_h + 8 * scale
    rank_colors = {1: "#fff3b0", 2: "#cfe8ff", 3: "#ffd1e8"}
    rank_idx = cols.index("Rank") if "Rank" in cols else None

    # 헤더
    x = margin
    for j, c in enumerate(cols):
        draw.rectangle([x, top, x + col_w[j], top + head_h], fill="#222222", outline="#d1d5db")
        draw.text((x + col_w[j] / 2, top + head_h / 2), c, font=f_head, fill="#ffffff", anchor="mm")
        x += col_w[j]

    # 본문(1~3위 색상 강조)
    y = top + head_h
    for r in rows:
        rank_val = None
        if rank_idx is not None:
            try:
                rank_val = int(float(r[rank_idx]))
            except Exception:
                rank_val = None
        bg = rank_colors.get(rank_val, "#ffffff")
        x = margin
        for j, v in enumerate(r):
            draw.rectangle([x, y, x + col_w[j], y + row_h], fill=bg, outline="#d1d5db")
            draw.text((x + col_w[j] / 2, y + row_h / 2), v, font=f_cell, fill="#111111", anchor="mm")
            x += col_w[j]
        y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), W // scale

# =========================
# 자동 승급/강등 (✅ 버킷 기반 + 상태 저장)
# =========================
def apply_auto_promo_demotion(
    players_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    mode: str,
    min_matches: int,
    promote_threshold: float,
    demote_threshold: float,
    window: str
) -> tuple[pd.DataFrame, list[dict]]:
    if matches_df.empty or players_df.empty:
        return players_df, []

    dfm = normalize_date_col(matches_df)
    today = date.today()

    if window == "최근 30일":
        start = today.fromordinal(today.toordinal() - 30)
        dfm = dfm[dfm["date"] >= start]
    elif window == "최근 90일":
        start = today.fromordinal(today.toordinal() - 90)
        dfm = dfm[dfm["date"] >= start]
    elif window == "올해":
        dfm = dfm[pd.to_datetime(dfm["date"]).dt.year == today.year]
    elif window == "이번 분기":
        dfm = dfm[(pd.to_datetime(dfm["date"]).dt.year == today.year) &
                  (pd.to_datetime(dfm["date"]).dt.quarter == quarter_of(today))]

    t = explode_player_rows(dfm)
    if t.empty:
        return players_df, []

    stats = t.groupby("name", as_index=False).agg(
        matches=("name","count"),
        points=("points","sum"),
        win=("win","sum"),
        loss=("loss","sum"),
    )
    stats["winrate"] = (stats["win"] / (stats["win"] + stats["loss"])).fillna(0)

    ladder_index = {g: i for i, g in enumerate(GRADE_LADDER)}
    name_to_grade = dict(zip(players_df["name"], players_df["grade"]))

    promo_logs = []
    updated = players_df.copy()

    # ✅ 상태 로드
    promo_state = load_promo_state()
    state_map = {}
    if not promo_state.empty:
        for _, s in promo_state.iterrows():
            state_map[(s["name"], s["rule_mode"], s["rule_window"])] = int(s["last_bucket"])

    state_updates = []

    for _, r in stats.iterrows():
        name = r["name"]
        if name not in name_to_grade:
            continue
        if int(r["matches"]) < int(min_matches):
            continue

        cur_grade = name_to_grade[name]
        if cur_grade not in ladder_index:
            continue
        cur_i = ladder_index[cur_grade]

        metric = float(r["points"]) if mode == "점수" else float(r["winrate"])

        # ====== ✅ 점수 모드: 10점(=promote_threshold 절대값) 단위 버킷 변화량만큼 이동 ======
        if mode == "점수":
            step = float(abs(promote_threshold)) if float(abs(promote_threshold)) > 0 else 10.0
            bucket = points_to_bucket(metric, step)
            last_bucket = state_map.get((name, mode, window), 0)
            delta = int(bucket - last_bucket)

            if delta == 0:
                continue

            new_i = max(0, min(len(GRADE_LADDER) - 1, cur_i + delta))
            if new_i == cur_i:
                # 급수 상/하한에 걸려 이동은 못해도 상태는 최신으로 저장 (무한 반복 방지)
                state_updates.append({"name": name, "rule_mode": mode, "rule_window": window, "last_bucket": bucket})
                continue

            new_grade = GRADE_LADDER[new_i]
            updated.loc[updated["name"] == name, "grade"] = new_grade

            promo_logs.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": name,
                "from_grade": cur_grade,
                "to_grade": new_grade,
                "rule_mode": mode,
                "rule_window": window,
                "min_matches": int(min_matches),
                "metric_value": round(metric, 4),
                "promote_threshold": promote_threshold,
                "demote_threshold": demote_threshold,
                "bucket": bucket,
                "last_bucket": last_bucket,
                "delta_bucket": delta,
            })

            state_updates.append({"name": name, "rule_mode": mode, "rule_window": window, "last_bucket": bucket})
            continue

        # ====== 승률 모드: 기존대로 1단계만 ======
        move = 0
        if metric >= promote_threshold:
            move = +1
        elif metric <= demote_threshold:
            move = -1

        if move == 0:
            continue

        new_i = max(0, min(len(GRADE_LADDER) - 1, cur_i + move))
        if new_i == cur_i:
            continue

        new_grade = GRADE_LADDER[new_i]
        updated.loc[updated["name"] == name, "grade"] = new_grade

        promo_logs.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": name,
            "from_grade": cur_grade,
            "to_grade": new_grade,
            "rule_mode": mode,
            "rule_window": window,
            "min_matches": int(min_matches),
            "metric_value": round(metric, 4),
            "promote_threshold": promote_threshold,
            "demote_threshold": demote_threshold,
        })

    # ✅ 상태 저장(merge upsert)
    if state_updates:
        upd_df = pd.DataFrame(state_updates)
        if promo_state.empty:
            promo_state = upd_df
        else:
            promo_state = promo_state.merge(
                upd_df,
                on=["name", "rule_mode", "rule_window"],
                how="outer",
                suffixes=("", "_new")
            )
            promo_state["last_bucket"] = promo_state["last_bucket_new"].fillna(promo_state["last_bucket"]).astype(int)
            promo_state = promo_state.drop(columns=["last_bucket_new"], errors="ignore")

        save_promo_state(promo_state)

    return updated, promo_logs

# =========================
# UI: 사이드바 설정
# =========================
st.sidebar.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
      <span style="color:#2F6BFF; font-weight:800; font-size:18px;">{THIS_YEAR}년</span>
      <span style="
        background:#222; color:#fff; font-weight:700; font-size:12px;
        padding:3px 8px; border-radius:999px; line-height:1;">
        시즌
      </span>
    </div>
    <h2 style="margin:0 0 0.2rem 0;">
      <span style="color:#FFD400;">JS</span>
      <span> 테니스 </span>
      <span style="color:#FF3333;">랭킹</span>
      <span> 포인트</span>
    </h2>
    """,
    unsafe_allow_html=True
)
st.sidebar.caption("설정 / 규칙")

auto_grade_enabled = st.sidebar.toggle("급수 자동 승급/강등 사용", value=True)

st.sidebar.subheader("급수 자동 승급/강등 규칙")
promo_mode = st.sidebar.radio("기준", ["점수", "승률"], horizontal=True)

promo_window = st.sidebar.selectbox(
    "적용 범위",
    ["전체 누적", "최근 30일", "최근 90일", "올해", "이번 분기"],
    index=0,
)

min_matches = st.sidebar.number_input("최소 경기 수", min_value=1, max_value=50, value=6, step=1)

if promo_mode == "점수":
    promote_threshold = st.sidebar.number_input("승급 기준(버킷 step: 누적 승점 10점 단위)", value=10.0, step=0.5)
    demote_threshold = st.sidebar.number_input("강등 기준(표시용)", value=-10.0, step=0.5)
else:
    promote_threshold = st.sidebar.number_input("승급 기준(승률 ≥)", value=0.70, step=0.05)
    demote_threshold = st.sidebar.number_input("강등 기준(승률 ≤)", value=0.30, step=0.05)

st.sidebar.caption(f"점수 상/하한: 승자 {WIN_MIN}~{WIN_MAX}, 패자 -{LOSE_MIN_MAGNITUDE}~-{LOSE_MAX_MAGNITUDE}")

# =========================
# 데이터 로드
# =========================
players_df = load_players()
matches_df = normalize_date_col(load_matches())

# ✅ 앱 실행 시 1회 자동 승급/강등 즉시 적용
if auto_grade_enabled and ("_auto_grade_bootstrap_done" not in st.session_state):
    st.session_state["_auto_grade_bootstrap_done"] = True
    if not matches_df.empty:
        updated_players, promo_logs = apply_auto_promo_demotion(
            players_df=players_df,
            matches_df=matches_df,
            mode=promo_mode,
            min_matches=min_matches,
            promote_threshold=float(promote_threshold),
            demote_threshold=float(demote_threshold),
            window=promo_window
        )
        if promo_logs:
            save_players(updated_players)
            append_promo_log(promo_logs)
            players_df = updated_players

# ✅ 부팅 시 요약 엑셀도 한번 생성(있으면 갱신)
build_and_save_summary(players_df=players_df, matches_df=matches_df)

# 이름 내림차순 + 빈칸
names = sorted(players_df["name"].tolist(), reverse=True)
names_with_blank = [""] + names
grade_map = dict(zip(players_df["name"], players_df["grade"]))

# =========================
# 오늘 경기 입력: ✅ data_editor 제거 / row별 위젯 key-in
# =========================
def _new_row_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")

def init_today_state():
    if "today_row_ids" not in st.session_state:
        st.session_state["today_row_ids"] = [_new_row_id(), _new_row_id(), _new_row_id()]
    if "today_date" not in st.session_state:
        st.session_state["today_date"] = date.today()
    if "today_venue" not in st.session_state:
        st.session_state["today_venue"] = ""

def add_today_row():
    st.session_state["today_row_ids"].append(_new_row_id())

def remove_today_row():
    if len(st.session_state["today_row_ids"]) <= 1:
        return
    rid = st.session_state["today_row_ids"].pop()
    for suffix in ["w1","w2","l1","l2","wg","lg"]:
        k = f"today_{rid}_{suffix}"
        if k in st.session_state:
            del st.session_state[k]

def _selectbox_with_value(label, options, value, key):
    """streamlit selectbox는 value 직접 지정이 아니라 index라서 helper로 처리"""
    if value in options:
        idx = options.index(value)
    else:
        idx = 0
    return st.selectbox(label, options=options, index=idx, key=key)

def get_today_rows_from_state():
    rows = []
    for rid in st.session_state["today_row_ids"]:
        w1 = st.session_state.get(f"today_{rid}_w1", "")
        w2 = st.session_state.get(f"today_{rid}_w2", "")
        l1 = st.session_state.get(f"today_{rid}_l1", "")
        l2 = st.session_state.get(f"today_{rid}_l2", "")
        wg = int(st.session_state.get(f"today_{rid}_wg", 6))
        lg = int(st.session_state.get(f"today_{rid}_lg", 3))
        rows.append((rid, {"승리1": w1, "승리2": w2, "패배1": l1, "패배2": l2, "승리게임": wg, "패배게임": lg}))
    return rows

init_today_state()

# =========================
# 헤더/탭
# =========================
st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:2px;">
      <span style="color:#2F6BFF; font-weight:900; font-size:34px;">{THIS_YEAR}년</span>
      <span style="
        background:#222; color:#fff; font-weight:800; font-size:14px;
        padding:6px 12px; border-radius:999px; line-height:1;">
        시즌
      </span>
    </div>
    <h1 style="margin-top:0; margin-bottom: 0.2rem;">
      <span style="color:#FFD400;">JS</span>
      <span> 테니스 </span>
      <span style="color:#FF3333;">랭킹</span>
      <span> 포인트 입력 &amp; 합산</span>
    </h1>
    """,
    unsafe_allow_html=True
)

tabs = st.tabs([
    "오늘 경기 입력",
    "모바일 전용 입력",
    "누적 랭킹보드",
    "파트너/궁합 통계",
    "분기 스냅샷",
    "원본 데이터 & 선수 관리"
])

# =========================
# 탭 1: 오늘 경기 입력
# =========================
with tabs[0]:
    st.subheader("오늘 경기 입력 (안정 입력 모드)")

    colA, colB, colC, colD = st.columns([1, 1, 1, 2])
    with colA:
        st.session_state["today_date"] = st.date_input("날짜", value=st.session_state["today_date"], key="today_date_input")
    with colB:
        st.session_state["today_venue"] = st.text_input("장소/모임(선택)", value=st.session_state["today_venue"], key="today_venue_input")
    with colC:
        b1, b2 = st.columns(2)
        with b1:
            if st.button("➕ 1게임 추가", key="btn_add_today"):
                add_today_row()
                st.rerun()
        with b2:
            if st.button("➖ 마지막 게임 삭제", key="btn_del_today"):
                remove_today_row()
                st.rerun()
    with colD:
        st.caption("✅ 이 화면은 data_editor 대신 row별 위젯 key로 입력을 고정합니다. (입력 튐/사라짐 방지)")

    st.markdown("---")

    h = st.columns([0.6, 2, 2, 1.2, 2, 2, 1.2])
    h[0].markdown("**No**")
    h[1].markdown("**승리1**")
    h[2].markdown("**승리2**")
    h[3].markdown("**승리게임**")
    h[4].markdown("**패배1**")
    h[5].markdown("**패배2**")
    h[6].markdown("**패배게임**")

    for idx, rid in enumerate(st.session_state["today_row_ids"], start=1):
        row = st.columns([0.6, 2, 2, 1.2, 2, 2, 1.2])
        row[0].write(idx)

        cur_w1 = st.session_state.get(f"today_{rid}_w1", "")
        cur_w2 = st.session_state.get(f"today_{rid}_w2", "")
        cur_l1 = st.session_state.get(f"today_{rid}_l1", "")
        cur_l2 = st.session_state.get(f"today_{rid}_l2", "")
        cur_wg = int(st.session_state.get(f"today_{rid}_wg", 6))
        cur_lg = int(st.session_state.get(f"today_{rid}_lg", 3))

        with row[1]:
            _selectbox_with_value(" ", names_with_blank, cur_w1, key=f"today_{rid}_w1")
        with row[2]:
            _selectbox_with_value("  ", names_with_blank, cur_w2, key=f"today_{rid}_w2")
        with row[3]:
            st.number_input("   ", min_value=0, max_value=9, step=1, value=cur_wg, key=f"today_{rid}_wg")
        with row[4]:
            _selectbox_with_value("    ", names_with_blank, cur_l1, key=f"today_{rid}_l1")
        with row[5]:
            _selectbox_with_value("     ", names_with_blank, cur_l2, key=f"today_{rid}_l2")
        with row[6]:
            st.number_input("      ", min_value=0, max_value=9, step=1, value=cur_lg, key=f"today_{rid}_lg")

    rows = get_today_rows_from_state()

    preview_rows, errors = [], []
    for i, (_, r) in enumerate(rows, start=1):
        w1, w2 = str(r["승리1"]).strip(), str(r["승리2"]).strip()
        l1, l2 = str(r["패배1"]).strip(), str(r["패배2"]).strip()
        wg, lg = int(r["승리게임"]), int(r["패배게임"])

        if not (w1 and w2 and l1 and l2):
            continue

        if w1 not in grade_map or w2 not in grade_map or l1 not in grade_map or l2 not in grade_map:
            errors.append(f"{i}번째: 선수 목록에 없는 이름이 포함되어 있습니다.")
            continue
        if w1 == w2 or l1 == l2:
            errors.append(f"{i}번째: 같은 팀 중복 선택")
            continue
        if {w1, w2} & {l1, l2}:
            errors.append(f"{i}번째: 한 사람이 양 팀에 포함")
            continue
        if wg <= lg:
            errors.append(f"{i}번째: 승리게임 수가 더 커야 함")
            continue

        res = compute_points(grade_map[w1], grade_map[w2], grade_map[l1], grade_map[l2], wg, lg)
        preview_rows.append({
            "게임": i,
            "승리팀": f"{w1} / {w2}",
            "패배팀": f"{l1} / {l2}",
            "스코어": f"{wg}-{lg}",
            "승점(각자)": fmt2(res["final_win_pt"]),
            "패점(각자)": fmt2(res["final_lose_pt"]),
            "팀급수합(승/패)": f"{res['winner_team_points']} / {res['loser_team_points']}",
            "급수차": res["team_diff"],
            "스코어보너스(승자기준)": fmt2(res["score_bonus"]),
        })

    st.markdown("#### 계산 미리보기 (소수점 2자리 고정)")
    if errors:
        st.warning("\n".join(errors))
    st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

    if st.button("이 경기들을 저장(누적 반영)", type="primary", key="btn_save_today"):
        new_rows = []
        for (_, r) in rows:
            w1, w2 = str(r["승리1"]).strip(), str(r["승리2"]).strip()
            l1, l2 = str(r["패배1"]).strip(), str(r["패배2"]).strip()
            wg, lg = int(r["승리게임"]), int(r["패배게임"])

            if not (w1 and w2 and l1 and l2):
                continue
            if w1 not in grade_map or w2 not in grade_map or l1 not in grade_map or l2 not in grade_map:
                continue
            if w1 == w2 or l1 == l2:
                continue
            if {w1, w2} & {l1, l2}:
                continue
            if wg <= lg:
                continue

            res = compute_points(grade_map[w1], grade_map[w2], grade_map[l1], grade_map[l2], wg, lg)
            new_rows.append({
                "date": str(st.session_state["today_date"]),
                "venue": st.session_state["today_venue"],
                "winner1": w1, "winner2": w2,
                "loser1": l1, "loser2": l2,
                "winner_games": wg, "loser_games": lg,
                **res
            })

        if not new_rows:
            st.error("저장할 유효한 경기 데이터가 없습니다. (빈칸/오류 입력 확인)")
        else:
            new_df = pd.DataFrame(new_rows)
            all_df = pd.concat([matches_df, new_df], ignore_index=True) if not matches_df.empty else new_df
            all_df = normalize_date_col(all_df)
            save_matches(all_df)

            if auto_grade_enabled:
                updated_players, promo_logs = apply_auto_promo_demotion(
                    players_df=players_df,
                    matches_df=all_df,
                    mode=promo_mode,
                    min_matches=min_matches,
                    promote_threshold=float(promote_threshold),
                    demote_threshold=float(demote_threshold),
                    window=promo_window
                )
                if promo_logs:
                    save_players(updated_players)
                    append_promo_log(promo_logs)
                    players_df = updated_players

            # ✅ 요약 엑셀 갱신
            build_and_save_summary(players_df=load_players(), matches_df=all_df)

            st.success(f"{len(new_df)}게임 저장 완료! (누적 {len(all_df)}게임)")
            st.cache_data.clear()
            st.rerun()

# =========================
# 탭 2: 모바일 전용 입력
# =========================
with tabs[1]:
    st.subheader("모바일 전용 입력 (한 게임씩 빠르게)")

    # ✅ 직전 저장 성공 메시지 표시 (저장 후 rerun 되어도 유지)
    _saved_msg = st.session_state.pop("mobile_saved_msg", None)
    if _saved_msg:
        st.success(_saved_msg)

    with st.form("mobile_form", clear_on_submit=False):
        mcol1, mcol2 = st.columns([1, 1])
        with mcol1:
            m_date = st.date_input("날짜", value=date.today(), key="m_date")
        with mcol2:
            m_venue = st.text_input("장소/모임(선택)", value="", key="m_venue")

        st.markdown("### 승리팀")
        wcol1, wcol2 = st.columns(2)
        with wcol1:
            mw1 = st.selectbox("승리 1", options=names_with_blank, index=0, key="mw1")
        with wcol2:
            mw2 = st.selectbox("승리 2", options=names_with_blank, index=0, key="mw2")

        st.markdown("### 패배팀")
        lcol1, lcol2 = st.columns(2)
        with lcol1:
            ml1 = st.selectbox("패배 1", options=names_with_blank, index=0, key="ml1")
        with lcol2:
            ml2 = st.selectbox("패배 2", options=names_with_blank, index=0, key="ml2")

        scol1, scol2 = st.columns(2)
        with scol1:
            mwg = st.number_input("승리 게임", min_value=0, max_value=9, value=6, step=1, key="mwg")
        with scol2:
            mlg = st.number_input("패배 게임", min_value=0, max_value=9, value=3, step=1, key="mlg")

        submitted = st.form_submit_button("계산하고 바로 저장", type="primary")

    if submitted:
        problems = []
        if not (mw1 and mw2 and ml1 and ml2):
            problems.append("승/패 팀 이름을 모두 선택해주세요.")
        if mw1 and mw2 and mw1 == mw2:
            problems.append("승리팀에 같은 사람이 중복되었습니다.")
        if ml1 and ml2 and ml1 == ml2:
            problems.append("패배팀에 같은 사람이 중복되었습니다.")
        if {mw1, mw2} & {ml1, ml2}:
            problems.append("한 사람이 양 팀에 동시에 포함되었습니다.")
        if int(mwg) <= int(mlg):
            problems.append("승리 게임 수가 패배 게임 수보다 커야 합니다.")
        if any((p not in grade_map) for p in [mw1, mw2, ml1, ml2]):
            problems.append("선수 목록에 없는 이름이 있습니다.")

        if problems:
            st.error("\n".join(problems))
        else:
            # ✅ 제출 즉시 계산+저장 (기존의 '이 내용으로 저장' 중첩 버튼은
            #    rerun 시 폼 제출 상태가 초기화되어 절대 실행되지 않는 버그였음)
            res = compute_points(grade_map[mw1], grade_map[mw2], grade_map[ml1], grade_map[ml2], int(mwg), int(mlg))
            row = {
                "date": str(m_date),
                "venue": m_venue,
                "winner1": mw1, "winner2": mw2,
                "loser1": ml1, "loser2": ml2,
                "winner_games": int(mwg), "loser_games": int(mlg),
                **res
            }
            new_df = pd.DataFrame([row])
            all_df = pd.concat([matches_df, new_df], ignore_index=True) if not matches_df.empty else new_df
            all_df = normalize_date_col(all_df)
            save_matches(all_df)

            if auto_grade_enabled:
                updated_players, promo_logs = apply_auto_promo_demotion(
                    players_df=players_df,
                    matches_df=all_df,
                    mode=promo_mode,
                    min_matches=min_matches,
                    promote_threshold=float(promote_threshold),
                    demote_threshold=float(demote_threshold),
                    window=promo_window
                )
                if promo_logs:
                    save_players(updated_players)
                    append_promo_log(promo_logs)
                    players_df = updated_players

            # ✅ 요약 엑셀 갱신
            build_and_save_summary(players_df=load_players(), matches_df=all_df)

            st.session_state["mobile_saved_msg"] = (
                f"✅ 저장 완료! {mw1}/{mw2} 승 ({int(mwg)}-{int(mlg)}) — "
                f"승점(각자): {fmt2(res['final_win_pt'])} / 패점(각자): {fmt2(res['final_lose_pt'])} "
                f"(누적 {len(all_df)}게임)"
            )
            st.cache_data.clear()
            st.rerun()

# =========================
# 탭 3: 누적 랭킹보드
# =========================
with tabs[2]:
    st.subheader("누적 랭킹보드")

    if matches_df.empty:
        st.info("아직 저장된 경기가 없습니다.")
    else:
        df = matches_df.copy()
        all_dates = sorted(df["date"].dropna().unique())

        col1, col2 = st.columns([1, 2])
        with col1:
            mode = st.radio("표시 기준", ["전체 누적", "특정 날짜만(오늘 승패점)"], horizontal=True)
        with col2:
            selected_date = st.selectbox(
                "날짜 선택",
                options=all_dates,
                index=len(all_dates)-1,
                disabled=(mode == "전체 누적")
            )

        full_board = make_rankboard(players_df, df)

        day_df = df[df["date"] == selected_date].copy()

        day_participants = set()
        if not day_df.empty:
            for _, m in day_df.iterrows():
                for p in [m["winner1"], m["winner2"], m["loser1"], m["loser2"]]:
                    if isinstance(p, str) and p.strip():
                        day_participants.add(p.strip())

        day_rows = []
        for _, m in day_df.iterrows():
            win_pt = float(m["final_win_pt"])
            lose_pt = float(m["final_lose_pt"])

            for p in [m["winner1"], m["winner2"]]:
                day_rows.append({"name": p, "day_points": win_pt, "day_win": 1, "day_loss": 0})
            for p in [m["loser1"], m["loser2"]]:
                day_rows.append({"name": p, "day_points": lose_pt, "day_win": 0, "day_loss": 1})

        if day_rows:
            day_stats = (
                pd.DataFrame(day_rows)
                .groupby("name", as_index=False)
                .agg(
                    day_points=("day_points", "sum"),
                    day_win=("day_win", "sum"),
                    day_loss=("day_loss", "sum"),
                )
            )
        else:
            day_stats = pd.DataFrame(columns=["name","day_points","day_win","day_loss"])

        if not day_stats.empty:
            day_stats["day_points"] = pd.to_numeric(day_stats["day_points"], errors="coerce").fillna(0).round(2)
            day_stats["day_win"] = pd.to_numeric(day_stats["day_win"], errors="coerce").fillna(0).astype(int)
            day_stats["day_loss"] = pd.to_numeric(day_stats["day_loss"], errors="coerce").fillna(0).astype(int)

        day_points_map = dict(zip(day_stats["name"], day_stats["day_points"]))
        day_win_map = dict(zip(day_stats["name"], day_stats["day_win"]))
        day_loss_map = dict(zip(day_stats["name"], day_stats["day_loss"]))

        board = full_board.copy()
        board["오늘 승패점"] = board["이름"].map(day_points_map).fillna(0.0)
        board["오늘 승패점"] = pd.to_numeric(board["오늘 승패점"], errors="coerce").fillna(0).round(2)
        board["승점"] = pd.to_numeric(board["승점"], errors="coerce").fillna(0).round(2)

        if mode == "특정 날짜만(오늘 승패점)":
            board["승"] = board["이름"].map(day_win_map).fillna(0).astype(int)
            board["패"] = board["이름"].map(day_loss_map).fillna(0).astype(int)

            denom = (board["승"] + board["패"]).replace(0, pd.NA)
            board["승률"] = (board["승"] / denom).fillna(0)
            board["승률"] = (board["승률"] * 100).round(0).astype(int).astype(str) + "%"

            if day_participants:
                board = board[board["이름"].isin(day_participants)].copy()
            else:
                board = board.iloc[0:0].copy()

            board = board.sort_values(["오늘 승패점", "승"], ascending=[False, False]).reset_index(drop=True)
            if "Rank" in board.columns:
                board = board.drop(columns=["Rank"])
            board.insert(0, "Rank", board.index + 1)

        board_display = format_2dp_columns_for_display(board, ["승점", "오늘 승패점"])
        st.dataframe(style_rankboard(board_display), use_container_width=True)

        # ✅ 랭킹보드 이미지 저장 (표시 기준 그대로 PNG 생성 → 다른 곳에 업로드용)
        st.markdown("---")
        st.markdown("#### 📸 랭킹보드 이미지 저장")

        if mode == "전체 누적":
            cap_title = "전체 누적 랭킹"
            cap_tag = f"total_{date.today()}"
        else:
            cap_title = f"{selected_date} 랭킹 (오늘 승패점 기준)"
            cap_tag = str(selected_date)

        if board_display is None or board_display.empty:
            st.info("캡처할 랭킹 데이터가 없습니다.")
        else:
            try:
                png_bytes, disp_w = board_to_png(board_display, cap_title)
                st.image(png_bytes, caption=f"미리보기 — {cap_title}", width=min(disp_w, 900))
                st.download_button(
                    "📥 PNG 이미지 다운로드",
                    data=png_bytes,
                    file_name=f"ranking_{cap_tag}.png",
                    mime="image/png",
                    key=f"dl_board_{mode}_{cap_tag}",
                )
            except Exception as e:
                st.warning(f"이미지 생성 실패: {e}")

        promo_log_df = storage_read_csv("promotion_log.csv")
        if promo_log_df is not None and not promo_log_df.empty:
            with st.expander("급수 자동 승급/강등 로그 보기"):
                st.dataframe(promo_log_df.tail(200), use_container_width=True, hide_index=True)

# =========================
# 탭 4: 파트너/궁합 통계
# =========================
with tabs[3]:
    st.subheader("파트너별 승률 / 궁합 통계")

    if matches_df.empty:
        st.info("아직 경기 데이터가 없습니다.")
    else:
        df = matches_df.copy()
        team_rows = []
        for _, m in df.iterrows():
            d = m["date"]
            w_pair = tuple(sorted([m["winner1"], m["winner2"]]))
            l_pair = tuple(sorted([m["loser1"], m["loser2"]]))
            win_pt = float(m["final_win_pt"])
            lose_pt = float(m["final_lose_pt"])

            team_rows.append({"date": d, "a": w_pair[0], "b": w_pair[1], "win": 1, "loss": 0, "points": win_pt})
            team_rows.append({"date": d, "a": l_pair[0], "b": l_pair[1], "win": 0, "loss": 1, "points": lose_pt})

        team_df = pd.DataFrame(team_rows)

        partner = team_df.groupby(["a","b"], as_index=False).agg(
            경기수=("a","count"),
            승=("win","sum"),
            패=("loss","sum"),
            누적점수=("points","sum"),
            평균점수=("points","mean"),
        )
        partner["승률"] = (partner["승"] / partner["경기수"]).fillna(0)
        partner["누적점수"] = pd.to_numeric(partner["누적점수"], errors="coerce").fillna(0).round(2)
        partner["평균점수"] = pd.to_numeric(partner["평균점수"], errors="coerce").fillna(0).round(2)

        partner = partner.sort_values(["승률","누적점수","경기수"], ascending=[False, False, False]).reset_index(drop=True)

        show_top = st.number_input("상위 N개 파트너 표시", min_value=10, max_value=200, value=50, step=10)
        view = partner.head(int(show_top)).copy()
        view["승률"] = (view["승률"]*100).round(1).astype(str) + "%"
        view.insert(0, "Rank", range(1, len(view)+1))

        view_disp = format_2dp_columns_for_display(view, ["누적점수", "평균점수"])
        st.dataframe(view_disp.rename(columns={"a":"파트너A","b":"파트너B"}), use_container_width=True, hide_index=True)

        st.divider()
        target = st.selectbox("특정 선수의 베스트 파트너 보기", options=[""] + names, index=0)
        if not target:
            st.info("선수를 선택하면 베스트 파트너를 보여드립니다.")
        else:
            sub = partner[(partner["a"] == target) | (partner["b"] == target)].copy()
            if sub.empty:
                st.info("해당 선수의 파트너 기록이 아직 없습니다.")
            else:
                sub["파트너"] = sub.apply(lambda x: x["b"] if x["a"] == target else x["a"], axis=1)
                sub = sub.groupby("파트너", as_index=False).agg(
                    경기수=("경기수","sum"),
                    승=("승","sum"),
                    패=("패","sum"),
                    누적점수=("누적점수","sum"),
                    평균점수=("평균점수","mean"),
                )
                sub["승률"] = (sub["승"] / sub["경기수"]).fillna(0)
                sub["누적점수"] = pd.to_numeric(sub["누적점수"], errors="coerce").fillna(0).round(2)
                sub["평균점수"] = pd.to_numeric(sub["평균점수"], errors="coerce").fillna(0).round(2)

                sub = sub.sort_values(["승률","누적점수","경기수"], ascending=[False, False, False]).reset_index(drop=True)
                sub["승률"] = (sub["승률"]*100).round(1).astype(str) + "%"
                sub.insert(0, "Rank", range(1, len(sub)+1))

                sub_disp = format_2dp_columns_for_display(sub, ["누적점수", "평균점수"])
                st.dataframe(sub_disp, use_container_width=True, hide_index=True)

# =========================
# 탭 5: 분기 스냅샷
# =========================
with tabs[4]:
    st.subheader("분기별 랭킹 스냅샷 저장")

    if matches_df.empty:
        st.info("경기 데이터가 없어서 스냅샷을 만들 수 없습니다.")
    else:
        df = matches_df.copy()
        years = sorted(pd.to_datetime(df["date"]).dt.year.unique().tolist())
        y = st.selectbox("연도", options=years, index=len(years)-1)
        q = st.selectbox("분기", options=[1,2,3,4], index=(quarter_of(date.today())-1))
        snap_mode = st.radio("스냅샷 기준", ["해당 분기만 집계", "해당 분기까지 누적"], horizontal=True)

        if snap_mode == "해당 분기만 집계":
            snap_df = filter_by_quarter(df, y, q)
        else:
            dtmp = normalize_date_col(df).copy()
            end_month = q * 3
            end_date = (pd.Timestamp(year=y, month=end_month, day=1) + pd.offsets.MonthEnd(0)).date()
            snap_df = dtmp[dtmp["date"] <= end_date].copy()

        board = make_rankboard(players_df, snap_df)
        board["승점"] = pd.to_numeric(board["승점"], errors="coerce").fillna(0).round(2)

        board_disp = format_2dp_columns_for_display(board, ["승점"])
        st.dataframe(style_rankboard(board_disp), use_container_width=True)

        if st.button("이 내용으로 스냅샷 저장"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"rank_snapshot_{y}_Q{q}_{'QONLY' if snap_mode=='해당 분기만 집계' else 'CUM'}_{ts}.csv"
            fpath = os.path.join(SNAPSHOT_DIR, fname)
            board.to_csv(fpath, index=False, encoding="utf-8-sig")
            st.success(f"저장 완료: {fname}")

        st.divider()
        files = sorted([f for f in os.listdir(SNAPSHOT_DIR) if f.lower().endswith(".csv")], reverse=True)
        if not files:
            st.info("아직 저장된 스냅샷이 없습니다.")
        else:
            pick = st.selectbox("다운로드할 스냅샷 선택", options=files, index=0)
            with open(os.path.join(SNAPSHOT_DIR, pick), "rb") as fp:
                st.download_button("선택 스냅샷 다운로드", data=fp, file_name=pick, mime="text/csv")

# =========================
# 탭 6: 원본 데이터 & 선수 관리
# =========================
with tabs[5]:
    st.subheader("원본 데이터 수정/삭제 & 선수 관리")

    st.markdown("## 경기 기록(matches.csv) 수정/삭제")
    editable = matches_df.copy()

    if editable.empty:
        st.info("현재 저장된 경기 기록이 없습니다.")
    else:
        if "삭제" not in editable.columns:
            editable.insert(0, "삭제", False)
        editable["date"] = editable["date"].astype(str)

        edited_matches = st.data_editor(
            editable,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "삭제": st.column_config.CheckboxColumn("삭제"),
                "winner1": st.column_config.SelectboxColumn("winner1", options=names_with_blank),
                "winner2": st.column_config.SelectboxColumn("winner2", options=names_with_blank),
                "loser1": st.column_config.SelectboxColumn("loser1", options=names_with_blank),
                "loser2": st.column_config.SelectboxColumn("loser2", options=names_with_blank),
                "winner_games": st.column_config.NumberColumn("winner_games", min_value=0, max_value=9, step=1),
                "loser_games": st.column_config.NumberColumn("loser_games", min_value=0, max_value=9, step=1),
            }
        )

        if st.button("수정/삭제 저장 (승점 자동 재계산)"):
            save_df = edited_matches.copy().reset_index(drop=True)
            if "삭제" not in save_df.columns:
                save_df.insert(0, "삭제", False)
            save_df = save_df.loc[~save_df["삭제"].astype(bool)].copy()
            save_df = save_df.drop(columns=["삭제"], errors="ignore")

            new_rows, errs = [], []
            current_players = load_players()
            current_grade_map = dict(zip(current_players["name"], current_players["grade"]))
            current_names = set(current_players["name"].tolist())

            for idx, m in save_df.iterrows():
                try:
                    w1, w2 = str(m["winner1"]).strip(), str(m["winner2"]).strip()
                    l1, l2 = str(m["loser1"]).strip(), str(m["loser2"]).strip()
                    wg, lg = int(m["winner_games"]), int(m["loser_games"])

                    if not (w1 and w2 and l1 and l2):
                        raise ValueError("이름이 비어있습니다.")
                    if any(p not in current_names for p in [w1, w2, l1, l2]):
                        raise ValueError("선수 목록에 없는 이름이 포함됨(선수 관리에서 확인)")
                    if w1 == w2 or l1 == l2:
                        raise ValueError("같은 사람을 같은 팀에 중복 선택")
                    if {w1, w2} & {l1, l2}:
                        raise ValueError("한 사람이 양 팀에 동시에 포함")
                    if wg <= lg:
                        raise ValueError("승리게임 수가 패배게임 수보다 커야 함")

                    res = compute_points(
                        current_grade_map[w1], current_grade_map[w2],
                        current_grade_map[l1], current_grade_map[l2],
                        wg, lg
                    )

                    row = m.to_dict()
                    row.update(res)
                    new_rows.append(row)
                except Exception as e:
                    errs.append(f"{idx}행 오류: {e}")

            if errs:
                st.error("저장 중 일부 오류가 발생했습니다.\n\n" + "\n".join(errs))

            final_df = pd.DataFrame(new_rows)
            final_df = normalize_date_col(final_df)
            save_matches(final_df)

            if auto_grade_enabled and not final_df.empty:
                updated_players, promo_logs = apply_auto_promo_demotion(
                    players_df=current_players,
                    matches_df=final_df,
                    mode=promo_mode,
                    min_matches=min_matches,
                    promote_threshold=float(promote_threshold),
                    demote_threshold=float(demote_threshold),
                    window=promo_window
                )
                if promo_logs:
                    save_players(updated_players)
                    append_promo_log(promo_logs)

            # ✅ 요약 엑셀 갱신
            build_and_save_summary(players_df=load_players(), matches_df=final_df)

            st.success(f"저장 완료! (총 {len(final_df)}게임)")
            st.cache_data.clear()
            st.rerun()

    st.download_button(
        "matches.csv 다운로드",
        data=matches_df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="matches.csv",
        mime="text/csv"
    )

    st.divider()
    st.markdown("## 선수 관리(players.csv) 추가/수정/삭제")

    players_edit = players_df.copy()
    if "삭제" not in players_edit.columns:
        players_edit.insert(0, "삭제", False)

    edited_players = st.data_editor(
        players_edit,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "삭제": st.column_config.CheckboxColumn("삭제"),
            "name": st.column_config.TextColumn("이름"),
            "grade": st.column_config.SelectboxColumn("급수", options=GRADE_LADDER),
        }
    )

    if st.button("선수 정보 저장"):
        edited_players_fixed = edited_players.copy().reset_index(drop=True)
        if "삭제" not in edited_players_fixed.columns:
            edited_players_fixed.insert(0, "삭제", False)

        final_players = edited_players_fixed.loc[~edited_players_fixed["삭제"].astype(bool)].copy()
        final_players = final_players.drop(columns=["삭제"], errors="ignore")

        final_players["name"] = final_players["name"].astype(str).str.strip()
        final_players["grade"] = final_players["grade"].astype(str).str.strip()
        final_players = final_players[final_players["name"] != ""].copy()

        if final_players.empty:
            st.error("저장할 선수가 없습니다. 최소 1명은 있어야 합니다.")
        elif final_players["name"].duplicated().any():
            st.error("선수 이름이 중복되었습니다. 중복을 제거해주세요.")
        elif (~final_players["grade"].isin(GRADE_LADDER)).any():
            st.error("급수 값이 올바르지 않습니다.")
        else:
            save_players(final_players)
            # ✅ 선수 변경 후에도 요약 엑셀 갱신
            build_and_save_summary(players_df=final_players, matches_df=matches_df)
            st.success("선수 정보 저장 완료!")
            st.cache_data.clear()
            st.rerun()

    st.download_button(
        "players.csv 다운로드",
        data=players_df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="players.csv",
        mime="text/csv"
    )

    st.divider()
    st.markdown("## 전체 요약 테이블(엑셀)")

    # ✅ 요약 엑셀 다운로드
    if os.path.exists(SUMMARY_XLSX_PATH):
        with open(SUMMARY_XLSX_PATH, "rb") as fp:
            st.download_button(
                "rank_summary.xlsx 다운로드(요약)",
                data=fp,
                file_name="rank_summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("요약 엑셀이 아직 없습니다. 경기 저장/수정 후 자동 생성됩니다.")
