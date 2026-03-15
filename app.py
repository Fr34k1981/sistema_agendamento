# ============================================
# Sistema de Agendamento • Streamlit + Supabase (REST, sem login p/ professor)
# Abas: ✨ Agendar | 📋 Meus Agendamentos | ⚙️ Gestão | 🖨️ Imprimir |
#       👥 Professores | 📈 Relatórios | 🧹 Manutenção
# ============================================

import os
import re
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

# -------- PDF (reportlab) --------
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# -------- Gráficos (matplotlib) --------
import matplotlib.pyplot as plt
from matplotlib import cm
import numpy as np

# -----------------------------
# 0) Config da Página
# -----------------------------
st.set_page_config(page_title="Sistema de Agendamento", layout="wide", page_icon="📅")

# -----------------------------
# 0.1) CSS — Tema vermelho + botões com brilho/sombra
# -----------------------------
def inject_css():
    st.markdown(
        """
        <style>
        :root{
            --brand-red: #D7263D;      /* vermelho principal */
            --brand-red-dark: #B31F33; /* vermelho mais escuro */
            --brand-red-light: #F04A5D;/* vermelho claro */
            --brand-gray-900:#0F1116;
            --brand-gray-700:#1C212C;
            --brand-gray-200:#E7E9EE;
            --brand-white:#FFFFFF;
        }

        /* Fundo sutil */
        .stApp {
            background: linear-gradient(180deg, #0f1116 0%, #141824 100%);
            color: var(--brand-white);
        }

        /* Títulos */
        h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            color: var(--brand-white);
            text-shadow: 0 1px 0 rgba(0,0,0,.3);
        }

        /* Linhas divisórias */
        hr, .stMarkdown hr {
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--brand-red), transparent);
            margin: 12px 0 18px 0;
        }

        /* Caixas/expanders */
        [data-testid="stExpander"] {
            border: 1px solid rgba(255,255,255,.08);
            background: rgba(255,255,255,.04);
            border-radius: 10px;
        }

        /* Campos de entrada */
        .stTextInput > div > div > input,
        .stSelectbox > div > div > div,
        .stDateInput > div > div > input {
            background: rgba(255,255,255,.06) !important;
            color: var(--brand-white) !important;
            border: 1px solid rgba(255,255,255,.12) !important;
            border-radius: 10px !important;
        }

        /* Dataframe glass */
        .stDataFrame {
            border: 1px solid rgba(255,255,255,.08);
            background: rgba(255,255,255,.03);
            border-radius: 10px;
        }

        /* Botões base (largura do texto) */
        div.stButton > button, div.stDownloadButton > button {
            display: inline-block;
            width: auto;                 /* largura = conteúdo */
            padding: 10px 16px;
            border-radius: 999px;        /* pílula */
            border: 0;
            font-weight: 600;
            letter-spacing: .2px;
            background: linear-gradient(180deg, var(--brand-red) 0%, var(--brand-red-dark) 100%);
            color: #fff;
            box-shadow: 0 6px 14px rgba(215, 38, 61, .35);
            transition: all .15s ease-in-out;
        }

        /* Hover: brilho */
        div.stButton > button:hover, div.stDownloadButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 20px rgba(215, 38, 61, .55), 0 0 0 2px rgba(240, 74, 93, .25) inset;
        }

        /* Active: press */
        div.stButton > button:active, div.stDownloadButton > button:active {
            transform: translateY(0);
            box-shadow: 0 6px 14px rgba(215, 38, 61, .35) inset;
        }

        /* “Secondary button” – usamos quando não selecionado na navbar */
        .btn-secondary > button{
            background: linear-gradient(180deg, #2a2f3f 0%, #1e2433 100%) !important;
            color: #e9ecf2 !important;
            box-shadow: 0 4px 10px rgba(10, 12, 16, .4) !important;
        }
        .btn-secondary > button:hover{
            box-shadow: 0 8px 16px rgba(10, 12, 16, .6) !important;
        }

        /* Contêiner horizontal (navbar) com espaçamento */
        .navbar-row {
            gap: 10px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 6px;
        }
        .navbar-row > div {
            flex: 0 0 auto; /* não estica */
        }

        /* Alertas com borda vermelha suave */
        .stAlert {
            border-radius: 12px;
            background: rgba(255,255,255,.03);
            border: 1px solid rgba(215,38,61,.25);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_css()

# -----------------------------
# 1) Credenciais Supabase (robustas)
# -----------------------------
def _get_secret(key: str, default: str = "") -> str:
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets.get(key)
    except Exception:
        pass
    return os.getenv(key, default)

SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "⚠️ Credenciais Supabase ausentes.\n\n"
        "Defina SUPABASE_URL / SUPABASE_KEY (anon JWT iniciando com `eyJ...`) em `.streamlit/secrets.toml` "
        "ou em **Settings → Secrets** (Streamlit Cloud)."
    )
    st.stop()

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
HEADERS_UPSERT = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}

# -----------------------------
# 2) Constantes e Listas
# -----------------------------
SENHA_GESTAO = "040600"          # ajuste aqui a senha da Gestão
DIAS_PRIORITARIO = 60
DIAS_NORMAL = 15

PRIORIDADES_ESTENDIDAS = ["Redação", "Leitura", "Tecnologia", "Programação"]
PRIORIDADES_OUTRAS = ["Matific", "Alura", "Speak"]
PRIORIDADE_VALIDAS = {"PRIORITARIO", "PRIORITÁRIO", "NORMAL"} | set(PRIORIDADES_ESTENDIDAS) | set(PRIORIDADES_OUTRAS)

ESPACOS = [
    "Sala de Informática",
    "Carrinho Positivo",
    "Carrinho ChromeBook",
    "Tablet Positivo",
    "Sala de Leitura",
]

HORARIOS = [
    "07:00-07:50", "07:50-08:40", "08:40-09:00", "08:40-09:30",
    "09:00-09:50", "09:30-09:50", "09:50-10:40", "10:40-11:30",
    "11:30-12:20", "12:20-13:10", "13:10-14:00", "14:00-14:50",
    "14:40-15:00", "14:50-15:40", "15:40-16:30", "16:40-17:30", "17:30-18:20"
]

# Intervalos por turma (informativo)
TURMAS_INTERVALOS = {
    "6º A": {"cafe": "08:40-09:00", "almoco": "10:40-11:30"},
    "6º B": {"cafe": "08:40-09:00", "almoco": "10:40-11:30"},
    "7º A": {"cafe": "08:40-09:00", "almoco": "10:40-11:30"},
    "7º B": {"cafe": "08:40-09:00", "almoco": "10:40-11:30"},
    "7º C": {"cafe": "08:40-09:00", "almoco": "10:40-11:30"},
    "8º A": {"cafe": "09:30-09:50", "almoco": "11:30-12:20"},
    "8º B": {"cafe": "09:30-09:50", "almoco": "11:30-12:20"},
    "8º C": {"cafe": "09:30-09:50", "almoco": "11:30-12:20"},
    "9º A": {"cafe": "09:30-09:50", "almoco": "11:30-12:20"},
    "9º B": {"cafe": "09:30-09:50", "almoco": "11:30-12:20"},
    "9º C": {"cafe": "09:30-09:50", "almoco": "11:30-12:20"},
    "3º A": {"cafe": "08:40-09:00", "almoco": "10:40-11:30"},
    "3º B": {"cafe": "08:40-09:00", "almoco": "10:40-11:30"},
    "1º A": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "1º B": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "1º C": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "1º D": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "1º E": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "1º F": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "2º A": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "2º B": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "2º C": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "3º C": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "3º D": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"},
    "3º E": {"cafe": "14:40-15:00", "almoco": "16:40-17:30"}
}

DISCIPLINAS = [
    "Língua Portuguesa", "Matemática", "Ciências", "Geografia", "História",
    "Arte", "Educação Física", "Língua Inglesa", "Projeto de Vida",
    "Tecnologia e Inovação", "Educação Financeira", "Redação e Leitura",
    "Orientação de Estudos", "Biologia", "Física", "Química",
    "Filosofia", "Sociologia", "Tecnologia e Robótica", "Itinerários Formativos",
    "Matific", "Alura", "Speak", "Redação", "Tecnologia"
]

# -----------------------------
# 3) Notificações (toasts + persistente)
# -----------------------------
if 'mensagem_tipo' not in st.session_state:
    st.session_state.mensagem_tipo = None
if 'mensagem_texto' not in st.session_state:
    st.session_state.mensagem_texto = None

def notify(kind: str, msg: str, toast: bool = True, persist: bool = False):
    kind = (kind or "info").lower().strip()
    if toast:
        st.toast(msg)
    if persist:
        st.session_state.mensagem_texto = msg
        st.session_state.mensagem_tipo = kind
    else:
        if   kind == "success": st.success(msg)
        elif kind == "warning": st.warning(msg)
        elif kind == "error":   st.error(msg)
        else:                   st.info(msg)

def render_persisted_message():
    if st.session_state.get("mensagem_texto"):
        tipo = st.session_state.get("mensagem_tipo", "info")
        msg = st.session_state["mensagem_texto"]
        if   tipo == "success": st.success(msg)
        elif tipo == "warning": st.warning(msg)
        elif tipo == "error":   st.error(msg)
        else:                   st.info(msg)
        st.session_state.mensagem_texto = None
        st.session_state.mensagem_tipo = None

# -----------------------------
# 4) Supabase Helpers (REST) - ANON
# -----------------------------
def _rest_get(path: str, params: dict = None, headers: dict = None, timeout: int = 20):
    url = f"{SUPABASE_URL}{path}"
    h = HEADERS.copy()
    if headers: h.update(headers)
    r = requests.get(url, headers=h, params=params or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _rest_post(path: str, payload: dict, headers: dict = None, timeout: int = 20):
    url = f"{SUPABASE_URL}{path}"
    h = HEADERS.copy()
    if headers: h.update(headers)
    r = requests.post(url, json=payload, headers=h, timeout=timeout)
    if r.status_code not in (200, 201): return False, f"{r.status_code} - {r.text}"
    return True, r.json()

def _rest_patch(path: str, payload: dict, timeout: int = 20):
    url = f"{SUPABASE_URL}{path}"
    r = requests.patch(url, json=payload, headers=HEADERS, timeout=timeout)
    if r.status_code not in (200, 204): return False, f"{r.status_code} - {r.text}"
    return True, None

# Professores
def prof_list(only_active: bool = True) -> pd.DataFrame:
    try:
        path = "/rest/v1/professores"
        sel = "?select=id,nome,email,status&order=nome.asc"
        extra = "&status=eq.ATIVO" if only_active else ""
        rows = _rest_get(path + sel + extra)
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id","nome","email","status"])
    except Exception as e:
        st.warning(f"Não foi possível carregar professores (REST): {e}")
        return pd.DataFrame(columns=["id","nome","email","status"])

def prof_insert(nome: str, email: str, status: str = "ATIVO"):
    payload = {"nome": nome.strip(), "email": email.strip(), "status": status.strip()}
    return _rest_post("/rest/v1/professores", payload)

def prof_upsert(nome: str, email: str, status: str = "ATIVO"):
    payload = {"nome": (nome or "").strip(), "email": (email or "").strip(), "status": status.strip()}
    return _rest_post("/rest/v1/professores?on_conflict=email", payload, headers=HEADERS_UPSERT)

def prof_update(id_: int, nome: str, email: str, status: str):
    payload = {"nome": nome.strip(), "email": email.strip(), "status": status.strip()}
    return _rest_patch(f"/rest/v1/professores?id=eq.{id_}", payload)

def prof_delete(id_: int):
    url = f"/rest/v1/professores?id=eq.{id_}"
    r = requests.delete(f"{SUPABASE_URL}{url}", headers=HEADERS, timeout=15)
    if r.status_code not in (200, 204): return False, f"{r.status_code} - {r.text}"
    return True, None

# Agendamentos
@st.cache_data(ttl=120)
def carregar_agendamentos_filtrado(data_ini: str, data_fim: str, espaco: str = None, professor: str = None) -> pd.DataFrame:
    try:
        base = "/rest/v1/agendamentos?select=id,data_agendamento,horario,espaco,turma,disciplina,prioridade,semanas,professor_nome,professor_email,status&order=data_agendamento.asc,horario.asc"
        filtros = f"&data_agendamento=gte.{data_ini}&data_agendamento=lte.{data_fim}"
        if espaco and espaco in ESPACOS:
            filtros += f"&espaco=eq.{espaco}"
        if professor:
            filtros += f"&professor_nome=eq.{professor}"
        rows = _rest_get(base + filtros)
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        st.warning(f"Falha ao consultar agendamentos: {e}")
        return pd.DataFrame()

def salvar_agendamento(dados: dict):
    return _rest_post("/rest/v1/agendamentos", dados)

def cancelar_agendamento(id_agend: str):
    return _rest_patch(f"/rest/v1/agendamentos?id=eq.{id_agend}", {"status": "CANCELADO"})

def excluir_agendamento(id_agend: str):
    return _rest_patch(f"/rest/v1/agendamentos?id=eq.{id_agend}", {"status": "EXCLUIDO_GESTAO"})

def atualizar_agendamento(id_agend: str, payload: dict):
    campos = {k: v for k, v in payload.items() if v is not None}
    return _rest_patch(f"/rest/v1/agendamentos?id=eq.{id_agend}", campos)

def verificar_conflito_api(data_yyyy_mm_dd: str, horario: str, espaco: str):
    try:
        path = "/rest/v1/agendamentos"
        sel = "?select=id,professor_nome"
        filtro = f"&data_agendamento=eq.{data_yyyy_mm_dd}&horario=eq.{horario}&espaco=eq.{espaco}&status=eq.ATIVO&limit=1"
        rows = _rest_get(path + sel + filtro)
        return rows[0] if rows else None
    except Exception:
        return None

# -----------------------------
# 5) Normalização CSV/XLSX
# -----------------------------
def _strip(x): return x.strip() if isinstance(x, str) else x

def _normalize_turma(t: str) -> str:
    if not isinstance(t, str): return t
    t = t.strip()
    t = re.sub(r"(\d)o(\s)", r"\1º\2", t)
    t = re.sub(r"(\d)o$", r"\1º", t)
    return t

def _normalize_espaco(e: str) -> str:
    if not isinstance(e, str): return e
    m = {
        "sala de informatica": "Sala de Informática",
        "sala de informática": "Sala de Informática",
        "sala de leitura": "Sala de Leitura",
        "tablet positivo": "Tablet Positivo",
        "carrinho chromebook": "Carrinho ChromeBook",
        "carrinho positivo": "Carrinho Positivo",
    }
    key = e.strip().lower()
    return m.get(key, e.strip())

def _normalize_prioridade(p) -> str:
    if p is None: return "NORMAL"
    s = str(p).strip().upper()
    if "PRIORIT" in s: return "PRIORITARIO"
    if "NORMAL"  in s: return "NORMAL"
    return str(p).strip() if str(p).strip() in PRIORIDADE_VALIDAS else "NORMAL"

def _normalize_status(raw: str, default="ATIVO") -> str:
    if not raw: return default
    s = str(raw).strip().upper()
    if "CANCEL" in s:  return "CANCELADO"
    if "EXCLU"  in s:  return "EXCLUIDO_GESTAO"
    return default

def _parse_dt_mixed(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    for dayfirst in (True, False):
        try:
            ts = pd.to_datetime(value, dayfirst=dayfirst, errors="raise")
            return ts.date().isoformat()
        except Exception:
            pass
    try:
        num = float(value)
        base = pd.Timestamp("1899-12-30")
        dt = base + pd.to_timedelta(num, unit="D")
        return dt.date().isoformat()
    except Exception:
        return None

def _guess_status_from_row(row: dict) -> str:
    for key in ["status", "Status", "STATUS", "Data Agendamento", "data_agendamento", "Prioridade"]:
        if key in row and isinstance(row[key], str):
            stt = _normalize_status(row[key], default=None)
            if stt in ("CANCELADO", "EXCLUIDO_GESTAO"):
                return stt
    return "ATIVO"

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "data agendamento": "data_agendamento",
        "data_agendamento": "data_agendamento",
        "horário": "horario",
        "horario": "horario",
        "espaço": "espaco",
        "espaco": "espaco",
        "turma": "turma",
        "professor": "professor_nome",
        "email": "professor_email",
        "disciplina": "disciplina",
        "semanas": "semanas",
        "prioridade": "prioridade",
        "status": "status",
    }
    new_cols = {}
    for c in df.columns:
        key = c.strip().lower()
        new_cols[c] = mapping.get(key, c)
    return df.rename(columns=new_cols)

def _adapt_from_planilha_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(df)
    needed = ["data_agendamento","horario","espaco","turma","disciplina","prioridade","professor_nome","professor_email"]
    for n in needed:
        if n not in df.columns: df[n] = None

    if "status" not in df.columns: df["status"] = None
    df["status"] = [
        _guess_status_from_row(row._asdict() if hasattr(row, "_asdict") else row.to_dict())
        for _, row in df.iterrows()
    ]
    df["status"] = df["status"].apply(lambda x: _normalize_status(x, default="ATIVO"))

    df["data_agendamento"] = df["data_agendamento"].apply(_parse_dt_mixed)
    df["horario"] = df["horario"].apply(lambda x: _strip(x) if isinstance(x, str) else x)
    df["espaco"] = df["espaco"].apply(_normalize_espaco)
    df["turma"] = df["turma"].apply(_normalize_turma)
    df["disciplina"] = df["disciplina"].apply(lambda x: _strip(x) if isinstance(x, str) else x)
    df["prioridade"] = df["prioridade"].apply(_normalize_prioridade)
    df["professor_nome"] = df["professor_nome"].apply(lambda x: _strip(x) if isinstance(x, str) else x)
    df["professor_email"] = df["professor_email"].apply(lambda x: _strip(x) if isinstance(x, str) else x)

    df = df[
        df["data_agendamento"].notna() &
        df["horario"].notna() &
        df["espaco"].notna() &
        df["turma"].notna() &
        df["professor_nome"].notna()
    ].copy()
    return df

def _download_modelo_csv() -> bytes:
    modelo = pd.DataFrame([{
        "data_agendamento": "2026-03-15",
        "horario": "07:00-07:50",
        "espaco": "Sala de Informática",
        "turma": "6º A",
        "disciplina": "Redação",
        "prioridade": "PRIORITARIO",
        "professor_nome": "Professor(a) Teste",
        "professor_email": "teste@example.com",
        "status": "ATIVO",
    }])
    return modelo.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

def _ensure_professor(nome: str, email: str, create_if_missing: bool) -> bool:
    try:
        if email:
            path = f"/rest/v1/professores?select=id&email=eq.{email}"
            r = _rest_get(path)
            if r: return True
            if create_if_missing:
                ok, _ = prof_upsert(nome.strip() if nome else email.split("@")[0], email.strip(), "ATIVO")
                return ok
            return False
        if nome:
            path = f"/rest/v1/professores?select=id&nome=eq.{nome}"
            r = _rest_get(path)
            if r: return True
        return False if not create_if_missing else prof_upsert(nome or "(sem nome)", email or "", "ATIVO")[0]
    except Exception:
        return False

def importar_agendamentos_df(
    df_input: pd.DataFrame,
    ignorar_cancelados: bool = True,
    incluir_excluido_gestao: bool = True,
    criar_prof_automatico: bool = True
):
    df = _adapt_from_planilha_if_needed(df_input)

    if ignorar_cancelados:
        df = df[df["status"] != "CANCELADO"]
    if not incluir_excluido_gestao:
        df = df[df["status"] != "EXCLUIDO_GESTAO"]

    def _hor_ok(h): return isinstance(h, str) and h in HORARIOS
    def _esp_ok(e): return isinstance(e, str) and e in ESPACOS

    invalid_rows, rows_to_insert = [], []

    for idx, row in df.iterrows():
        err = []
        data_iso = row["data_agendamento"]
        horario = row["horario"]
        espaco = row["espaco"]
        turma = row["turma"]
        disc = row["disciplina"]
        prior = row["prioridade"]
        prof_nome = row["professor_nome"]
        prof_email = row["professor_email"]
        status = row["status"] or "ATIVO"

        if not data_iso: err.append("data_agendamento inválida")
        if not _hor_ok(horario): err.append("horario inválido")
        if not _esp_ok(espaco): err.append("espaco inválido (use nomes do app)")
        if not prof_nome: err.append("professor_nome vazio")
        if not _ensure_professor(prof_nome, prof_email, criar_prof_automatico):
            err.append("professor inexistente e criação automática desabilitada")

        if err:
            invalid_rows.append((idx, "; ".join(err)))
            continue

        payload = {
            "data_agendamento": data_iso,
            "horario": horario,
            "espaco": espaco,
            "turma": turma,
            "disciplina": disc,
            "prioridade": prior,
            "semanas": 0,
            "professor_nome": prof_nome,
            "professor_email": prof_email or None,
            "status": status
        }
        rows_to_insert.append((idx, payload))

    sucessos, falhas = [], []
    for idx, payload in rows_to_insert:
        ok, resp = salvar_agendamento(payload)
        if ok: sucessos.append((idx, payload))
        else:  falhas.append((idx, payload, resp))
    return sucessos, falhas, invalid_rows, df

# -----------------------------
# 6) Estados de Sessão + Navegação
# -----------------------------
if 'gestao_logado' not in st.session_state:
    st.session_state.gestao_logado = False
if 'aba_selecionada' not in st.session_state:
    st.session_state.aba_selecionada = "✨ Agendar"
if 'pending_cancel_id' not in st.session_state:
    st.session_state.pending_cancel_id = None
if 'pending_delete_id' not in st.session_state:
    st.session_state.pending_delete_id = None
if 'pending_delete_prof' not in st.session_state:
    st.session_state.pending_delete_prof = None

# ===== LIMPEZA DE CACHE (TEMPORÁRIO) =====
if st.button("🧽 Limpar cache (temporário)"):
    st.cache_data.clear()
    st.rerun()

# Navbar (7 abas) — botões “soltos”, tamanho do texto
nav_cols = st.container()
with nav_cols:
    st.markdown('<div class="navbar-row">', unsafe_allow_html=True)
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    def nav_button(col, label):
        selected = (st.session_state.aba_selecionada == label)
        # aplica classe "btn-secondary" quando NÃO selecionado (cor escura)
        with col:
            btn_holder = st.container()
            if not selected: 
                btn_holder.markdown('<div class="btn-secondary">', unsafe_allow_html=True)
            clicked = st.button(label, key=f"nav_{label}")
            if not selected:
                btn_holder.markdown('</div>', unsafe_allow_html=True)
            if clicked:
                st.session_state.aba_selecionada = label
                st.experimental_rerun()
    nav_button(col1, "✨ Agendar")
    nav_button(col2, "📋 Meus Agendamentos")
    nav_button(col3, "⚙️ Gestão")
    nav_button(col4, "🖨️ Imprimir")
    nav_button(col5, "👥 Professores")
    nav_button(col6, "📈 Relatórios")
    nav_button(col7, "🧹 Manutenção")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# -----------------------------
# 7) ABA ✨ Agendar
# -----------------------------
if st.session_state.aba_selecionada == "✨ Agendar":
    st.subheader("📅 Novo Agendamento — Espaços de Tecnologia e Leitura")
    render_persisted_message()

    df_prof = prof_list(only_active=True)
    lista_nomes = df_prof["nome"].dropna().tolist() if not df_prof.empty else []

    with st.form("form_agendamento", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            if not lista_nomes:
                st.warning("⚠️ Nenhum professor ATIVO encontrado. Use a aba '👥 Professores' para cadastrar/importar.")
            professor = st.selectbox("👨‍🏫 Professor:", [""] + lista_nomes, index=0)

            # auto preencher e-mail
            email_default = ""
            if professor and not df_prof.empty:
                linha = df_prof[df_prof["nome"] == professor]
                if not linha.empty:
                    v = linha.iloc[0].get("email")
                    if isinstance(v, str):
                        email_default = v

            email = st.text_input("📧 Email (opcional):", value=email_default)
            turma = st.selectbox("🎓 Turma:", [""] + sorted(TURMAS_INTERVALOS.keys()))
            disciplina = st.selectbox("📚 Disciplina:", [""] + DISCIPLINAS)

            if turma and turma in TURMAS_INTERVALOS:
                intervalos = TURMAS_INTERVALOS[turma]
                st.info(f"⏰ Intervalos dessa turma: ☕ {intervalos['cafe']} • 🍽️ {intervalos['almoco']}")

        with col2:
            prioridade = st.selectbox("⭐ Prioridade:", [""] + PRIORIDADES_ESTENDIDAS + PRIORIDADES_OUTRAS)
            espaco = st.selectbox("📍 Espaço:", [""] + ESPACOS)
            data = st.date_input("📅 Data:", min_value=datetime.now().date())

            st.markdown("### ⏰ Horários")
            horario1 = st.selectbox("1ª Aula:", [""] + HORARIOS)
            horario2 = st.selectbox("2ª Aula (opcional):", [""] + HORARIOS)

            semanas = st.selectbox("🔄 Repetir por:", [
                "📅 Apenas este dia", "📆 1 semana", "📆 2 semanas", "📆 3 semanas", "📆 4 semanas"
            ])

        submitted = st.form_submit_button("✅ Confirmar Agendamento")

        if submitted:
            if (not professor) or (not disciplina) or (not prioridade) or (not espaco) or (not turma):
                notify('warning', "⚠️ Preencha todos os campos obrigatórios", toast=True, persist=True)
                st.rerun()

            horarios = [h for h in [horario1, horario2] if h]
            if not horarios:
                notify('warning', "⚠️ Selecione pelo menos 1 horário", toast=True, persist=True)
                st.rerun()

            semanas_num = int(semanas.split()[1]) if semanas != "📅 Apenas este dia" else 0
            eh_prioritario = prioridade in PRIORIDADES_ESTENDIDAS
            limite_dias = DIAS_PRIORITARIO if eh_prioritario else DIAS_NORMAL
            diff_dias = (data - datetime.now().date()).days
            if diff_dias > limite_dias:
                notify('warning', f"⚠️ Antecedência máxima: {limite_dias} dias", toast=True, persist=True)
                st.rerun()

            if turma in TURMAS_INTERVALOS:
                intervalos = TURMAS_INTERVALOS[turma]
                for h in horarios:
                    if h in [intervalos.get('cafe'), intervalos.get('almoco')]:
                        notify('warning', "⚠️ Horário de intervalo para esta turma", toast=True, persist=True)
                        st.rerun()

            # Conflito
            conflito_msg = None
            for h in horarios:
                for i in range(semanas_num + 1):
                    data_rep = data + timedelta(days=i * 7)
                    conf = verificar_conflito_api(data_rep.strftime("%Y-%m-%d"), h, espaco)
                    if conf:
                        nome_quem = conf.get("professor_nome", "(desconhecido)")
                        conflito_msg = f"{nome_quem} em {data_rep.strftime('%d/%m')} às {h}"
                        break
                if conflito_msg: break

            if conflito_msg:
                notify('error', f"❌ CONFLITO: {conflito_msg} já agendou", toast=True, persist=True)
                st.rerun()
            else:
                falhas, sucessos = [], 0
                for i in range(semanas_num + 1):
                    data_salvar = (data + timedelta(days=i * 7)).strftime("%Y-%m-%d")
                    for h in horarios:
                        ok, resp = salvar_agendamento({
                            "data_agendamento": data_salvar,
                            "horario": h,
                            "espaco": espaco,
                            "turma": turma,
                            "disciplina": disciplina,
                            "prioridade": prioridade,
                            "semanas": semanas_num,
                            "professor_nome": professor,
                            "professor_email": email or None,
                            "status": "ATIVO"
                        })
                        if ok: sucessos += 1
                        else:  falhas.append((f"{data_salvar} {h}", resp))

                if sucessos:
                    notify('success', f"✅ Agendamento confirmado! ({sucessos} registro(s))", toast=True, persist=True)
                if falhas:
                    notify('warning', f"⚠️ Alguns registros falharam: {len(falhas)}", toast=True, persist=False)
                    with st.expander("Ver falhas"):
                        for item, err in falhas:
                            st.caption(f"- {item}: {err}")
                st.rerun()

# -----------------------------
# 8) ABA 📋 Meus Agendamentos (inclui Importar)
# -----------------------------
elif st.session_state.aba_selecionada == "📋 Meus Agendamentos":
    st.header("📋 Meus Agendamentos")
    render_persisted_message()

    df_prof = prof_list(only_active=True)
    lista_nomes = df_prof["nome"].dropna().tolist() if not df_prof.empty else []
    professor_selecionado = st.selectbox("👨‍🏫 Seu Nome:", [""] + lista_nomes)

    if st.button("🔍 Buscar"):
        if not professor_selecionado:
            notify('warning', "⚠️ Selecione seu nome primeiro", toast=True, persist=False)
        else:
            hoje = datetime.now().date()
            ini = hoje - timedelta(days=7)
            fim = hoje + timedelta(days=90)
            df = carregar_agendamentos_filtrado(ini.isoformat(), fim.isoformat(), professor=professor_selecionado)
            if df.empty:
                st.info("📭 Nenhum agendamento encontrado")
            else:
                for _, row in df.iterrows():
                    data_obj = datetime.strptime(row['data_agendamento'], '%Y-%m-%d')
                    dia_semana = data_obj.strftime('%A')
                    eh_prioritario = (row.get('prioridade') in PRIORIDADES_ESTENDIDAS)

                    with st.expander(f"{dia_semana}, {row['data_agendamento']} - {row['horario']} {'⭐' if eh_prioritario else ''}", expanded=False):
                        st.markdown(f"""
**📍 Espaço:** {row['espaco']}  
**🎓 Turma:** {row['turma']}  
**📚 Disciplina:** {row['disciplina']}  
**🔖 Prioridade:** {row.get('prioridade', '')}  
**👨‍🏫 Professor:** {row['professor_nome']}  
**🆔 ID:** {row['id']}
""")

                        a1, a2, a3 = st.columns(3)

                        # --- Editar ---
                        if a1.button("✏️ Editar", key=f"edit_{row['id']}"):
                            st.session_state[f"edit_mode_{row['id']}"] = True

                        if st.session_state.get(f"edit_mode_{row['id']}", False):
                            with st.form(f"form_edit_{row['id']}"):
                                c1, c2 = st.columns(2)
                                with c1:
                                    novo_espaco = st.selectbox("📍 Espaço", ESPACOS, index=ESPACOS.index(row['espaco']) if row['espaco'] in ESPACOS else 0)
                                    nova_turma = st.text_input("🎓 Turma", value=row['turma'])
                                    nova_disc = st.text_input("📚 Disciplina", value=row['disciplina'] or "")
                                with c2:
                                    nova_prior = st.selectbox("⭐ Prioridade", PRIORIDADES_ESTENDIDAS + PRIORIDADES_OUTRAS + ["PRIORITARIO", "NORMAL"])
                                    novo_email = st.text_input("📧 Email (opcional)", value=row.get('professor_email') or "")

                                if st.form_submit_button("💾 Salvar alterações"):
                                    ok, err = atualizar_agendamento(row['id'], {
                                        "espaco": novo_espaco,
                                        "turma": nova_turma,
                                        "disciplina": nova_disc,
                                        "prioridade": nova_prior,
                                        "professor_email": novo_email or None
                                    })
                                    if ok:
                                        notify('success', "✅ Agendamento atualizado.", toast=True, persist=True)
                                        st.session_state[f"edit_mode_{row['id']}"] = False
                                        st.rerun()
                                    else:
                                        notify('error', f"Erro ao atualizar: {err}", toast=True, persist=False)
                            if st.button("↩️ Cancelar edição", key=f"cancel_edit_{row['id']}"):
                                st.session_state[f"edit_mode_{row['id']}"] = False

                        # --- Excluir (EXCLUIDO_GESTAO) ---
                        if a2.button("🗑️ Excluir", key=f"del_{row['id']}"):
                            st.session_state[f"confirm_del_{row['id']}"] = True

                        if st.session_state.get(f"confirm_del_{row['id']}", False):
                            d1, d2 = st.columns(2)
                            if d1.button("✅ Confirmar exclusão", key=f"conf_del_{row['id']}"):
                                ok, err = excluir_agendamento(row['id'])
                                if ok:
                                    notify('success', "🗑️ Agendamento marcado como EXCLUIDO_GESTAO.", toast=True, persist=True)
                                    st.session_state[f"confirm_del_{row['id']}"] = False
                                    st.rerun()
                                else:
                                    notify('error', f"Erro ao excluir: {err}", toast=True, persist=False)
                            if d2.button("↩️ Voltar", key=f"undo_del_{row['id']}"):
                                st.session_state[f"confirm_del_{row['id']}"] = False

                        # --- Cancelar ---
                        if st.session_state.pending_cancel_id == row['id']:
                            c1, c2 = st.columns(2)
                            if c1.button("✅ Confirmar cancelamento", key=f"conf_cancel_{row['id']}"):
                                ok, err = cancelar_agendamento(row['id'])
                                if ok:
                                    notify('success', "🗑️ Agendamento cancelado com sucesso.", toast=True, persist=True)
                                    st.session_state.pending_cancel_id = None
                                    st.rerun()
                                else:
                                    notify('error', f"Erro ao cancelar: {err}", toast=True, persist=False)
                            if c2.button("↩️ Voltar", key=f"undo_cancel_{row['id']}"):
                                st.session_state.pending_cancel_id = None
                        else:
                            if a3.button("🛑 Cancelar", key=f"cancel_{row['id']}", type="secondary"):
                                st.session_state.pending_cancel_id = row['id']

    st.markdown("---")

    # ====== IMPORTAR AGENDAMENTOS ======
    st.subheader("📥 Importar agendamentos (CSV ou XLSX)")
    st.caption("Selecione o arquivo e, após o preview, clique em **🚀 Importar agora**.")
    colopt1, colopt2, colopt3 = st.columns(3)
    with colopt1:
        ignorar_cancelados = st.checkbox("Ignorar CANCELADO", value=True)
    with colopt2:
        incluir_excluido_gestao = st.checkbox("Incluir EXCLUIDO_GESTAO", value=True)
    with colopt3:
        criar_prof_automatico = st.checkbox("Criar professor automaticamente", value=True)

    c_download, c_up = st.columns([1, 2])
    with c_download:
        st.download_button(
            "⬇️ Baixar modelo CSV",
            data=_download_modelo_csv(),
            file_name="agendamentos_modelo.csv",
            mime="text/csv"
        )
    with c_up:
        up = st.file_uploader("📄 Localizar arquivo (CSV ou XLSX)", type=["csv","xlsx"], accept_multiple_files=False)

    if up is not None:
        try:
            df_raw = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up, engine="openpyxl")
            st.success(f"✅ Arquivo carregado: {up.name} — {len(df_raw)} linha(s).")

            _, _, _, df_norm_preview = importar_agendamentos_df(
                df_raw,
                ignorar_cancelados=ignorar_cancelados,
                incluir_excluido_gestao=incluir_excluido_gestao,
                criar_prof_automatico=criar_prof_automatico
            )
            show_cols = ["data_agendamento","horario","espaco","turma","disciplina","prioridade","professor_nome","professor_email","status"]
            for c in show_cols:
                if c not in df_norm_preview.columns:
                    df_norm_preview[c] = None
            st.dataframe(df_norm_preview[show_cols].head(30), use_container_width=True, hide_index=True)

            btn_c1, btn_c2 = st.columns([1,1])
            with btn_c1:
                if st.button("🚀 Importar agora"):
                    sucessos, falhas, invalid_rows, _ = importar_agendamentos_df(
                        df_raw,
                        ignorar_cancelados=ignorar_cancelados,
                        incluir_excluido_gestao=incluir_excluido_gestao,
                        criar_prof_automatico=criar_prof_automatico
                    )
                    if sucessos:
                        notify('success', f"✅ Inseridos: {len(sucessos)}", toast=True, persist=True)
                    if invalid_rows:
                        notify('warning', f"⚠️ Linhas inválidas (não enviadas): {len(invalid_rows)}", toast=True, persist=False)
                        with st.expander("Ver inválidas"):
                            for idx, msg in invalid_rows:
                                st.write(f"- linha #{idx}: {msg}")
                    if falhas:
                        notify('error', f"❌ Falhas (ex.: 409 conflito): {len(falhas)}", toast=True, persist=False)
                        with st.expander("Ver falhas"):
                            for idx, payload, err in falhas:
                                st.write(f"- #{idx} | {payload.get('data_agendamento')} {payload.get('horario')} / {payload.get('espaco')} → {err}")
                    if sucessos and not falhas:
                        st.balloons()
            with btn_c2:
                if st.button("🧹 Limpar arquivo"):
                    st.rerun()
        except Exception as e:
            notify('error', f"Erro ao processar arquivo: {e}", toast=True, persist=False)

# -----------------------------
# 9) ABA ⚙️ Gestão (senha simples)
# -----------------------------
elif st.session_state.aba_selecionada == "⚙️ Gestão":
    st.header("⚙️ Gestão de Agendamentos")
    render_persisted_message()

    if not st.session_state.gestao_logado:
        st.info("🔐 Acesso restrito")
        senha = st.text_input("Senha da Gestão:", type="password")
        if st.button("🔓 Acessar"):
            if senha == SENHA_GESTAO:
                st.session_state.gestao_logado = True
                notify('success', "✅ Acesso autorizado!", toast=True, persist=True)
                st.rerun()
            else:
                notify('error', "❌ Senha inválida", toast=True, persist=False)
    else:
        if st.button("🚪 Sair"):
            st.session_state.gestao_logado = False
            st.rerun()

        col1, col2, col3 = st.columns(3)
        with col1:
            data_inicio = st.date_input("Início:", datetime.now().date())
        with col2:
            data_fim = st.date_input("Fim:", datetime.now().date() + timedelta(days=30))
        with col3:
            espaco_filtro = st.selectbox("Espaço:", ["Todos"] + ESPACOS)

        if st.button("🔍 Carregar"):
            df = carregar_agendamentos_filtrado(
                data_inicio.strftime("%Y-%m-%d"),
                data_fim.strftime("%Y-%m-%d"),
                espaco=None if espaco_filtro=="Todos" else espaco_filtro
            )
            if df.empty:
                st.info("📭 Nada no período escolhido.")
            else:
                st.dataframe(
                    df[['id','data_agendamento','horario','espaco','turma','professor_nome','disciplina','prioridade','status']],
                    use_container_width=True, hide_index=True
                )

                st.markdown("### 🗑️ Excluir (marcar como EXCLUIDO_GESTAO)")
                id_list = df['id'].tolist()
                id_excluir = st.selectbox("Selecione o ID:", id_list)

                if id_excluir:
                    if st.session_state.pending_delete_id == id_excluir:
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Confirmar exclusão", key=f"conf_{id_excluir}"):
                            ok, err = excluir_agendamento(id_excluir)
                            if ok:
                                notify('success', "🗑️ Agendamento marcado como EXCLUIDO_GESTAO.", toast=True, persist=True)
                                st.session_state.pending_delete_id = None
                                st.rerun()
                            else:
                                notify('error', f"Erro: {err}", toast=True, persist=False)
                        if c2.button("↩️ Cancelar", key=f"undo_{id_excluir}"):
                            st.session_state.pending_delete_id = None
                    else:
                        if st.button("🗑️ Excluir Permanentemente"):
                            st.session_state.pending_delete_id = id_excluir

# -----------------------------
# 10) ABA 🖨️ Imprimir
# -----------------------------
elif st.session_state.aba_selecionada == "🖨️ Imprimir":
    st.header("🖨️ Relatório para Impressão")
    render_persisted_message()

    col1, col2, col3 = st.columns(3)
    with col1:
        data_inicio = st.date_input("Data início:", datetime.now().date())
    with col2:
        data_fim = st.date_input("Data fim:", datetime.now().date() + timedelta(days=30))
    with col3:
        espaco_filtro = st.selectbox("Espaço:", ["Todos"] + ESPACOS)

    if st.button("📊 Gerar Relatório"):
        df = carregar_agendamentos_filtrado(
            data_inicio.strftime("%Y-%m-%d"),
            data_fim.strftime("%Y-%m-%d"),
            espaco=None if espaco_filtro=="Todos" else espaco_filtro
        )
        if df.empty:
            st.info("📭 Nenhum agendamento no período.")
        else:
            notify('info', f"📄 Relatório com {len(df)} linha(s) pronto.", toast=True, persist=False)
            st.dataframe(
                df[['data_agendamento','horario','espaco','turma','professor_nome','disciplina','prioridade','status']],
                use_container_width=True, hide_index=True
            )
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            c1, c2 = st.columns([1,1])
            with c1:
                st.download_button(
                    label="📥 Baixar CSV",
                    data=csv,
                    file_name=f"agendamentos_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            with c2:
                if st.button("🖨️ Imprimir"):
                    components.html("<script>window.print()</script>", height=0, width=0)

            # Exportar PDF
            c3, _ = st.columns([1,1])
            with c3:
                def gerar_pdf_agendamentos(df_pdf: pd.DataFrame, titulo: str = "Relatório de Agendamentos") -> bytes:
                    if df_pdf is None or df_pdf.empty: return b""
                    from io import BytesIO
                    buffer = BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
                    styles = getSampleStyleSheet()
                    story = []
                    story.append(Paragraph(titulo, styles["Title"]))
                    story.append(Spacer(1, 8))
                    cols = ["data_agendamento","horario","espaco","turma","professor_nome","disciplina","prioridade","status"]
                    for c in cols:
                        if c not in df_pdf.columns: df_pdf[c] = ""
                    data_tab = [ ["Data","Horário","Espaço","Turma","Professor","Disciplina","Prioridade","Status"] ]
                    for _, r in df_pdf[cols].iterrows():
                        data_tab.append([
                            r["data_agendamento"], r["horario"], r["espaco"], r["turma"],
                            r["professor_nome"], r["disciplina"], r.get("prioridade",""), r["status"]
                        ])
                    table = Table(data_tab, repeatRows=1)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#eeeeee")),
                        ('TEXTCOLOR',(0,0),(-1,0), colors.black),
                        ('ALIGN',(0,0),(-1,-1),'LEFT'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0,0), (-1,-1), 9),
                        ('BOTTOMPADDING', (0,0), (-1,0), 6),
                        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                    ]))
                    story.append(table)
                    doc.build(story)
                    pdf = buffer.getvalue()
                    buffer.close()
                    return pdf

                pdf_bytes = gerar_pdf_agendamentos(df, titulo=f"Agendamentos {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
                st.download_button(
                    "📄 Exportar PDF",
                    data=pdf_bytes,
                    file_name=f"agendamentos_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    disabled=(not pdf_bytes)
                )

# -----------------------------
# 11) ABA 👥 Professores (CRUD + Import CSV)
# -----------------------------
elif st.session_state.aba_selecionada == "👥 Professores":
    st.header("👥 Professores — Importar, Cadastrar, Editar, Excluir")
    render_persisted_message()

    colA, colB, _ = st.columns([1,1,3])
    with colA:
        if st.button("🔄 Atualizar lista"):
            st.rerun()
    with colB:
        filtro_status = st.selectbox("Filtro", ["ATIVOS", "TODOS"], index=0)

    st.markdown("### 📥 Importar CSV (professores)")
    st.caption("Cabeçalho: nome,email,status")
    up = st.file_uploader("Selecione um CSV", type=["csv"], key="up_prof")
    if up is not None:
        try:
            df_csv = pd.read_csv(up)
            st.dataframe(df_csv.head(10), use_container_width=True, hide_index=True)
            if st.button("⬆️ Enviar CSV (upsert por email)"):
                res = {"ok": 0, "fail": 0, "msgs": []}
                df_csv = df_csv.rename(columns={c: c.lower().strip() for c in df_csv.columns})
                if not {"nome","email","status"}.issubset(set(df_csv.columns)):
                    notify('error', "CSV inválido. Cabeçalho precisa de nome,email,status", toast=True, persist=False)
                else:
                    for _, r in df_csv.iterrows():
                        ok, resp = prof_upsert(str(r["nome"]), str(r["email"]), str(r["status"]))
                        if ok: res["ok"] += 1
                        else:
                            res["fail"] += 1
                            res["msgs"].append(f'{r.get("email")}: {resp}')
                    if res["ok"]:
                        notify('success', f"👥 {res['ok']} professor(es) atualizados/criados.", toast=True, persist=True)
                    if res["fail"]:
                        notify('warning', f"⚠️ {res['fail']} falha(s) ao importar. Veja detalhes abaixo.", toast=True, persist=False)
                        with st.expander("Ver falhas"):
                            for m in res["msgs"]:
                                st.write("- ", m)
                    st.rerun()
        except Exception as e:
            notify('error', f"Erro ao ler CSV: {e}", toast=True, persist=False)

    st.markdown("---")
    st.markdown("### ➕ Cadastrar professor")
    with st.form("form_prof_novo"):
        c1, c2, c3 = st.columns([2,2,1])
        nome_n = c1.text_input("Nome *")
        email_n = c2.text_input("Email *")
        status_n = c3.selectbox("Status", ["ATIVO", "INATIVO"], index=0)
        if st.form_submit_button("Salvar"):
            if not nome_n or not email_n:
                notify('warning', "Informe nome e e‑mail.", toast=True, persist=False)
            else:
                ok, resp = prof_insert(nome_n, email_n, status_n)
                if ok:
                    notify('success', "👤 Professor cadastrado!", toast=True, persist=True)
                    st.rerun()
                else:
                    notify('error', f"Erro ao salvar: {resp}", toast=True, persist=False)

    st.markdown("---")
    st.markdown("### ✏️ Editar / 🗑️ Excluir")
    df_all = prof_list(only_active=(filtro_status == "ATIVOS"))
    if df_all.empty:
        st.info("Nenhum professor encontrado com o filtro atual.")
    else:
        for _, row in df_all.iterrows():
            with st.expander(f"{row['nome']} — {row['email']} ({row['status']})", expanded=False):
                f1, f2, f3 = st.columns([2,2,1])
                nome_e = f1.text_input("Nome", value=row["nome"], key=f"nome_{row['id']}")
                email_e = f2.text_input("Email", value=row["email"], key=f"email_{row['id']}")
                status_e = f3.selectbox("Status", ["ATIVO", "INATIVO"], index=(0 if row["status"] == "ATIVO" else 1), key=f"status_{row['id']}")

                b1, b2, b3 = st.columns([1,1,2])
                if b1.button("💾 Atualizar", key=f"upd_{row['id']}"):
                    ok, err = prof_update(int(row["id"]), nome_e, email_e, status_e)
                    if ok:
                        notify('success', "✅ Professor atualizado.", toast=True, persist=True)
                        st.rerun()
                    else:
                        notify('error', f"Erro: {err}", toast=True, persist=False)

                novo_status = "INATIVO" if row["status"] == "ATIVO" else "ATIVO"
                if b2.button(("🚫 Inativar" if row["status"] == "ATIVO" else "✅ Ativar"), key=f"toggle_{row['id']}"):
                    ok, err = prof_update(int(row["id"]), nome_e, email_e, novo_status)
                    if ok:
                        notify('success', f"Estado alterado para {novo_status}.", toast=True, persist=True)
                        st.rerun()
                    else:
                        notify('error', f"Erro: {err}", toast=True, persist=False)

                if st.session_state.pending_delete_prof == row["id"]:
                    c1, c2 = st.columns(2)
                    if c1.button("❗ Confirmar exclusão", key=f"conf_del_prof_{row['id']}"):
                        ok, err = prof_delete(int(row["id"]))
                        if ok:
                            notify('success', "🗑️ Professor excluído.", toast=True, persist=True)
                            st.session_state.pending_delete_prof = None
                            st.rerun()
                        else:
                            notify('error', f"Erro: {err}", toast=True, persist=False)
                    if c2.button("↩️ Cancelar", key=f"undo_del_prof_{row['id']}"):
                        st.session_state.pending_delete_prof = None
                else:
                    if st.button("🗑️ Excluir definitivamente", key=f"del_prof_{row['id']}"):
                        st.session_state.pending_delete_prof = row["id"]

# -----------------------------
# 12) Funções de gráfico colorido (por categoria)
# -----------------------------
def plot_bar_counts(series: pd.Series, title: str, max_bars: int = 30, palette: str = "tab20"):
    """Plota barras com cores diferentes por categoria (top N)."""
    if series is None or series.empty:
        st.info("📭 Sem dados para o gráfico.")
        return
    series = series.sort_values(ascending=False).head(max_bars)
    labels = series.index.astype(str).tolist()
    values = series.values.astype(int)

    # Paleta
    cmap = cm.get_cmap(palette, len(labels))
    colors_list = [cmap(i) for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(min(12, 1 + 0.45*len(labels)), 5), dpi=120)
    bars = ax.bar(labels, values, color=colors_list, edgecolor="#10131a", linewidth=0.6)
    ax.set_title(title, color="#FFFFFF", fontsize=12, pad=12)
    ax.set_ylabel("Quantidade", color="#FFFFFF")
    ax.set_xticklabels(labels, rotation=45, ha="right", color="#E9ECF2")
    ax.set_yticks(ax.get_yticks())
    ax.set_yticklabels([int(t) for t in ax.get_yticks()], color="#E9ECF2")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#555a66")
    ax.spines["bottom"].set_color("#555a66")
    ax.set_facecolor("#0F1116")
    fig.patch.set_facecolor("#0F1116")

    # Valores nas barras
    for rect in bars:
        height = rect.get_height()
        if height > 0:
            ax.text(rect.get_x() + rect.get_width()/2., 1.02*height,
                    f"{int(height)}", ha='center', va='bottom', color="#FFFFFF", fontsize=8)
    st.pyplot(fig, clear_figure=True)

# -----------------------------
# 13) ABA 📈 Relatórios
# -----------------------------
elif st.session_state.aba_selecionada == "📈 Relatórios":
    st.header("📈 Relatórios por Espaço / Turma / Período")
    render_persisted_message()

    c1, c2, c3 = st.columns(3)
    with c1:
        data_inicio = st.date_input("Início:", datetime.now().date() - timedelta(days=7))
    with c2:
        data_fim = st.date_input("Fim:", datetime.now().date() + timedelta(days=7))
    with c3:
        status_filtro = st.selectbox("Status:", ["Todos", "ATIVO", "CANCELADO", "EXCLUIDO_GESTAO"], index=0)

    if st.button("📊 Gerar"):
        df = carregar_agendamentos_filtrado(
            data_inicio.strftime("%Y-%m-%d"),
            data_fim.strftime("%Y-%m-%d")
        )
        if status_filtro != "Todos":
            df = df[df["status"] == status_filtro]
        if df.empty:
            st.info("📭 Sem dados no período.")
        else:
            # Por Professor
            st.subheader("👨‍🏫 Quem mais usa (Professores)")
            por_prof = df.groupby("professor_nome")["id"].count()
            plot_bar_counts(por_prof, "Uso por Professor", palette="tab20")

            colx, coly = st.columns(2)
            with colx:
                # Por Turma
                st.subheader("🎓 Turmas que mais usam")
                por_turma = df.groupby("turma")["id"].count()
                plot_bar_counts(por_turma, "Uso por Turma", palette="Set3")
            with coly:
                # Por Espaço
                st.subheader("📍 Espaços mais usados")
                por_espaco = df.groupby("espaco")["id"].count()
                plot_bar_counts(por_espaco, "Uso por Espaço", palette="tab20")

            # Por Dia da Semana
            st.subheader("🗓️ Por Dia da Semana")
            df["dia_semana"] = pd.to_datetime(df["data_agendamento"]).dt.day_name()
            por_dia = df.groupby("dia_semana")["id"].count()
            # Ordena dias: Monday..Sunday
            ordem = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            por_dia = por_dia.reindex(ordem).dropna()
            plot_bar_counts(por_dia, "Uso por Dia da Semana", palette="tab20")

            st.subheader("📄 Tabela detalhada")
            st.dataframe(df[['data_agendamento','horario','espaco','turma','professor_nome','disciplina','prioridade','status']], use_container_width=True, hide_index=True)

# -----------------------------
# 14) ABA 🧹 Manutenção (apenas Gestão com senha)
# -----------------------------
elif st.session_state.aba_selecionada == "🧹 Manutenção":
    st.header("🧹 Manutenção / Limpeza de Agendamentos")
    render_persisted_message()

    if not st.session_state.gestao_logado:
        st.warning("🔒 Acesso restrito à Gestão (informe a senha na aba ⚙️ Gestão).")
    else:
        st.info("Remove **definitivamente** CANCELADO/EXCLUIDO_GESTAO anteriores à data de corte.")
        colx1, colx2 = st.columns(2)
        with colx1:
            dias = st.number_input("Remover registros anteriores a (dias):", min_value=7, max_value=3650, value=180, step=1)
        with colx2:
            st.caption("Modo: DELETE definitivo")

        if st.button("🧹 Executar limpeza agora"):
            cutoff = (datetime.now().date() - timedelta(days=int(dias))).strftime("%Y-%m-%d")
            try:
                base = f"{SUPABASE_URL}/rest/v1/agendamentos?status=in.(CANCELADO,EXCLUIDO_GESTAO)&data_agendamento=lt.{cutoff}"
                r = requests.delete(base, headers=HEADERS, timeout=20)
                if r.status_code in (200, 204):
                    notify('success', f"✅ Limpeza concluída (corte: {cutoff}).", toast=True, persist=True)
                else:
                    notify('error', f"Erro na limpeza: {r.status_code} - {r.text}", toast=True, persist=False)
            except Exception as e:
                notify('error', f"Falha na limpeza: {e}", toast=True, persist=False)

# -----------------------------
# 15) Rodapé
# -----------------------------
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#b8bdc7;font-size:0.9rem'>Sistema de Agendamento • Streamlit + Supabase (sem login p/ professor) • Tema vermelho</div>",
    unsafe_allow_html=True,
)