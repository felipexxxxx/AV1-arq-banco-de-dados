import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from data_pages import (
    create_dataset,
    load_words_from_txt,
    preview_page,
)
from hash_index import (
    FNV1A_NAME,
    available_hash_algorithms,
    build_index,
    calculate_bucket_count,
    create_hash_index,
    search_in_index,
    validate_bucket_count,
)
from metrics import compare_searches, format_seconds, table_scan

# ── Paleta de cores ────────────────────────────────────────────────────────────
BG          = "#0f1117"   
BG_PANEL    = "#1a1d27"  
BG_INPUT    = "#242736"  
BG_HEADER   = "#141720"  
BORDER      = "#2e3347"   
ACCENT      = "#4f8ef7"  
ACCENT2     = "#7c5cfc"  
SUCCESS     = "#34d399"  
WARNING     = "#f59e0b"   
DANGER      = "#f87171"  
TEXT_PRI    = "#e8eaf0" 
TEXT_SEC    = "#8b92a8" 
TEXT_DIM    = "#555c72" 

FONT_MONO   = ("Consolas", 10)
FONT_LABEL  = ("Segoe UI", 9)
FONT_LABEL_BOLD = ("Segoe UI", 9, "bold")
FONT_TITLE  = ("Segoe UI", 10, "bold")
FONT_HEAD   = ("Segoe UI", 13, "bold")
FONT_STATUS = ("Segoe UI", 9)


class HashIndexApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hash Index Explorer — Projeto 1")
        self.geometry("1360x900")
        self.minsize(1100, 740)
        self.configure(bg=BG)

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_data_dir = os.path.join(self.base_dir, "english-words-master")

        self.records = []
        self.dataset = None
        self.index = None
        self.build_stats = None
        self.last_index_result = None
        self.last_scan_result = None

        self.file_path_var = tk.StringVar()
        self.record_count_var = tk.StringVar(value="—")
        self.page_size_var = tk.StringVar(value="128")
        self.fr_var = tk.StringVar(value="4")
        self.hash_var = tk.StringVar(value=FNV1A_NAME)
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Carregue um arquivo TXT com uma palavra por linha.")

        self._text_widgets = {}
        self._apply_styles()
        self._build_layout()
        self._render_dataset_summary()
        self._render_page_summary()
        self._render_index_result()
        self._render_scan_result()
        self._render_comparison()

    # ── Estilos TTK ───────────────────────────────────────────────────────────

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Fundo geral
        style.configure(".", background=BG, foreground=TEXT_PRI,
                        font=FONT_LABEL, borderwidth=0, relief="flat")

        # Frames simples
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=BG_PANEL)

        # Labels
        style.configure("TLabel", background=BG, foreground=TEXT_PRI, font=FONT_LABEL)
        style.configure("Dim.TLabel", background=BG_PANEL, foreground=TEXT_SEC, font=FONT_LABEL)
        style.configure("Head.TLabel", background=BG_HEADER, foreground=TEXT_PRI, font=FONT_HEAD)
        style.configure("Tag.TLabel", background=BG_INPUT, foreground=ACCENT,
                        font=FONT_LABEL_BOLD, padding=(6, 2))

        # Entradas
        style.configure("TEntry", fieldbackground=BG_INPUT, foreground=TEXT_PRI,
                        insertcolor=TEXT_PRI, borderwidth=1, relief="flat",
                        padding=(8, 6))
        style.map("TEntry", fieldbackground=[("readonly", BG_INPUT)])

        # Combobox
        style.configure("TCombobox", fieldbackground=BG_INPUT, foreground=TEXT_PRI,
                        selectbackground=BG_INPUT, selectforeground=TEXT_PRI,
                        arrowcolor=ACCENT, borderwidth=1, relief="flat", padding=(6, 6))
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG_INPUT)],
                  foreground=[("readonly", TEXT_PRI)])

        # Botões primários
        style.configure("Primary.TButton",
                        background=ACCENT, foreground="#ffffff",
                        font=FONT_LABEL_BOLD, padding=(14, 7),
                        relief="flat", borderwidth=0)
        style.map("Primary.TButton",
                  background=[("active", "#3a7ae0"), ("pressed", "#2d64c0")])

        # Botões secundários
        style.configure("Secondary.TButton",
                        background=BG_INPUT, foreground=TEXT_PRI,
                        font=FONT_LABEL, padding=(12, 7),
                        relief="flat", borderwidth=0)
        style.map("Secondary.TButton",
                  background=[("active", "#2e3347"), ("pressed", "#1e2235")])

        # Botão de busca (accent2)
        style.configure("Search.TButton",
                        background=ACCENT2, foreground="#ffffff",
                        font=FONT_LABEL_BOLD, padding=(14, 7),
                        relief="flat", borderwidth=0)
        style.map("Search.TButton",
                  background=[("active", "#6a4de0"), ("pressed", "#5840c0")])

        # Separador
        style.configure("TSeparator", background=BORDER)

        # Scrollbar
        style.configure("Vertical.TScrollbar",
                        background=BG_PANEL, troughcolor=BG_PANEL,
                        arrowcolor=TEXT_DIM, borderwidth=0, relief="flat",
                        width=8)
        style.map("Vertical.TScrollbar",
                  background=[("active", BG_INPUT)])

    # ── Layout principal ──────────────────────────────────────────────────────

    def _build_layout(self):
        # ── Cabeçalho ──
        header = tk.Frame(self, bg=BG_HEADER, height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="⬡  Hash Index Explorer",
            bg=BG_HEADER, fg=TEXT_PRI,
            font=FONT_HEAD,
            padx=20,
        ).pack(side="left", pady=14)

        tk.Label(
            header,
            text="Projeto 1 – Banco de Dados",
            bg=BG_HEADER, fg=TEXT_DIM,
            font=FONT_STATUS,
        ).pack(side="right", padx=20)

        # Linha separadora
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Corpo ──
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)
        body.rowconfigure(4, weight=1)

        # Seção 1 – Arquivo
        self._build_section_arquivo(body)

        # Seção 2 – Parâmetros
        self._build_section_params(body)

        # Seção 3 – Busca
        self._build_section_busca(body)

        # Linha separadora
        tk.Frame(body, bg=BORDER, height=1).grid(
            row=3, column=0, sticky="ew", padx=16, pady=(0, 0))

        # Seção 4 – Painéis de resultado (linha superior)
        self._build_section_resumos(body, row=4)

        # Seção 5 – Painéis de resultado (linha inferior)
        self._build_section_resultados(body, row=5)

        # Barra de status
        status_bar = tk.Frame(self, bg=BG_HEADER, height=32)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)

        tk.Frame(status_bar, bg=ACCENT, width=3).pack(side="left", fill="y")
        tk.Label(
            status_bar,
            textvariable=self.status_var,
            bg=BG_HEADER, fg=TEXT_SEC,
            font=FONT_STATUS, anchor="w", padx=12,
        ).pack(side="left", fill="y")

    def _build_section_arquivo(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        frame.columnconfigure(1, weight=1)

        self._section_tag(frame, "01  ARQUIVO", col=0)

        inner = tk.Frame(frame, bg=BG_PANEL)
        inner.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        inner.columnconfigure(1, weight=1)

        ttk.Button(inner, text="📂  Carregar TXT",
                   style="Primary.TButton",
                   command=self._load_file).grid(
            row=0, column=0, padx=(12, 8), pady=10, sticky="w")

        path_entry = ttk.Entry(inner, textvariable=self.file_path_var,
                               state="readonly", font=FONT_MONO)
        path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=10)

        count_lbl = tk.Label(inner, textvariable=self.record_count_var,
                             bg=BG_PANEL, fg=ACCENT, font=FONT_LABEL_BOLD,
                             padx=12)
        count_lbl.grid(row=0, column=2, sticky="e", padx=(0, 12))

    def _build_section_params(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 0))

        self._section_tag(frame, "02  PARÂMETROS", col=0)

        inner = tk.Frame(frame, bg=BG_PANEL)
        inner.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        # Tamanho da página
        self._param_field(inner, "Tamanho da Página", self.page_size_var,
                          col=0, width=10)

        tk.Frame(inner, bg=BORDER, width=1).grid(
            row=0, column=2, rowspan=3, sticky="ns", padx=12, pady=8)

        # FR
        self._param_field(inner, "FR  (capacidade primária do bucket)",
                          self.fr_var, col=3, width=10)

        tk.Frame(inner, bg=BORDER, width=1).grid(
            row=0, column=5, rowspan=3, sticky="ns", padx=12, pady=8)

        # Hash
        tk.Label(inner, text="Algoritmo Hash", bg=BG_PANEL,
                 fg=TEXT_SEC, font=FONT_LABEL).grid(
            row=0, column=6, sticky="w", padx=(0, 0), pady=(10, 2))
        hash_combo = ttk.Combobox(
            inner,
            textvariable=self.hash_var,
            values=available_hash_algorithms(),
            state="readonly",
            width=20,
            font=FONT_LABEL,
        )
        hash_combo.grid(row=1, column=6, sticky="w", padx=(0, 16), pady=(0, 10))

        # Botão construir
        ttk.Button(inner, text="⚙  Construir Índice",
                   style="Primary.TButton",
                   command=self._build_index).grid(
            row=1, column=7, padx=(0, 12), pady=(0, 10), sticky="w")

    def _build_section_busca(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(12, 12))
        frame.columnconfigure(1, weight=1)

        self._section_tag(frame, "03  BUSCA", col=0)

        inner = tk.Frame(frame, bg=BG_PANEL)
        inner.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        inner.columnconfigure(1, weight=1)

        tk.Label(inner, text="Palavra", bg=BG_PANEL,
                 fg=TEXT_SEC, font=FONT_LABEL).grid(
            row=0, column=0, sticky="w", padx=(14, 8), pady=(10, 2))

        search_entry = ttk.Entry(inner, textvariable=self.search_var,
                                 font=FONT_MONO)
        search_entry.grid(row=0, column=1, sticky="ew",
                          padx=(0, 8), pady=(8, 8))
        search_entry.bind("<Return>", lambda _e: self._search_by_index())

        ttk.Button(inner, text="🔍  Buscar via Índice",
                   style="Search.TButton",
                   command=self._search_by_index).grid(
            row=0, column=2, padx=(0, 8), pady=8)

        ttk.Button(inner, text="≡  Table Scan",
                   style="Secondary.TButton",
                   command=self._run_table_scan).grid(
            row=0, column=3, padx=(0, 12), pady=8)

    def _build_section_resumos(self, parent, row):
        container = tk.Frame(parent, bg=BG)
        container.grid(row=row, column=0, sticky="nsew",
                       padx=16, pady=(10, 4))
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)
        parent.rowconfigure(row, weight=1)

        self._make_panel(container, "Resumo e Métricas", "dataset",
                         row=0, col=0, padright=4)
        self._make_panel(container, "Primeira e Última Página", "pages",
                         row=0, col=1, padleft=4)

    def _build_section_resultados(self, parent, row):
        container = tk.Frame(parent, bg=BG)
        container.grid(row=row, column=0, sticky="nsew",
                       padx=16, pady=(4, 14))
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.columnconfigure(2, weight=1)
        container.rowconfigure(0, weight=1)
        parent.rowconfigure(row, weight=1)

        self._make_panel(container, "🔍  Busca via Índice", "index",
                         row=0, col=0, padright=4)
        self._make_panel(container, "≡  Table Scan", "scan",
                         row=0, col=1, padleft=4, padright=4)
        self._make_panel(container, "⚡  Comparação", "compare",
                         row=0, col=2, padleft=4)

    # ── Helpers de UI ─────────────────────────────────────────────────────────

    def _section_tag(self, parent, text, col=0):
        """Etiqueta de seção com estilo de 'pill'."""
        lbl = tk.Label(
            parent,
            text=text,
            bg=BG, fg=TEXT_DIM,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        )
        lbl.grid(row=0, column=col, sticky="w", pady=(0, 0))

    def _param_field(self, parent, label, var, col, width=10):
        tk.Label(parent, text=label, bg=BG_PANEL,
                 fg=TEXT_SEC, font=FONT_LABEL).grid(
            row=0, column=col, sticky="w", padx=(14, 0), pady=(10, 2))
        entry = ttk.Entry(parent, textvariable=var, width=width, font=FONT_MONO)
        entry.grid(row=1, column=col, sticky="w",
                   padx=(14, 0), pady=(0, 10))

    def _make_panel(self, parent, title, key, row, col,
                    padleft=0, padright=0):
        """Cria um painel com título e caixa de texto."""
        frame = tk.Frame(parent, bg=BG_PANEL,
                         highlightbackground=BORDER, highlightthickness=1)
        frame.grid(row=row, column=col, sticky="nsew",
                   padx=(padleft, padright))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        # Cabeçalho do painel
        header = tk.Frame(frame, bg=BG_INPUT, height=34)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        tk.Label(header, text=title, bg=BG_INPUT,
                 fg=TEXT_PRI, font=FONT_TITLE,
                 padx=12).pack(side="left", pady=6)

        # Área de texto com scrollbar
        text_frame = tk.Frame(frame, bg=BG_PANEL)
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        text = tk.Text(
            text_frame,
            wrap="word",
            padx=12, pady=10,
            font=FONT_MONO,
            bg=BG_PANEL,
            fg=TEXT_PRI,
            insertbackground=TEXT_PRI,
            selectbackground=ACCENT,
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            spacing1=2,
            spacing3=2,
        )
        text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical",
                                  command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)
        text.configure(state="disabled")

        self._text_widgets[key] = text
        return frame

    # ── Texto colorido nos painéis ────────────────────────────────────────────

    def _configure_tags(self, widget):
        widget.tag_configure("accent",  foreground=ACCENT)
        widget.tag_configure("accent2", foreground=ACCENT2)
        widget.tag_configure("success", foreground=SUCCESS)
        widget.tag_configure("warning", foreground=WARNING)
        widget.tag_configure("danger",  foreground=DANGER)
        widget.tag_configure("dim",     foreground=TEXT_SEC)
        widget.tag_configure("bold",    font=FONT_LABEL_BOLD)
        widget.tag_configure("head",    font=FONT_TITLE, foreground=TEXT_PRI)

    def _set_text(self, key, content):
        widget = self._text_widgets[key]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        self._configure_tags(widget)
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _set_rich(self, key, segments):
        """segments = list of (text, tag_or_None)"""
        widget = self._text_widgets[key]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        self._configure_tags(widget)
        for text, tag in segments:
            if tag:
                widget.insert("end", text, tag)
            else:
                widget.insert("end", text)
        widget.configure(state="disabled")

    # ── Lógica de negócio (idêntica ao original) ──────────────────────────────

    def _load_file(self):
        initial_dir = (self.default_data_dir
                       if os.path.exists(self.default_data_dir)
                       else self.base_dir)
        selected = filedialog.askopenfilename(
            title="Selecione um arquivo TXT",
            initialdir=initial_dir,
            filetypes=[("Arquivos TXT", "*.txt"), ("Todos os arquivos", "*.*")],
        )
        if not selected:
            return

        try:
            loaded_records = load_words_from_txt(selected)
        except Exception as error:
            self.status_var.set("Falha ao carregar arquivo.")
            messagebox.showerror("Erro", str(error))
            return

        self.records = list(loaded_records)
        self.dataset = None
        self.index = None
        self.build_stats = None
        self.last_index_result = None
        self.last_scan_result = None

        self.file_path_var.set(selected)
        self.record_count_var.set(
            f"{len(self.records):,} registros".replace(",", "."))

        self._render_dataset_summary()
        self._render_page_summary()
        self._render_index_result()
        self._render_scan_result()
        self._render_comparison()
        self.status_var.set("✓  Arquivo carregado com sucesso.")

    def _build_index(self):
        if not self.records:
            messagebox.showwarning(
                "Arquivo", "Carregue um arquivo TXT antes de construir o índice.")
            return

        try:
            page_size = int(self.page_size_var.get())
            fr = int(self.fr_var.get())
        except ValueError:
            messagebox.showwarning(
                "Parâmetros", "Tamanho da página e FR devem ser inteiros.")
            return

        if page_size <= 0:
            messagebox.showwarning(
                "Parâmetros", "Tamanho da página deve ser maior que zero.")
            return

        if fr <= 0:
            messagebox.showwarning(
                "Parâmetros", "FR deve ser maior que zero.")
            return

        hash_algorithm = self.hash_var.get()

        try:
            dataset = create_dataset(self.records, page_size)
            bucket_count = calculate_bucket_count(dataset["nr"], fr)
            if not validate_bucket_count(bucket_count, dataset["nr"], fr):
                raise ValueError("NB calculado não atende à validação NB > NR/FR.")
            index = create_hash_index(fr, bucket_count, hash_algorithm)
            stats = build_index(index, dataset)
        except Exception as error:
            self.status_var.set("Falha ao construir índice.")
            messagebox.showerror("Erro", str(error))
            return

        self.dataset = dataset
        self.index = index
        self.build_stats = stats
        self.last_index_result = None
        self.last_scan_result = None

        self._render_dataset_summary()
        self._render_page_summary()
        self._render_index_result()
        self._render_scan_result()
        self._render_comparison()
        self.status_var.set("✓  Índice construído com sucesso.")

    def _search_by_index(self):
        if self.index is None or self.dataset is None:
            messagebox.showwarning("Índice", "Construa o índice antes de buscar.")
            return

        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Busca", "Informe uma palavra para pesquisar.")
            return

        self.last_index_result = search_in_index(
            self.index, query, self.dataset)
        self._render_index_result()
        self._render_comparison()
        self.status_var.set("✓  Busca via índice concluída.")

    def _run_table_scan(self):
        if self.dataset is None:
            messagebox.showwarning(
                "Dados",
                "Construa o índice para preparar as páginas antes do table scan.")
            return

        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Busca", "Informe uma palavra para pesquisar.")
            return

        self.last_scan_result = table_scan(self.dataset, query)
        self._render_scan_result()
        self._render_comparison()
        self.status_var.set("✓  Table scan concluído.")

    # ── Renderização dos painéis ───────────────────────────────────────────────

    def _render_dataset_summary(self):
        seg = []
        path = self.file_path_var.get() or "—"

        seg += [("Arquivo\n", "dim"), (f"{path}\n", None)]

        if self.dataset is None or self.build_stats is None:
            if self.records:
                seg += [
                    ("\n", None),
                    (f"{len(self.records):,}".replace(",", "."), "accent"),
                    (" registros carregados\n", "dim"),
                    ("\n", None),
                    ("Defina os parâmetros e clique em ", "dim"),
                    ("Construir Índice", "accent"),
                    (".\n", "dim"),
                ]
            else:
                seg += [
                    ("\n", None),
                    ("Nenhum arquivo carregado.\n", "dim"),
                ]
        else:
            ratio = (self.build_stats["record_count"]
                     / self.build_stats["bucket_capacity"])
            ok = validate_bucket_count(
                self.build_stats["bucket_count"],
                self.build_stats["record_count"],
                self.build_stats["bucket_capacity"],
            )

            def row(label, value, tag=None):
                seg.append((f"\n{label}  ", "dim"))
                seg.append((str(value), tag or "accent"))

            seg.append(("\n── Estrutura ──────────────────\n", "dim"))
            row("Tamanho da página", self.dataset["page_size"])
            row("Páginas de dados", self.dataset["page_count"])
            row("FR", self.build_stats["bucket_capacity"])
            row("NB calculado", self.build_stats["bucket_count"])

            validacao_tag = "success" if ok else "danger"
            validacao_txt = "OK ✓" if ok else "FALHOU ✗"
            seg += [
                ("\n\nValidação NB > NR/FR  ", "dim"),
                (f"{self.build_stats['bucket_count']} > {ratio:.2f}", None),
                (f"  {validacao_txt}\n", validacao_tag),
            ]

            seg.append(("\n── Performance ────────────────\n", "dim"))
            row("Hash", self.index["hash_algorithm"] if self.index else "—", None)
            row("Tempo de construção",
                format_seconds(self.build_stats["build_seconds"]))
            row("Colisões",
                f"{self.build_stats['collision_count']:,}".replace(",", "."),
                "warning")
            row("Taxa de colisões",
                f"{self.build_stats['collision_rate']:.3f}%", "warning")
            row("Buckets com overflow",
                f"{self.build_stats['overflow_bucket_count']:,}".replace(",", "."),
                "warning")
            row("Páginas de overflow",
                f"{self.build_stats['overflow_page_count']:,}".replace(",", "."),
                "warning")
            row("Taxa de overflow",
                f"{self.build_stats['overflow_rate']:.3f}%", "warning")
            seg.append(("\n", None))

        self._set_rich("dataset", seg)

    def _render_page_summary(self):
        if self.dataset is None:
            self._set_rich("pages", [
                ("As páginas serão exibidas após a construção do índice.\n\n",
                 "dim"),
                ("Apenas a primeira e a última página são mostradas\n"
                 "para evitar renderização pesada.", "dim"),
            ])
            return

        first_preview = preview_page(self.dataset, 1)
        last_preview = preview_page(self.dataset, self.dataset["page_count"])

        seg = [
            (f"Total de páginas  ", "dim"),
            (f"{self.dataset['page_count']}\n", "accent"),
        ]
        seg += self._page_preview_segs("Primeira Página", first_preview)
        seg += [("\n", None)]
        seg += self._page_preview_segs("Última Página", last_preview)

        self._set_rich("pages", seg)

    def _page_preview_segs(self, title, preview):
        seg = [
            (f"\n── {title} ─────────────────────\n", "dim"),
        ]
        if preview is None:
            seg.append(("Sem registros.\n", "dim"))
            return seg
        records = (", ".join(preview["first_records"])
                   if preview["first_records"] else "—")
        seg += [
            (f"Página #", "dim"),
            (f"{preview['page_number']}", "accent"),
            (f"   Registros: ", "dim"),
            (f"{preview['record_count']}\n", "accent"),
            (f"Primeiros: ", "dim"),
            (f"{records}\n", None),
        ]
        return seg

    def _render_index_result(self):
        if self.last_index_result is None:
            self._set_rich("index", [
                ("Execute ", "dim"),
                ("Buscar via Índice", "accent2"),
                (" para ver:\n\n", "dim"),
                ("  • bucket acessado\n"
                 "  • página encontrada\n"
                 "  • custo estimado\n"
                 "  • tempo de busca\n", "dim"),
            ])
            return

        r = self.last_index_result
        found = r["found"]
        status_tag = "success" if found else "danger"
        status_txt = "ENCONTRADO ✓" if found else "NÃO ENCONTRADO ✗"

        seg = [
            ("Palavra  ", "dim"), (f"{r['query']}\n", "accent2"),
            ("Status   ", "dim"), (f"{status_txt}\n\n", status_tag),
            ("── Índice ────────────────────────\n", "dim"),
            ("Bucket calculado         ", "dim"),
            (f"{r['bucket_index']}\n", "accent"),
            ("Leit. bucket/overflow    ", "dim"),
            (f"{r['bucket_pages_read']}\n", "accent"),
            ("Leit. páginas de dados   ", "dim"),
            (f"{r['data_pages_read']}\n", "accent"),
            ("Custo total estimado     ", "dim"),
            (f"{r['total_page_reads']}\n", "accent"),
            ("Entradas examinadas      ", "dim"),
            (f"{r['bucket_entries_examined']}\n", "accent"),
            ("Tempo                    ", "dim"),
            (f"{format_seconds(r['elapsed_seconds'])}\n", "accent"),
            ("Página encontrada        ", "dim"),
            (f"{r['page_number'] if r['page_number'] is not None else '—'}\n", "accent"),
            ("\n── Snapshot do Bucket ────────────\n", "dim"),
            (self._format_bucket_snapshot(r["bucket_snapshot"]) + "\n", None),
        ]

        if r["page_preview"] is not None:
            seg += self._page_preview_segs(
                "Página Confirmada", r["page_preview"])

        self._set_rich("index", seg)

    def _render_scan_result(self):
        if self.last_scan_result is None:
            self._set_rich("scan", [
                ("Execute ", "dim"),
                ("Table Scan", "accent"),
                (" para ver:\n\n", "dim"),
                ("  • páginas lidas\n"
                 "  • registros lidos\n"
                 "  • página encontrada\n"
                 "  • custo e tempo\n", "dim"),
            ])
            return

        r = self.last_scan_result
        found = r["found"]
        status_tag = "success" if found else "danger"
        status_txt = "ENCONTRADO ✓" if found else "NÃO ENCONTRADO ✗"

        visited = ", ".join(str(p) for p in r["visited_pages_preview"]) or "—"
        if r["preview_truncated"]:
            visited += ", …"

        seg = [
            ("Palavra  ", "dim"), (f"{r['query']}\n", "accent"),
            ("Status   ", "dim"), (f"{status_txt}\n\n", status_tag),
            ("── Scan ──────────────────────────\n", "dim"),
            ("Páginas lidas       ", "dim"),
            (f"{r['pages_read']}\n", "warning"),
            ("Registros lidos     ", "dim"),
            (f"{r['records_read']:,}\n".replace(",", "."), "warning"),
            ("Custo total         ", "dim"),
            (f"{r['pages_read']}\n", "warning"),
            ("Tempo               ", "dim"),
            (f"{format_seconds(r['elapsed_seconds'])}\n", "accent"),
            ("Página encontrada   ", "dim"),
            (f"{r['page_number'] if r['page_number'] is not None else '—'}\n", "accent"),
            ("\n── Páginas Visitadas (amostra) ───\n", "dim"),
            (f"{visited}\n", None),
        ]

        if r["page_preview"] is not None:
            seg += self._page_preview_segs(
                "Página Encontrada", r["page_preview"])

        self._set_rich("scan", seg)

    def _render_comparison(self):
        comparison = compare_searches(
            self.last_index_result, self.last_scan_result)

        seg = [("── Comparação ────────────────────\n", "dim")]

        if comparison is None:
            seg += [
                ("\nExecute as duas buscas para comparar\n"
                 "tempo e custo de cada abordagem.\n", "dim"),
            ]
        elif not comparison["same_query"]:
            seg += [
                ("\nAs buscas foram feitas com palavras ", "dim"),
                ("diferentes", "danger"),
                (".\nRepita com a mesma palavra para\numa comparação válida.\n", "dim"),
            ]
        else:
            saved_t = comparison["time_saved_seconds"]
            saved_p = comparison["page_reads_saved"]
            t_tag = "success" if saved_t > 0 else "danger"
            p_tag = "success" if saved_p > 0 else "danger"
            seg += [
                ("\nPalavra   ", "dim"), (f"{comparison['query']}\n\n", "accent2"),
                ("Δ Tempo  (scan − índice)  ", "dim"),
                (f"{format_seconds(saved_t)}\n", t_tag),
                ("Δ Custo  (scan − índice)  ", "dim"),
                (f"{saved_p} leituras\n", p_tag),
            ]

        if self.last_index_result is not None:
            seg += [
                ("\n── Snapshot do Bucket ────────────\n", "dim"),
                (self._format_bucket_snapshot(
                    self.last_index_result["bucket_snapshot"]) + "\n", None),
            ]

        preview = None
        preview_title = "Última Página Relevante"
        if (self.last_index_result is not None
                and self.last_index_result["page_preview"] is not None):
            preview = self.last_index_result["page_preview"]
            preview_title = "Página — Busca via Índice"
        elif (self.last_scan_result is not None
              and self.last_scan_result["page_preview"] is not None):
            preview = self.last_scan_result["page_preview"]
            preview_title = "Página — Table Scan"

        if preview is not None:
            seg += self._page_preview_segs(preview_title, preview)

        self._set_rich("compare", seg)

    def _format_bucket_snapshot(self, snapshot):
        primary = self._format_entries(snapshot["primary_entries"])
        lines = [
            f"Bucket #{snapshot['bucket_index']}",
            f"Entradas totais: {snapshot['total_entries']}",
            f"Primário ({len(snapshot['primary_entries'])}): {primary}",
        ]

        if not snapshot["overflow_pages"]:
            lines.append("Overflow: nenhum")
            return "\n".join(lines)

        lines.append(f"Overflow: {len(snapshot['overflow_pages'])} página(s)")
        for i, entries in enumerate(snapshot["overflow_pages"], start=1):
            lines.append(
                f"  Overflow {i} ({len(entries)}): "
                f"{self._format_entries(entries)}"
            )
        return "\n".join(lines)

    def _format_entries(self, entries):
        if not entries:
            return "—"
        preview = [f"{e['key']}→{e['page_number']}" for e in entries[:5]]
        if len(entries) > 5:
            preview.append("…")
        return ", ".join(preview)


def launch_app():
    app = HashIndexApp()
    app.mainloop()