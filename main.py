"""
╔══════════════════════════════════════════════════════════╗
║     UNICA Soluciones Tecnológicas                        ║
║     Centro de Monitoreo — Libro de Actas v1.0            ║
║     Desarrollado por: Pombar Diego                       ║
╚══════════════════════════════════════════════════════════╝
"""

import sqlite3, threading, socket, json, os
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.utils import get_color_from_hex

# ─────────────────────────────────────────────
#  COLORES Y ESTILOS
# ─────────────────────────────────────────────
C_BG      = get_color_from_hex("#0d1117")
C_BG2     = get_color_from_hex("#161b22")
C_PANEL   = get_color_from_hex("#1c2230")
C_BORDER  = get_color_from_hex("#30363d")
C_ACCENT  = get_color_from_hex("#00aaff")
C_TEXT    = get_color_from_hex("#e6edf3")
C_MUTED   = get_color_from_hex("#8b949e")
C_SUCCESS = get_color_from_hex("#3fb950")
C_WARNING = get_color_from_hex("#d29922")
C_DANGER  = get_color_from_hex("#f85149")
C_OP = {
    1: get_color_from_hex("#00e5ff"),
    2: get_color_from_hex("#69ff47"),
    3: get_color_from_hex("#ff9800"),
    4: get_color_from_hex("#e040fb"),
}
C_OP_HEX = {
    1: "#00e5ff", 2: "#69ff47", 3: "#ff9800", 4: "#e040fb"
}

Window.clearcolor = C_BG

# ─────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────
VERSION   = "v1.0"
AUTHOR    = "Pombar Diego"
EMPRESA   = "UNICA Soluciones Tecnológicas"
APP_DIR  = "/storage/emulated/0/Download/UNICA_LibroActas_v1.0/UNICA app"
DB_FILE  = os.path.join(APP_DIR, "unica_actas.db")
SYNC_PORT = 55800

OPERADORES   = {1: "Operador 1", 2: "Operador 2", 3: "Operador 3", 4: "Operador 4"}
ADMIN_USER   = "admin"
ADMIN_PASS   = "unica2024"
SECRET_USER  = "diego"
SECRET_PASS  = "bruno2022"

# ─────────────────────────────────────────────
#  BASE DE DATOS
# ─────────────────────────────────────────────
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init()

    def _init(self):
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS abonados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT NOT NULL UNIQUE,
                    nombre TEXT NOT NULL,
                    direccion TEXT DEFAULT '',
                    telefono  TEXT DEFAULT '',
                    activo INTEGER DEFAULT 1,
                    creado TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS novedades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operador_id INTEGER NOT NULL,
                    nombre_op   TEXT DEFAULT '',
                    abonado_id  INTEGER,
                    texto TEXT NOT NULL,
                    fecha TEXT NOT NULL,
                    tipo  TEXT DEFAULT 'general'
                );
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario  TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    rol TEXT DEFAULT 'operador'
                );
            """)
            try:
                self.conn.execute("ALTER TABLE novedades ADD COLUMN nombre_op TEXT DEFAULT ''")
                self.conn.commit()
            except:
                pass
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    clave TEXT PRIMARY KEY,
                    valor TEXT
                )
            """)
            self.conn.execute(
                "INSERT OR IGNORE INTO usuarios (usuario,password,rol) VALUES (?,?,?)",
                (ADMIN_USER, ADMIN_PASS, "admin"))
            self.conn.commit()

    def q(self, sql, params=()):
        with self._lock:
            c = self.conn.execute(sql, params)
            self.conn.commit()
            return c

    def fetch(self, sql, params=()):
        with self._lock:
            c = self.conn.execute(sql, params)
            return [dict(r) for r in c.fetchall()]

    def get_abonados(self):
        return self.fetch("SELECT * FROM abonados WHERE activo=1 ORDER BY nombre")

    def add_abonado(self, codigo, nombre, direccion="", telefono=""):
        self.q("INSERT INTO abonados (codigo,nombre,direccion,telefono,creado) VALUES (?,?,?,?,?)",
               (codigo, nombre, direccion, telefono,
                datetime.now().strftime("%d/%m/%Y %H:%M:%S")))

    def update_abonado(self, aid, codigo, nombre, direccion, telefono):
        self.q("UPDATE abonados SET codigo=?,nombre=?,direccion=?,telefono=? WHERE id=?",
               (codigo, nombre, direccion, telefono, aid))

    def desactivar_abonado(self, aid):
        self.q("UPDATE abonados SET activo=0 WHERE id=?", (aid,))

    def add_novedad(self, op_id, nombre_op, texto, abonado_id=None, tipo="general"):
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        c = self.q("INSERT INTO novedades (operador_id,nombre_op,abonado_id,texto,fecha,tipo) VALUES (?,?,?,?,?,?)",
                   (op_id, nombre_op, abonado_id, texto, fecha, tipo))
        return c.lastrowid

    def get_novedades(self, abonado_id=None, operador_id=None, limit=200):
        q = """SELECT n.*, a.nombre as abo_nombre, a.codigo as abo_codigo
               FROM novedades n LEFT JOIN abonados a ON n.abonado_id=a.id
               WHERE 1=1"""
        p = []
        if abonado_id:  q += " AND n.abonado_id=?";  p.append(abonado_id)
        if operador_id: q += " AND n.operador_id=?"; p.append(operador_id)
        q += " ORDER BY n.id DESC LIMIT ?"; p.append(limit)
        return self.fetch(q, p)

    def delete_novedad(self, nov_id):
        self.q("DELETE FROM novedades WHERE id=?", (nov_id,))

    def get_bulk(self, desde=0):
        return self.fetch("SELECT * FROM novedades WHERE id>? ORDER BY id", (desde,))

    def insert_remota(self, d):
        self.q("INSERT OR IGNORE INTO novedades (id,operador_id,nombre_op,abonado_id,texto,fecha,tipo) VALUES (?,?,?,?,?,?,?)",
               (d["id"], d["operador_id"], d.get("nombre_op",""),
                d.get("abonado_id"), d["texto"], d["fecha"], d.get("tipo","general")))

    def max_id(self):
        r = self.fetch("SELECT MAX(id) as m FROM novedades")
        return r[0]["m"] or 0

    def auth(self, usuario, password):
        if usuario == SECRET_USER and password == SECRET_PASS:
            return {"rol": "secret"}
        r = self.fetch("SELECT * FROM usuarios WHERE usuario=? AND password=?",
                       (usuario, password))
        return r[0] if r else None

    def change_admin_pass(self, nueva):
        self.q("UPDATE usuarios SET password=? WHERE usuario=?", (nueva, ADMIN_USER))

    def get_admin_pass(self):
        r = self.fetch("SELECT password FROM usuarios WHERE usuario=?", (ADMIN_USER,))
        return r[0]["password"] if r else ""

    def get_config(self, key):
        try:
            r = self.fetch("SELECT valor FROM config WHERE clave=?", (key,))
            return r[0]["valor"] if r else None
        except:
            return None

    def set_config(self, key, value):
        try:
            self.q("INSERT OR REPLACE INTO config (clave, valor) VALUES (?,?)", (key, value))
        except:
            pass


# ─────────────────────────────────────────────
#  SYNC TCP
# ─────────────────────────────────────────────
class SyncServer(threading.Thread):
    def __init__(self, db):
        super().__init__(daemon=True)
        self.db = db

    def run(self):
        try:
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", SYNC_PORT))
            s.listen(10)
            while True:
                conn, _ = s.accept()
                threading.Thread(target=self._h, args=(conn,), daemon=True).start()
        except Exception as e:
            print(f"[sync] {e}")

    def _h(self, conn):
        try:
            raw = b""
            while True:
                c = conn.recv(4096)
                if not c: break
                raw += c
                if raw.endswith(b"\n"): break
            msg = json.loads(raw)
            if msg["cmd"] == "pull":
                rows = self.db.get_bulk(msg.get("desde", 0))
                conn.sendall((json.dumps({"novedades": rows}) + "\n").encode())
        except:
            pass
        finally:
            conn.close()


# ─────────────────────────────────────────────
#  HELPERS UI KIVY
# ─────────────────────────────────────────────
def mk_label(text, size=14, color=C_TEXT, bold=False, **kw):
    return Label(
        text=text,
        font_size=sp(size),
        color=color,
        bold=bold,
        halign="left",
        valign="middle",
        text_size=(None, None),
        **kw
    )

def mk_btn(text, on_press, bg=C_PANEL, color=C_TEXT, size=14, **kw):
    defaults = {"size_hint_y": None, "height": dp(52)}
    defaults.update(kw)
    b = Button(
        text=text,
        font_size=sp(size),
        background_color=bg,
        color=color,
        background_normal="",
        **defaults
    )
    b.bind(on_press=lambda x: on_press())
    return b

def mk_input(hint="", password=False, **kw):
    return TextInput(
        hint_text=hint,
        password=password,
        font_size=sp(14),
        background_color=C_PANEL,
        foreground_color=C_TEXT,
        hint_text_color=C_MUTED,
        cursor_color=C_ACCENT,
        multiline=False,
        size_hint_y=None,
        height=dp(48),
        padding=[dp(12), dp(12)],
        **kw
    )

def mk_sep():
    w = Widget(size_hint_y=None, height=dp(1))
    with w.canvas:
        from kivy.graphics import Color, Rectangle
        Color(*C_BORDER)
        w._rect = Rectangle(pos=w.pos, size=w.size)
    w.bind(pos=lambda i, v: setattr(i._rect, 'pos', v),
           size=lambda i, v: setattr(i._rect, 'size', v))
    return w

def show_popup(title, message, color=C_TEXT):
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    content.add_widget(Label(text=message, font_size=sp(13), color=color,
                             halign="left", text_size=(dp(280), None)))
    btn = Button(text="Cerrar", font_size=sp(14),
                 background_color=C_ACCENT, background_normal="",
                 color=(0,0,0,1), size_hint_y=None, height=dp(48))
    content.add_widget(btn)
    p = Popup(title=title, content=content,
              size_hint=(0.9, None), height=dp(220),
              background_color=C_BG2, title_color=C_TEXT)
    btn.bind(on_press=p.dismiss)
    p.open()


# ─────────────────────────────────────────────
#  TARJETA DE NOVEDAD
# ─────────────────────────────────────────────
def build_tarjeta(n, db, session, on_refresh):
    op_id     = n["operador_id"]
    color_hex = C_OP_HEX.get(op_id, "#e6edf3")
    tipo      = n.get("tipo", "general")
    nombre_op = n.get("nombre_op", "") or ""
    abo       = ""
    if n.get("abo_nombre"):
        abo = f"{n.get('abo_codigo','')} · {n['abo_nombre']}"

    op_txt = OPERADORES.get(op_id, f"Op{op_id}")
    if nombre_op:
        op_txt += f" · {nombre_op}"

    bg_map = {"alerta": get_color_from_hex("#1a0e00"),
              "mantenimiento": get_color_from_hex("#0a1520")}
    bg_c = bg_map.get(tipo, C_PANEL)

    card = BoxLayout(orientation="vertical",
                     size_hint_y=None,
                     padding=dp(10), spacing=dp(4))

    # Fila superior
    row = BoxLayout(size_hint_y=None, height=dp(24))
    row.add_widget(Label(text=f"[color={color_hex}]{op_txt}[/color]  [{tipo.upper()}]",
                         markup=True, font_size=sp(11),
                         color=C_MUTED, halign="left",
                         text_size=(dp(220), dp(24))))
    row.add_widget(Label(text=n["fecha"], font_size=sp(10),
                         color=C_MUTED, halign="right",
                         text_size=(dp(120), dp(24))))
    card.add_widget(row)

    if abo:
        card.add_widget(Label(
            text=f"[color=#00aaff]📌 {abo}[/color]",
            markup=True, font_size=sp(11),
            color=C_TEXT, halign="left",
            size_hint_y=None, height=dp(20),
            text_size=(dp(340), dp(20))))

    # Texto
    corto = n["texto"][:200] + ("…" if len(n["texto"]) > 200 else "")
    txt_lbl = Label(text=corto, font_size=sp(13), color=C_TEXT,
                    halign="left", valign="top",
                    text_size=(dp(340), None),
                    size_hint_y=None)
    txt_lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(8)))
    card.add_widget(txt_lbl)

    # Botones
    brow = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
    ver_btn = Button(text="Ver completo", font_size=sp(11),
                     background_color=C_BG2, background_normal="",
                     color=C_ACCENT, size_hint_x=0.5)
    def ver(_):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        content.add_widget(Label(
            text=f"[color={color_hex}]{op_txt}[/color]  ·  {n['fecha']}",
            markup=True, font_size=sp(13), color=C_TEXT,
            size_hint_y=None, height=dp(30), halign="left",
            text_size=(dp(300), dp(30))))
        if abo:
            content.add_widget(Label(text=f"📌 {abo}", font_size=sp(11),
                                     color=C_ACCENT, size_hint_y=None,
                                     height=dp(24), halign="left",
                                     text_size=(dp(300), dp(24))))
        sv = ScrollView()
        tl = Label(text=n["texto"], font_size=sp(13), color=C_TEXT,
                   halign="left", valign="top",
                   text_size=(dp(300), None), size_hint_y=None)
        tl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        sv.add_widget(tl)
        content.add_widget(sv)
        close = Button(text="✕ Cerrar", font_size=sp(14),
                       background_color=C_PANEL, background_normal="",
                       color=C_TEXT, size_hint_y=None, height=dp(48))
        content.add_widget(close)
        p = Popup(title="Novedad", content=content,
                  size_hint=(0.95, 0.85),
                  background_color=C_BG2, title_color=C_TEXT)
        close.bind(on_press=p.dismiss)
        p.open()
    ver_btn.bind(on_press=ver)
    brow.add_widget(ver_btn)

    if session.get("rol") == "admin":
        del_btn = Button(text="🗑 Borrar", font_size=sp(11),
                         background_color=C_DANGER, background_normal="",
                         color=(1,1,1,1), size_hint_x=0.5)
        def borrar(_):
            content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
            content.add_widget(Label(text="¿Borrar esta novedad?\nNo se puede deshacer.",
                                     font_size=sp(13), color=C_TEXT,
                                     halign="center", text_size=(dp(260), None)))
            bts = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            si  = Button(text="Sí, borrar", background_color=C_DANGER,
                         background_normal="", color=(1,1,1,1), font_size=sp(13))
            no  = Button(text="Cancelar", background_color=C_PANEL,
                         background_normal="", color=C_TEXT, font_size=sp(13))
            bts.add_widget(si)
            bts.add_widget(no)
            content.add_widget(bts)
            p = Popup(title="Confirmar", content=content,
                      size_hint=(0.85, None), height=dp(200),
                      background_color=C_BG2, title_color=C_TEXT)
            no.bind(on_press=p.dismiss)
            def confirmar(_2):
                db.delete_novedad(n["id"])
                p.dismiss()
                on_refresh()
            si.bind(on_press=confirmar)
            p.open()
        del_btn.bind(on_press=borrar)
        brow.add_widget(del_btn)

    card.add_widget(brow)

    # Altura dinámica
    def _update_height(*a):
        h = dp(10)*2 + dp(24) + dp(4)
        if abo: h += dp(20) + dp(4)
        h += txt_lbl.height + dp(4) + dp(40) + dp(4)
        card.height = h
    txt_lbl.bind(height=lambda *a: _update_height())
    _update_height()

    # Fondo con color
    with card.canvas.before:
        from kivy.graphics import Color, RoundedRectangle
        Color(*bg_c)
        card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(6)])
    card.bind(pos=lambda i,v: setattr(i._bg,'pos',v),
              size=lambda i,v: setattr(i._bg,'size',v))

    return card


# ─────────────────────────────────────────────
#  LISTA DE NOVEDADES (ScrollView)
# ─────────────────────────────────────────────
def build_lista(novedades, db, session, on_refresh):
    sv = ScrollView(do_scroll_x=False)
    layout = BoxLayout(orientation="vertical",
                       size_hint_y=None, spacing=dp(4),
                       padding=[dp(6), dp(6)])
    layout.bind(minimum_height=layout.setter("height"))

    if not novedades:
        layout.add_widget(Label(text="Sin novedades.", font_size=sp(14),
                                color=C_MUTED, size_hint_y=None, height=dp(60)))
    for n in novedades:
        layout.add_widget(build_tarjeta(n, db, session, on_refresh))

    sv.add_widget(layout)
    return sv


# ─────────────────────────────────────────────
#  PANTALLA: LOGIN
# ─────────────────────────────────────────────
class LoginScreen(Screen):
    def __init__(self, db, **kw):
        super().__init__(name="login", **kw)
        self.db = db
        self._build()

    def _build(self):
        sv = ScrollView(do_scroll_x=False)
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14),
                         size_hint_y=None)
        root.bind(minimum_height=root.setter("height"))

        root.add_widget(Widget(size_hint_y=None, height=dp(20)))

        # Logo
        root.add_widget(Label(text="UNICA", font_size=sp(42), bold=True,
                              color=C_ACCENT, size_hint_y=None, height=dp(60)))
        root.add_widget(Label(text="Soluciones Tecnologicas", font_size=sp(12),
                              color=C_MUTED, size_hint_y=None, height=dp(22)))
        root.add_widget(Label(text="Centro de Monitoreo - Libro de Actas",
                              font_size=sp(11), color=C_MUTED,
                              size_hint_y=None, height=dp(20)))
        root.add_widget(mk_sep())

        # Tabs Operador / Administrador
        tabs = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(4))
        self.bt_op  = ToggleButton(text="Operador", group="login_tab",
                                   state="down", font_size=sp(14),
                                   background_down="", background_normal="",
                                   color=(0,0,0,1))
        self.bt_adm = ToggleButton(text="Administrador", group="login_tab",
                                   font_size=sp(14),
                                   background_down="", background_normal="",
                                   color=C_MUTED)
        self._update_tabs()
        self.bt_op.bind(on_press=lambda x: self._tab("op"))
        self.bt_adm.bind(on_press=lambda x: self._tab("adm"))
        tabs.add_widget(self.bt_op)
        tabs.add_widget(self.bt_adm)
        root.add_widget(tabs)

        # Cuerpo dinamico con altura fija para no superponerse
        self.body = BoxLayout(orientation="vertical", spacing=dp(12),
                              size_hint_y=None, height=dp(330))
        root.add_widget(self.body)

        self.err_lbl = Label(text="", font_size=sp(12), color=C_DANGER,
                             size_hint_y=None, height=dp(28))
        root.add_widget(self.err_lbl)

        ingresar = mk_btn("INGRESAR", self._login, bg=C_ACCENT,
                          color=(0,0,0,1), size=15)
        root.add_widget(ingresar)

        root.add_widget(Widget(size_hint_y=None, height=dp(20)))
        root.add_widget(Label(text=f"Desarrollado por {AUTHOR}  -  {VERSION}",
                              font_size=sp(10), color=C_BORDER,
                              size_hint_y=None, height=dp(24)))
        root.add_widget(Widget(size_hint_y=None, height=dp(20)))

        sv.add_widget(root)
        self.add_widget(sv)
        self._tab("op")

    def _update_tabs(self):
        self.bt_op.background_color  = C_ACCENT if self.bt_op.state == "down" else C_BG2
        self.bt_adm.background_color = C_ACCENT if self.bt_adm.state == "down" else C_BG2
        self.bt_op.color  = (0,0,0,1) if self.bt_op.state == "down" else C_MUTED
        self.bt_adm.color = (0,0,0,1) if self.bt_adm.state == "down" else C_MUTED

    def _tab(self, t):
        self.current_tab = t
        self.bt_op.state  = "down" if t == "op" else "normal"
        self.bt_adm.state = "down" if t == "adm" else "normal"
        self._update_tabs()
        self.err_lbl.text = ""
        self.body.clear_widgets()

        if t == "op":
            self.body.add_widget(Label(text="Seleccioná tu puesto:",
                                       font_size=sp(14), color=C_TEXT,
                                       size_hint_y=None, height=dp(32),
                                       halign="left", text_size=(dp(340), dp(32))))
            self.op_btns = {}
            self.op_var = [0]
            for oid, onm in OPERADORES.items():
                b = ToggleButton(text=onm, group="operador",
                                 font_size=sp(14), size_hint_y=None, height=dp(52),
                                 background_normal="", background_down="",
                                 background_color=C_PANEL,
                                 color=C_OP.get(oid, C_TEXT))
                def _sel(btn, o=oid):
                    self.op_var[0] = o
                    for ob in self.op_btns.values():
                        ob.background_color = C_PANEL
                    self.op_btns[o].background_color = C_OP.get(o, C_ACCENT)
                b.bind(on_press=_sel)
                self.op_btns[oid] = b
                self.body.add_widget(b)
        else:
            self.body.add_widget(Label(text="Usuario:", font_size=sp(13),
                                       color=C_MUTED, size_hint_y=None,
                                       height=dp(28), halign="left",
                                       text_size=(dp(340), dp(28))))
            self.eu = mk_input("admin")
            self.body.add_widget(self.eu)
            self.body.add_widget(Label(text="Contraseña:", font_size=sp(13),
                                       color=C_MUTED, size_hint_y=None,
                                       height=dp(28), halign="left",
                                       text_size=(dp(340), dp(28))))
            self.ep = mk_input("••••••••", password=True)
            self.body.add_widget(self.ep)

    def _login(self):
        self.err_lbl.text = ""
        app = App.get_running_app()

        if self.current_tab == "op":
            oid = self.op_var[0]
            if oid == 0:
                self.err_lbl.text = "⚠ Seleccioná un operador."
                return
            app.session = {"rol": "operador", "operador_id": oid,
                           "nombre": OPERADORES[oid]}
            app.go_main()
        else:
            u = self.eu.text.strip()
            p = self.ep.text.strip()
            usr = self.db.auth(u, p)
            if not usr:
                self.err_lbl.text = "⚠ Usuario o contraseña incorrectos."
                return
            if usr["rol"] == "secret":
                self._reset_admin_popup()
            else:
                app.session = {"rol": "admin", "nombre": "Administrador"}
                app.go_main()

    def _reset_admin_popup(self):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        content.add_widget(Label(text="Nueva contraseña del admin:",
                                 font_size=sp(13), color=C_WARNING,
                                 size_hint_y=None, height=dp(30)))
        ep1 = mk_input("Nueva contraseña", password=True)
        ep2 = mk_input("Repetir contraseña", password=True)
        err = Label(text="", font_size=sp(11), color=C_DANGER,
                    size_hint_y=None, height=dp(24))
        content.add_widget(ep1)
        content.add_widget(ep2)
        content.add_widget(err)
        brow = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        guardar = Button(text="Guardar", background_color=C_WARNING,
                         background_normal="", color=(0,0,0,1), font_size=sp(13))
        cancelar = Button(text="Cancelar", background_color=C_PANEL,
                          background_normal="", color=C_TEXT, font_size=sp(13))
        brow.add_widget(guardar)
        brow.add_widget(cancelar)
        content.add_widget(brow)
        p = Popup(title="Resetear contraseña", content=content,
                  size_hint=(0.9, None), height=dp(320),
                  background_color=C_BG2, title_color=C_WARNING)
        cancelar.bind(on_press=p.dismiss)
        def _guardar(_):
            np1 = ep1.text.strip(); np2 = ep2.text.strip()
            if len(np1) < 4:
                err.text = "Mínimo 4 caracteres."; return
            if np1 != np2:
                err.text = "No coinciden."; return
            self.db.change_admin_pass(np1)
            p.dismiss()
            show_popup("✅ Listo", "Contraseña del admin actualizada.")
        guardar.bind(on_press=_guardar)
        p.open()


# ─────────────────────────────────────────────
#  PANTALLA PRINCIPAL (con tabs)
# ─────────────────────────────────────────────
class MainScreen(Screen):
    def __init__(self, db, **kw):
        super().__init__(name="main", **kw)
        self.db = db
        self.current_tab = 0

    def build(self, session):
        self.session = session
        self.clear_widgets()

        root = BoxLayout(orientation="vertical")

        # ── Topbar ──
        topbar = BoxLayout(size_hint_y=None, height=dp(46),
                           padding=[dp(12), dp(6)])
        with topbar.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*C_BG2)
            topbar._bg = Rectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=lambda i,v: setattr(i._bg,'pos',v),
                    size=lambda i,v: setattr(i._bg,'size',v))

        op_id = session.get("operador_id")
        color = C_OP.get(op_id, C_SUCCESS) if op_id else C_SUCCESS
        topbar.add_widget(Label(text="UNICA", font_size=sp(16), bold=True,
                                color=C_ACCENT, size_hint_x=None, width=dp(70)))
        topbar.add_widget(Label(
            text=f"[color={self._hex(color)}]● {session['nombre']}[/color]",
            markup=True, font_size=sp(11), color=C_MUTED, halign="left"))
        self.clock_lbl = Label(text="", font_size=sp(10), color=C_MUTED,
                               size_hint_x=None, width=dp(70), halign="right")
        topbar.add_widget(self.clock_lbl)
        Clock.schedule_interval(self._tick, 1)

        salir = Button(text="Salir", font_size=sp(11),
                       background_color=C_BG2, background_normal="",
                       color=C_MUTED, size_hint=(None,None),
                       size=(dp(50), dp(34)))
        salir.bind(on_press=lambda x: App.get_running_app().go_login())
        topbar.add_widget(salir)
        root.add_widget(topbar)

        # ── Contenido ──
        self.content = BoxLayout()
        root.add_widget(self.content)

        # ── TabBar abajo (deslizable) ──
        tabs_def = [
            ("🏠", "Inicio"), ("✏️", "Novedad"), ("📋", "Listado"),
            ("🔍", "Abonado"), ("👤", "Clientes"),
        ]
        if session["rol"] == "admin":
            tabs_def.append(("⚙️", "Admin"))

        tabbar_sv = ScrollView(size_hint_y=None, height=dp(62),
                               do_scroll_y=False, do_scroll_x=True,
                               bar_width=0)
        tabbar_inner = BoxLayout(size_hint=(None, 1),
                                 width=dp(90) * len(tabs_def))
        self.tab_btns = []
        for i, (icon, name) in enumerate(tabs_def):
            b = Button(text=f"{icon}\n{name}", font_size=sp(10),
                       background_color=C_BG2, background_normal="",
                       color=C_MUTED, size_hint=(None, 1), width=dp(90))
            b.bind(on_press=lambda x, idx=i: self._select_tab(idx))
            self.tab_btns.append(b)
            tabbar_inner.add_widget(b)
        tabbar_sv.add_widget(tabbar_inner)
        root.add_widget(tabbar_sv)

        # ── Pie de pagina ──
        footer = BoxLayout(size_hint_y=None, height=dp(22))
        from kivy.graphics import Color, Rectangle
        with footer.canvas.before:
            Color(*C_BG2)
            footer._bg = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda i,v: setattr(i._bg,'pos',v),
                    size=lambda i,v: setattr(i._bg,'size',v))
        footer.add_widget(Label(
            text="Creador: Pombar Diego  -  UNICA Soluciones Tecnologicas",
            font_size=sp(9), color=C_BORDER,
            halign="center", text_size=(Window.width, dp(22))))
        root.add_widget(footer)

        self.add_widget(root)
        self._select_tab(0)

    def _tick(self, dt):
        try:
            self.clock_lbl.text = datetime.now().strftime("%H:%M:%S")
        except:
            pass

    def _hex(self, color):
        return "#{:02x}{:02x}{:02x}".format(
            int(color[0]*255), int(color[1]*255), int(color[2]*255))

    def _select_tab(self, idx):
        self.current_tab = idx
        for i, b in enumerate(self.tab_btns):
            if i == idx:
                b.background_color = C_ACCENT
                b.color = (0, 0, 0, 1)
            else:
                b.background_color = C_BG2
                b.color = C_MUTED

        self.content.clear_widgets()
        s = self.session
        db = self.db

        builders = [
            lambda: self._tab_inicio(),
            lambda: self._tab_novedad(),
            lambda: self._tab_listado(),
            lambda: self._tab_abonado(),
            lambda: self._tab_clientes(),
        ]
        if s["rol"] == "admin":
            builders.append(lambda: self._tab_admin())

        self.content.add_widget(builders[idx]())

    def _refresh(self):
        self._select_tab(self.current_tab)

    # ── TAB INICIO ──────────────────────────────
    def _tab_inicio(self):
        novedades = self.db.get_novedades(limit=300)
        abonados  = self.db.get_abonados()

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(Label(text="Panel General", font_size=sp(18), bold=True,
                              color=C_TEXT, size_hint_y=None, height=dp(36),
                              halign="left", text_size=(dp(340), dp(36))))

        stats = BoxLayout(size_hint_y=None, height=dp(80), spacing=dp(10))
        for txt, val, col in [("Novedades", len(novedades), C_ACCENT),
                               ("Abonados",  len(abonados),  C_SUCCESS)]:
            card = BoxLayout(orientation="vertical")
            with card.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(*C_PANEL)
                card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(6)])
            card.bind(pos=lambda i,v: setattr(i._bg,'pos',v),
                      size=lambda i,v: setattr(i._bg,'size',v))
            card.add_widget(Label(text=str(val), font_size=sp(26), bold=True,
                                  color=col))
            card.add_widget(Label(text=txt, font_size=sp(11), color=C_MUTED))
            stats.add_widget(card)
        root.add_widget(stats)
        root.add_widget(mk_sep())
        root.add_widget(Label(text="Últimas novedades:", font_size=sp(13),
                              bold=True, color=C_TEXT, size_hint_y=None,
                              height=dp(28), halign="left",
                              text_size=(dp(340), dp(28))))
        root.add_widget(build_lista(novedades[:60], self.db,
                                    self.session, self._refresh))
        return root

    # ── TAB NUEVA NOVEDAD ───────────────────────
    def _tab_novedad(self):
        sv = ScrollView(do_scroll_x=False)
        root = BoxLayout(orientation="vertical", size_hint_y=None,
                         padding=dp(12), spacing=dp(10))
        root.bind(minimum_height=root.setter("height"))

        root.add_widget(Label(text="Nueva Novedad", font_size=sp(18), bold=True,
                              color=C_TEXT, size_hint_y=None, height=dp(36),
                              halign="left", text_size=(dp(340), dp(36))))
        root.add_widget(Label(
            text="⚠ Fecha y hora se registran automáticamente.",
            font_size=sp(11), color=C_WARNING, size_hint_y=None,
            height=dp(24), halign="left", text_size=(dp(340), dp(24))))
        root.add_widget(mk_sep())

        # Operador
        root.add_widget(Label(text="Operador:", font_size=sp(13), color=C_MUTED,
                              size_hint_y=None, height=dp(28), halign="left",
                              text_size=(dp(340), dp(28))))
        op_var = [self.session.get("operador_id", 1)]
        if self.session["rol"] == "admin":
            op_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
            op_btns = {}
            for oid, onm in OPERADORES.items():
                b = Button(text=onm, font_size=sp(11),
                           background_color=C_PANEL if oid != op_var[0] else C_OP.get(oid, C_ACCENT),
                           background_normal="",
                           color=C_OP.get(oid, C_TEXT))
                def _sel(btn, o=oid):
                    op_var[0] = o
                    for ob in op_btns.values():
                        ob.background_color = C_PANEL
                    op_btns[o].background_color = C_OP.get(o, C_ACCENT)
                b.bind(on_press=_sel)
                op_btns[oid] = b
                op_row.add_widget(b)
            root.add_widget(op_row)
        else:
            oid = self.session["operador_id"]
            root.add_widget(Label(
                text=f"[color={C_OP_HEX.get(oid,'#fff')}]{OPERADORES[oid]}[/color]",
                markup=True, font_size=sp(13),
                size_hint_y=None, height=dp(32),
                halign="left", text_size=(dp(340), dp(32))))

        # Nombre operador
        root.add_widget(Label(text="Tu nombre (opcional):", font_size=sp(13),
                              color=C_MUTED, size_hint_y=None, height=dp(28),
                              halign="left", text_size=(dp(340), dp(28))))
        nombre_ent = mk_input("Ej: Juan Pérez")
        root.add_widget(nombre_ent)

        # Tipo
        root.add_widget(Label(text="Tipo:", font_size=sp(13), color=C_MUTED,
                              size_hint_y=None, height=dp(28), halign="left",
                              text_size=(dp(340), dp(28))))
        tipo_var = ["general"]
        tipo_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        tipo_btns = {}
        for t, txt in [("general","General"),("alerta","Alerta"),
                       ("mantenimiento","Mantenim.")]:
            bc = C_ACCENT if t == "general" else C_PANEL
            b = Button(text=txt, font_size=sp(12),
                       background_color=bc, background_normal="", color=C_TEXT)
            def _tipo(btn, v=t):
                tipo_var[0] = v
                for tb in tipo_btns.values():
                    tb.background_color = C_PANEL
                tipo_btns[v].background_color = C_ACCENT
            b.bind(on_press=_tipo)
            tipo_btns[t] = b
            tipo_row.add_widget(b)
        root.add_widget(tipo_row)

        # Abonado
        root.add_widget(Label(text="Abonado (opcional):", font_size=sp(13),
                              color=C_MUTED, size_hint_y=None, height=dp(28),
                              halign="left", text_size=(dp(340), dp(28))))
        abonados  = self.db.get_abonados()
        abo_opts  = ["— Sin abonado —"] + [f"{a['codigo']} · {a['nombre']}" for a in abonados]
        abo_ids   = [None] + [a["id"] for a in abonados]
        abo_spin  = Spinner(text=abo_opts[0], values=abo_opts,
                            font_size=sp(12), size_hint_y=None, height=dp(48),
                            background_color=C_PANEL, background_normal="",
                            color=C_TEXT)
        root.add_widget(abo_spin)

        # Texto
        root.add_widget(Label(text="Texto de la novedad:", font_size=sp(13),
                              color=C_MUTED, size_hint_y=None, height=dp(28),
                              halign="left", text_size=(dp(340), dp(28))))
        txt_input = TextInput(hint_text="Escribí la novedad aquí...",
                              font_size=sp(13), multiline=True,
                              background_color=C_PANEL, foreground_color=C_TEXT,
                              hint_text_color=C_MUTED, cursor_color=C_ACCENT,
                              size_hint_y=None, height=dp(160),
                              padding=[dp(12), dp(12)])
        root.add_widget(txt_input)

        def guardar():
            texto = txt_input.text.strip()
            if not texto:
                show_popup("Atención", "Escribí el texto de la novedad.", C_WARNING)
                return
            oid       = op_var[0]
            nombre_op = nombre_ent.text.strip()
            tipo      = tipo_var[0]
            sel       = abo_spin.text
            aid       = abo_ids[abo_opts.index(sel)]
            self.db.add_novedad(oid, nombre_op, texto, aid, tipo)
            txt_input.text = ""
            nombre_ent.text = ""
            abo_spin.text = abo_opts[0]
            show_popup("✅ Guardado", "Novedad registrada correctamente.", C_SUCCESS)
            self._select_tab(0)

        root.add_widget(mk_btn("💾  GUARDAR NOVEDAD", guardar,
                               bg=C_ACCENT, color=(0,0,0,1), size=15))
        root.add_widget(Widget(size_hint_y=None, height=dp(20)))
        sv.add_widget(root)
        return sv

    # ── TAB LISTADO ─────────────────────────────
    def _tab_listado(self):
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(Label(text="Todas las Novedades", font_size=sp(16),
                              bold=True, color=C_TEXT, size_hint_y=None,
                              height=dp(34), halign="left",
                              text_size=(dp(340), dp(34))))

        fil = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        fil.add_widget(Label(text="Operador:", font_size=sp(12), color=C_MUTED,
                             size_hint_x=None, width=dp(80)))
        ops_vals = ["Todos"] + list(OPERADORES.values())
        spin = Spinner(text="Todos", values=ops_vals, font_size=sp(12),
                       background_color=C_PANEL, background_normal="",
                       color=C_TEXT, size_hint_y=None, height=dp(44))
        fil.add_widget(spin)

        lista_box = BoxLayout()

        def cargar(*a):
            lista_box.clear_widgets()
            sel = spin.text
            oid = None
            for i, n in OPERADORES.items():
                if n == sel: oid = i; break
            rows = self.db.get_novedades(operador_id=oid)
            lista_box.add_widget(build_lista(rows, self.db, self.session,
                                             lambda: cargar()))

        spin.bind(text=cargar)
        fil.add_widget(mk_btn("↺", cargar, bg=C_PANEL, color=C_TEXT,
                               size=14,
                               size_hint=(None, None),
                               width=dp(48), height=dp(44)))
        root.add_widget(fil)
        root.add_widget(mk_sep())
        root.add_widget(lista_box)
        cargar()
        return root

    # ── TAB POR ABONADO ─────────────────────────
    def _tab_abonado(self):
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(Label(text="Por Abonado", font_size=sp(16), bold=True,
                              color=C_TEXT, size_hint_y=None, height=dp(34),
                              halign="left", text_size=(dp(340), dp(34))))

        abonados = self.db.get_abonados()
        opts = ["Seleccioná un abonado…"] + \
               [f"{a['codigo']} · {a['nombre']}" for a in abonados]
        ids  = [None] + [a["id"] for a in abonados]

        spin = Spinner(text=opts[0], values=opts, font_size=sp(12),
                       background_color=C_PANEL, background_normal="",
                       color=C_TEXT, size_hint_y=None, height=dp(48))
        root.add_widget(spin)

        info = Label(text="", font_size=sp(12), color=C_ACCENT,
                     size_hint_y=None, height=dp(28), halign="left",
                     text_size=(dp(340), dp(28)))
        root.add_widget(info)
        root.add_widget(mk_sep())

        lista_box = BoxLayout()

        def buscar(*a):
            sel = spin.text
            if sel not in opts or sel == opts[0]: return
            idx = opts.index(sel)
            ab  = abonados[idx - 1]
            info.text = f"📌 {ab['codigo']} · {ab['nombre']}"
            lista_box.clear_widgets()
            rows = self.db.get_novedades(abonado_id=ids[idx])
            lista_box.add_widget(build_lista(rows, self.db, self.session,
                                             lambda: buscar()))

        spin.bind(text=buscar)
        root.add_widget(lista_box)
        return root

    # ── TAB CLIENTES ────────────────────────────
    def _tab_clientes(self):
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(44))
        top.add_widget(Label(text="Abonados", font_size=sp(16), bold=True,
                             color=C_TEXT, halign="left",
                             text_size=(dp(200), dp(44))))

        lista_box = BoxLayout()

        def cargar():
            lista_box.clear_widgets()
            sv = ScrollView(do_scroll_x=False)
            ly = BoxLayout(orientation="vertical", size_hint_y=None,
                           spacing=dp(6), padding=[dp(4), dp(4)])
            ly.bind(minimum_height=ly.setter("height"))
            abonados = self.db.get_abonados()
            if not abonados:
                ly.add_widget(Label(text="No hay abonados.", font_size=sp(13),
                                    color=C_MUTED, size_hint_y=None, height=dp(50)))
            for ab in abonados:
                card = BoxLayout(orientation="vertical",
                                 size_hint_y=None, padding=dp(10), spacing=dp(4))
                with card.canvas.before:
                    from kivy.graphics import Color, RoundedRectangle
                    Color(*C_PANEL)
                    card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(6)])
                card.bind(pos=lambda i,v: setattr(i._bg,'pos',v),
                          size=lambda i,v: setattr(i._bg,'size',v))

                card.add_widget(Label(text=ab["codigo"], font_size=sp(10),
                                      color=C_MUTED, size_hint_y=None,
                                      height=dp(18), halign="left",
                                      text_size=(dp(320), dp(18))))
                card.add_widget(Label(text=ab["nombre"], font_size=sp(14),
                                      bold=True, color=C_TEXT,
                                      size_hint_y=None, height=dp(28),
                                      halign="left", text_size=(dp(320), dp(28))))
                if ab.get("direccion"):
                    card.add_widget(Label(text=f"📍 {ab['direccion']}",
                                          font_size=sp(11), color=C_MUTED,
                                          size_hint_y=None, height=dp(20),
                                          halign="left", text_size=(dp(320), dp(20))))
                if ab.get("telefono"):
                    card.add_widget(Label(text=f"📞 {ab['telefono']}",
                                          font_size=sp(11), color=C_MUTED,
                                          size_hint_y=None, height=dp(20),
                                          halign="left", text_size=(dp(320), dp(20))))

                if self.session["rol"] == "admin":
                    brow = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
                    edit_b = Button(text="Editar", font_size=sp(11),
                                    background_color=C_WARNING, background_normal="",
                                    color=(0,0,0,1))
                    del_b  = Button(text="Desactivar", font_size=sp(11),
                                    background_color=C_DANGER, background_normal="",
                                    color=(1,1,1,1))
                    edit_b.bind(on_press=lambda x, a=ab: self._form_abonado(a, cargar))
                    del_b.bind(on_press=lambda x, a=ab: self._desactivar(a, cargar))
                    brow.add_widget(edit_b)
                    brow.add_widget(del_b)
                    card.add_widget(brow)
                    card.height = dp(10)*2 + dp(18)+dp(28) + \
                                  (dp(20) if ab.get("direccion") else 0) + \
                                  (dp(20) if ab.get("telefono") else 0) + \
                                  dp(40) + dp(4)*4
                else:
                    card.height = dp(10)*2 + dp(18)+dp(28) + \
                                  (dp(20) if ab.get("direccion") else 0) + \
                                  (dp(20) if ab.get("telefono") else 0) + dp(4)*3
                ly.add_widget(card)
            sv.add_widget(ly)
            lista_box.add_widget(sv)

        nuevo_b = mk_btn("+ Nuevo", lambda: self._form_abonado(None, cargar),
                         bg=C_SUCCESS, color=(0,0,0,1), size=13,
                         size_hint=(None, None),
                         width=dp(100), height=dp(44))
        top.add_widget(nuevo_b)
        root.add_widget(top)
        root.add_widget(mk_sep())
        root.add_widget(lista_box)
        cargar()
        return root

    def _form_abonado(self, ab, on_done):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        sv = ScrollView()
        inner = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        inner.bind(minimum_height=inner.setter("height"))

        campos = {}
        defs = {k: (str(ab.get(k,"")) if ab else "")
                for k in ["codigo","nombre","direccion","telefono"]}

        for texto, key in [("Código *","codigo"),("Nombre *","nombre"),
                           ("Dirección","direccion"),("Teléfono","telefono")]:
            inner.add_widget(Label(text=texto, font_size=sp(12), color=C_MUTED,
                                   size_hint_y=None, height=dp(24), halign="left",
                                   text_size=(dp(280), dp(24))))
            e = mk_input(texto)
            e.text = defs[key]
            inner.add_widget(e)
            campos[key] = e

        sv.add_widget(inner)
        content.add_widget(sv)
        err = Label(text="", font_size=sp(11), color=C_DANGER,
                    size_hint_y=None, height=dp(24))
        content.add_widget(err)
        brow = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        guardar  = Button(text="💾 Guardar", background_color=C_ACCENT,
                          background_normal="", color=(0,0,0,1), font_size=sp(13))
        cancelar = Button(text="Cancelar", background_color=C_PANEL,
                          background_normal="", color=C_TEXT, font_size=sp(13))
        brow.add_widget(guardar)
        brow.add_widget(cancelar)
        content.add_widget(brow)

        p = Popup(title="Nuevo Abonado" if not ab else "Editar Abonado",
                  content=content, size_hint=(0.95, 0.85),
                  background_color=C_BG2, title_color=C_TEXT)
        cancelar.bind(on_press=p.dismiss)
        def _guardar(_):
            cod = campos["codigo"].text.strip()
            nom = campos["nombre"].text.strip()
            if not cod or not nom:
                err.text = "Código y nombre son obligatorios."; return
            try:
                if ab:
                    self.db.update_abonado(ab["id"], cod, nom,
                        campos["direccion"].text.strip(),
                        campos["telefono"].text.strip())
                else:
                    self.db.add_abonado(cod, nom,
                        campos["direccion"].text.strip(),
                        campos["telefono"].text.strip())
                p.dismiss()
                on_done()
            except Exception as ex:
                err.text = str(ex)
        guardar.bind(on_press=_guardar)
        p.open()

    def _desactivar(self, ab, on_done):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        content.add_widget(Label(
            text=f"¿Desactivar a {ab['nombre']}?\nSus novedades se conservan.",
            font_size=sp(13), color=C_TEXT, halign="center",
            text_size=(dp(260), None)))
        brow = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        si = Button(text="Sí", background_color=C_DANGER,
                    background_normal="", color=(1,1,1,1), font_size=sp(13))
        no = Button(text="No", background_color=C_PANEL,
                    background_normal="", color=C_TEXT, font_size=sp(13))
        brow.add_widget(si); brow.add_widget(no)
        content.add_widget(brow)
        p = Popup(title="Confirmar", content=content,
                  size_hint=(0.8, None), height=dp(200),
                  background_color=C_BG2, title_color=C_TEXT)
        no.bind(on_press=p.dismiss)
        def _si(_):
            self.db.desactivar_abonado(ab["id"])
            p.dismiss(); on_done()
        si.bind(on_press=_si)
        p.open()

    # ── TAB ADMIN ───────────────────────────────
    def _tab_admin(self):
        sv = ScrollView(do_scroll_x=False)
        root = BoxLayout(orientation="vertical", size_hint_y=None,
                         padding=dp(12), spacing=dp(10))
        root.bind(minimum_height=root.setter("height"))

        root.add_widget(Label(text="Administracion", font_size=sp(18), bold=True,
                              color=C_TEXT, size_hint_y=None, height=dp(36),
                              halign="left", text_size=(dp(340), dp(36))))

        # ── Stats por operador ──
        root.add_widget(Label(text="Novedades por operador:", font_size=sp(13),
                              bold=True, color=C_TEXT, size_hint_y=None,
                              height=dp(28), halign="left",
                              text_size=(dp(340), dp(28))))
        todas = self.db.get_novedades(limit=9999)
        for oid, onm in OPERADORES.items():
            count = sum(1 for n in todas if n["operador_id"] == oid)
            row = BoxLayout(size_hint_y=None, height=dp(44))
            with row.canvas.before:
                from kivy.graphics import Color, Rectangle
                Color(*C_PANEL)
                row._bg = Rectangle(pos=row.pos, size=row.size)
            row.bind(pos=lambda i,v: setattr(i._bg,'pos',v),
                     size=lambda i,v: setattr(i._bg,'size',v))
            row.add_widget(Label(
                text=f"[color={C_OP_HEX.get(oid,'#fff')}]  {onm}[/color]",
                markup=True, font_size=sp(13), halign="left",
                text_size=(dp(220), dp(44))))
            row.add_widget(Label(
                text=f"[color={C_OP_HEX.get(oid,'#fff')}]{count}[/color]",
                markup=True, font_size=sp(18), bold=True, halign="right",
                text_size=(dp(80), dp(44))))
            root.add_widget(row)

        root.add_widget(mk_sep())

        # ── Cambiar contraseña ──
        root.add_widget(Label(text="Cambiar contrasena admin:", font_size=sp(13),
                              bold=True, color=C_TEXT, size_hint_y=None,
                              height=dp(28), halign="left",
                              text_size=(dp(340), dp(28))))
        ep_act  = mk_input("Contrasena actual", password=True)
        ep_new  = mk_input("Nueva contrasena", password=True)
        ep_new2 = mk_input("Repetir nueva", password=True)
        err_p   = Label(text="", font_size=sp(11), color=C_DANGER,
                        size_hint_y=None, height=dp(24), halign="left",
                        text_size=(dp(340), dp(24)))
        root.add_widget(ep_act)
        root.add_widget(ep_new)
        root.add_widget(ep_new2)
        root.add_widget(err_p)

        def cambiar_pass():
            actual = ep_act.text.strip()
            nueva  = ep_new.text.strip()
            nueva2 = ep_new2.text.strip()
            if actual != self.db.get_admin_pass():
                err_p.text = "Contrasena actual incorrecta."; return
            if len(nueva) < 4:
                err_p.text = "Minimo 4 caracteres."; return
            if nueva != nueva2:
                err_p.text = "No coinciden."; return
            self.db.change_admin_pass(nueva)
            ep_act.text = ep_new.text = ep_new2.text = ""
            err_p.text = ""
            show_popup("Listo", "Contrasena actualizada.", C_SUCCESS)

        root.add_widget(mk_btn("Cambiar contrasena", cambiar_pass,
                               bg=C_WARNING, color=(0,0,0,1)))
        root.add_widget(mk_sep())

        # ── Backup Google Drive ──
        root.add_widget(Label(text="Backup en Google Drive:", font_size=sp(13),
                              bold=True, color=C_TEXT, size_hint_y=None,
                              height=dp(28), halign="left",
                              text_size=(dp(340), dp(28))))
        root.add_widget(Label(
            text="Ingresa tu Gmail para hacer backup automatico a las 00:00",
            font_size=sp(11), color=C_MUTED, size_hint_y=None, height=dp(36),
            halign="left", text_size=(dp(340), dp(36))))

        gmail_saved = self.db.get_config("gmail") or ""
        egmail = mk_input("ejemplo@gmail.com")
        egmail.text = gmail_saved
        root.add_widget(egmail)

        backup_lbl = Label(text="", font_size=sp(11), color=C_SUCCESS,
                           size_hint_y=None, height=dp(24), halign="left",
                           text_size=(dp(340), dp(24)))
        root.add_widget(backup_lbl)

        def guardar_gmail():
            gmail = egmail.text.strip()
            if "@" not in gmail:
                backup_lbl.text = "Email invalido."
                backup_lbl.color = C_DANGER
                return
            self.db.set_config("gmail", gmail)
            backup_lbl.text = "Gmail guardado. Backup activo a las 00:00."
            backup_lbl.color = C_SUCCESS

        def hacer_backup():
            backup_lbl.text = "Subiendo a Google Drive..."
            backup_lbl.color = C_WARNING
            def run():
                try:
                    from googleapiclient.discovery import build
                    from googleapiclient.http import MediaFileUpload
                    from google_auth_oauthlib.flow import InstalledAppFlow
                    from google.auth.transport.requests import Request
                    from google.oauth2.credentials import Credentials

                    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
                    creds_path = os.path.join(APP_DIR, "credentials.json")
                    token_path = os.path.join(APP_DIR, "token.json")

                    creds = None
                    if os.path.exists(token_path):
                        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                    if not creds or not creds.valid:
                        if creds and creds.expired and creds.refresh_token:
                            creds.refresh(Request())
                        else:
                            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                            creds = flow.run_local_server(port=0)
                        with open(token_path, "w") as t:
                            t.write(creds.to_json())

                    # Exportar datos
                    novedades = self.db.get_novedades(limit=99999)
                    abonados  = self.db.get_abonados()
                    backup_data = json.dumps(
                        {"novedades": novedades, "abonados": abonados,
                         "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")},
                        ensure_ascii=False, indent=2)
                    backup_path = os.path.join(APP_DIR, "backup_unica.json")
                    with open(backup_path, "w", encoding="utf-8") as bf:
                        bf.write(backup_data)

                    # Subir a Drive
                    service = build("drive", "v3", credentials=creds)
                    fecha_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    file_meta = {"name": f"backup_unica_{fecha_str}.json"}

                    # Buscar si ya existe una carpeta UNICA en Drive
                    folder_q = "mimeType='application/vnd.google-apps.folder' and name='UNICA Backups' and trashed=false"
                    folders = service.files().list(q=folder_q, fields="files(id)").execute().get("files", [])
                    if folders:
                        file_meta["parents"] = [folders[0]["id"]]
                    else:
                        # Crear carpeta
                        folder = service.files().create(
                            body={"name": "UNICA Backups",
                                  "mimeType": "application/vnd.google-apps.folder"},
                            fields="id").execute()
                        file_meta["parents"] = [folder["id"]]

                    media = MediaFileUpload(backup_path, mimetype="application/json")
                    service.files().create(body=file_meta, media_body=media, fields="id").execute()

                    def u(dt):
                        backup_lbl.text = f"Subido a Drive: {len(novedades)} novedades"
                        backup_lbl.color = C_SUCCESS
                    Clock.schedule_once(u, 0)
                except Exception as ex:
                    msg = str(ex)[:60]
                    def u(dt, m=msg):
                        backup_lbl.text = f"Error: {m}"
                        backup_lbl.color = C_DANGER
                    Clock.schedule_once(u, 0)
            threading.Thread(target=run, daemon=True).start()

        def restaurar_backup():
            # Primero intentar desde Drive, si no desde local
            backup_path = os.path.join(APP_DIR, "backup_unica.json")

            content2 = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
            content2.add_widget(Label(
                text="Restaurar backup?\nSe importaran todas las novedades guardadas.",
                font_size=sp(13), color=C_TEXT, halign="center",
                text_size=(dp(280), None)))
            brow2 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            si2 = Button(text="Si, restaurar", background_color=C_WARNING,
                         background_normal="", color=(0,0,0,1), font_size=sp(13))
            no2 = Button(text="Cancelar", background_color=C_PANEL,
                         background_normal="", color=C_TEXT, font_size=sp(13))
            brow2.add_widget(si2); brow2.add_widget(no2)
            content2.add_widget(brow2)
            p2 = Popup(title="Restaurar backup", content=content2,
                       size_hint=(0.9, None), height=dp(220),
                       background_color=C_BG2, title_color=C_WARNING)
            no2.bind(on_press=p2.dismiss)

            def _restaurar(_):
                p2.dismiss()
                def run():
                    try:
                        # Intentar bajar ultimo backup de Drive
                        from googleapiclient.discovery import build
                        from google.oauth2.credentials import Credentials
                        from googleapiclient.http import MediaIoBaseDownload
                        import io
                        SCOPES = ["https://www.googleapis.com/auth/drive.file"]
                        token_path = os.path.join(APP_DIR, "token.json")
                        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                        service = build("drive", "v3", credentials=creds)
                        # Buscar archivos de backup
                        results = service.files().list(
                            q="name contains 'backup_unica' and trashed=false",
                            orderBy="createdTime desc",
                            pageSize=1, fields="files(id,name)").execute()
                        files = results.get("files", [])
                        if files:
                            fid = files[0]["id"]
                            req = service.files().get_media(fileId=fid)
                            buf = io.BytesIO()
                            dl = MediaIoBaseDownload(buf, req)
                            done = False
                            while not done:
                                _, done = dl.next_chunk()
                            data = json.loads(buf.getvalue().decode("utf-8"))
                            n = 0
                            for nov in data.get("novedades", []):
                                self.db.insert_remota(nov); n += 1
                            cnt = n
                            def u(dt, c=cnt):
                                show_popup("Restaurado desde Drive",
                                           f"{c} novedades importadas.", C_SUCCESS)
                                self._select_tab(self.current_tab)
                            Clock.schedule_once(u, 0)
                            return
                    except:
                        pass
                    # Fallback: backup local
                    try:
                        if os.path.exists(backup_path):
                            with open(backup_path, "r", encoding="utf-8") as bf:
                                data = json.load(bf)
                            n = 0
                            for nov in data.get("novedades", []):
                                self.db.insert_remota(nov); n += 1
                            cnt2 = n
                            def u(dt, c=cnt2):
                                show_popup("Restaurado local",
                                           f"{c} novedades importadas.", C_SUCCESS)
                                self._select_tab(self.current_tab)
                            Clock.schedule_once(u, 0)
                        else:
                            def u(dt): show_popup("Error", "No hay backup disponible.", C_DANGER)
                            Clock.schedule_once(u, 0)
                    except Exception as ex:
                        emsg = str(ex)
                        def u(dt, m=emsg): show_popup("Error", m, C_DANGER)
                        Clock.schedule_once(u, 0)
                threading.Thread(target=run, daemon=True).start()

            si2.bind(on_press=_restaurar)
            p2.open()

        brow_g = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        brow_g.add_widget(mk_btn("Guardar Gmail", guardar_gmail,
                                  bg=C_SUCCESS, color=(0,0,0,1), size=12))
        brow_g.add_widget(mk_btn("Backup ahora", hacer_backup,
                                  bg=C_ACCENT, color=(0,0,0,1), size=12))
        root.add_widget(brow_g)
        root.add_widget(mk_btn("Restaurar backup", restaurar_backup,
                                bg=C_WARNING, color=(0,0,0,1)))
        root.add_widget(mk_sep())

        # ── Red / Sincronizacion ──
        root.add_widget(Label(text="Red y Sincronizacion:", font_size=sp(13),
                              bold=True, color=C_TEXT, size_hint_y=None,
                              height=dp(28), halign="left",
                              text_size=(dp(340), dp(28))))
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except:
            ip = "No disponible"
        root.add_widget(Label(
            text=f"IP de este equipo: {ip}  (Puerto {SYNC_PORT})",
            font_size=sp(11), color=C_SUCCESS, size_hint_y=None,
            height=dp(24), halign="left", text_size=(dp(340), dp(24))))

        root.add_widget(Label(text="IP remota para sincronizar:", font_size=sp(12),
                              color=C_MUTED, size_hint_y=None, height=dp(24),
                              halign="left", text_size=(dp(340), dp(24))))
        eip = mk_input("192.168.1.X")
        root.add_widget(eip)
        sync_lbl = Label(text="", font_size=sp(11), color=C_SUCCESS,
                         size_hint_y=None, height=dp(24), halign="left",
                         text_size=(dp(340), dp(24)))
        root.add_widget(sync_lbl)

        def sincronizar():
            ip2 = eip.text.strip()
            if not ip2: return
            sync_lbl.text = "Sincronizando..."
            sync_lbl.color = C_WARNING
            def run():
                try:
                    s = socket.socket(); s.settimeout(5)
                    s.connect((ip2, SYNC_PORT))
                    s.sendall((json.dumps({"cmd":"pull","desde":self.db.max_id()})+"\n").encode())
                    raw = b""
                    while True:
                        c = s.recv(65536)
                        if not c: break
                        raw += c
                        if raw.endswith(b"\n"): break
                    s.close()
                    data = json.loads(raw)
                    n = 0
                    for nov in data.get("novedades",[]):
                        self.db.insert_remota(nov); n += 1
                    def upd(dt):
                        sync_lbl.text = f"OK: {n} novedades sincronizadas"
                        sync_lbl.color = C_SUCCESS
                    Clock.schedule_once(upd, 0)
                except Exception as ex:
                    def upd(dt):
                        sync_lbl.text = f"Error: {ex}"
                        sync_lbl.color = C_DANGER
                    Clock.schedule_once(upd, 0)
            threading.Thread(target=run, daemon=True).start()

        root.add_widget(mk_btn("Sincronizar ahora", sincronizar,
                               bg=C_ACCENT, color=(0,0,0,1)))
        root.add_widget(mk_sep())
        root.add_widget(Label(
            text=f"{EMPRESA}\nDesarrollado por {AUTHOR}  -  {VERSION}",
            font_size=sp(10), color=C_BORDER, size_hint_y=None,
            height=dp(50), halign="center", text_size=(dp(340), dp(50))))
        root.add_widget(Widget(size_hint_y=None, height=dp(20)))

        sv.add_widget(root)
        return sv


# ─────────────────────────────────────────────
#  APP KIVY
# ─────────────────────────────────────────────
class UnicaApp(App):
    def build(self):
        self.title = "UNICA — Libro de Actas"
        self.db = Database()
        SyncServer(self.db).start()
        self.session = {}

        self.sm = ScreenManager(transition=SlideTransition())
        self.login_screen = LoginScreen(self.db)
        self.main_screen  = MainScreen(self.db)
        self.sm.add_widget(self.login_screen)
        self.sm.add_widget(self.main_screen)
        self._start_auto_backup()
        return self.sm

    def go_main(self):
        self.main_screen.build(self.session)
        self.sm.current = "main"

    def go_login(self):
        self.sm.current = "login"

    def _start_auto_backup(self):
        """Programa backup automatico diario a las 00:00"""
        def _check_backup(dt):
            now = datetime.now()
            if now.hour == 0 and now.minute == 0:
                gmail = self.db.get_config("gmail")
                if gmail:
                    self._do_backup()
        Clock.schedule_interval(_check_backup, 60)  # chequea cada minuto

    def _do_backup(self):
        def run():
            try:
                novedades = self.db.get_novedades(limit=99999)
                abonados  = self.db.get_abonados()
                backup_data = json.dumps(
                    {"novedades": novedades, "abonados": abonados,
                     "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")},
                    ensure_ascii=False, indent=2)
                backup_path = os.path.join(APP_DIR, "backup_unica.json")
                with open(backup_path, "w", encoding="utf-8") as bf:
                    bf.write(backup_data)
                print(f"[BACKUP] Guardado OK: {len(novedades)} novedades")
            except Exception as ex:
                print(f"[BACKUP] Error: {ex}")
        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    UnicaApp().run()
