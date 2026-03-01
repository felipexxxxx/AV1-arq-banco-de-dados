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


class HashIndexApp(tk.Tk):
    # Esta eh a unica classe que ficou no projeto.
    # Aqui faz sentido usar classe porque a propria janela do Tkinter
    # funciona melhor assim: a classe guarda os campos, botoes e resultados.
    def __init__(self):
        super().__init__()
        self.title("Projeto 1 - Indice HASH")
        self.geometry("1280x860")
        self.minsize(1080, 720)

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_data_dir = os.path.join(self.base_dir, "english-words-master")

        # Estas variaveis guardam o estado atual da aplicacao.
        self.records = []
        self.dataset = None
        self.index = None
        self.build_stats = None
        self.last_index_result = None
        self.last_scan_result = None

        self.file_path_var = tk.StringVar()
        self.record_count_var = tk.StringVar(value="NR: -")
        self.page_size_var = tk.StringVar(value="128")
        self.fr_var = tk.StringVar(value="4")
        self.hash_var = tk.StringVar(value=FNV1A_NAME)
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Carregue um arquivo TXT com uma palavra por linha.")

        self._text_widgets = {}

        self._build_layout()
        self._render_dataset_summary()
        self._render_page_summary()
        self._render_index_result()
        self._render_scan_result()
        self._render_comparison()

    def _build_layout(self):
        # Monta a interface com os botoes e paineis de resultado.
        # A tela foi dividida em 5 partes:
        # 1. arquivo
        # 2. parametros
        # 3. buscas
        # 4. resumos
        # 5. comparacao final
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(3, weight=1)
        container.rowconfigure(4, weight=1)

        controls = ttk.LabelFrame(container, text="1. Arquivo")
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        controls.columnconfigure(1, weight=1)

        load_button = ttk.Button(controls, text="Carregar TXT", command=self._load_file)
        load_button.grid(row=0, column=0, sticky="w", padx=(0, 8))

        path_entry = ttk.Entry(controls, textvariable=self.file_path_var, state="readonly")
        path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        record_label = ttk.Label(controls, textvariable=self.record_count_var)
        record_label.grid(row=0, column=2, sticky="e")

        config = ttk.LabelFrame(container, text="2. Parametros")
        config.grid(row=1, column=0, sticky="ew", padx=8, pady=4)

        ttk.Label(config, text="Tamanho da pagina").grid(row=0, column=0, sticky="w")
        ttk.Entry(config, textvariable=self.page_size_var, width=10).grid(row=1, column=0, sticky="w", padx=(0, 12))

        ttk.Label(config, text="FR (capacidade primaria do bucket)").grid(row=0, column=1, sticky="w")
        ttk.Entry(config, textvariable=self.fr_var, width=10).grid(row=1, column=1, sticky="w", padx=(0, 12))

        ttk.Label(config, text="Hash deterministica").grid(row=0, column=2, sticky="w")
        hash_combo = ttk.Combobox(
            config,
            textvariable=self.hash_var,
            values=available_hash_algorithms(),
            state="readonly",
            width=18,
        )
        hash_combo.grid(row=1, column=2, sticky="w", padx=(0, 12))

        build_button = ttk.Button(config, text="Construir indice", command=self._build_index)
        build_button.grid(row=1, column=3, sticky="w")

        search = ttk.LabelFrame(container, text="3. Buscas")
        search.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        search.columnconfigure(1, weight=1)

        ttk.Label(search, text="Palavra").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(search, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        search_entry.bind("<Return>", lambda _event: self._search_by_index())

        index_button = ttk.Button(search, text="Buscar via indice", command=self._search_by_index)
        index_button.grid(row=0, column=2, sticky="w", padx=(0, 8))

        scan_button = ttk.Button(search, text="Table scan", command=self._run_table_scan)
        scan_button.grid(row=0, column=3, sticky="w")

        summary_row = ttk.Frame(container)
        summary_row.grid(row=3, column=0, sticky="nsew", padx=8, pady=4)
        summary_row.columnconfigure(0, weight=1)
        summary_row.columnconfigure(1, weight=1)
        summary_row.rowconfigure(0, weight=1)

        dataset_frame = ttk.LabelFrame(summary_row, text="Resumo e metricas")
        dataset_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        dataset_frame.rowconfigure(0, weight=1)
        dataset_frame.columnconfigure(0, weight=1)
        self._text_widgets["dataset"] = self._make_text_box(dataset_frame, height=18)

        pages_frame = ttk.LabelFrame(summary_row, text="Primeira e ultima pagina")
        pages_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        pages_frame.rowconfigure(0, weight=1)
        pages_frame.columnconfigure(0, weight=1)
        self._text_widgets["pages"] = self._make_text_box(pages_frame, height=18)

        results_row = ttk.Frame(container)
        results_row.grid(row=4, column=0, sticky="nsew", padx=8, pady=(4, 8))
        results_row.columnconfigure(0, weight=1)
        results_row.columnconfigure(1, weight=1)
        results_row.columnconfigure(2, weight=1)
        results_row.rowconfigure(0, weight=1)

        index_result_frame = ttk.LabelFrame(results_row, text="Busca via indice")
        index_result_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        index_result_frame.rowconfigure(0, weight=1)
        index_result_frame.columnconfigure(0, weight=1)
        self._text_widgets["index"] = self._make_text_box(index_result_frame, height=18)

        scan_result_frame = ttk.LabelFrame(results_row, text="Table scan")
        scan_result_frame.grid(row=0, column=1, sticky="nsew", padx=4)
        scan_result_frame.rowconfigure(0, weight=1)
        scan_result_frame.columnconfigure(0, weight=1)
        self._text_widgets["scan"] = self._make_text_box(scan_result_frame, height=18)

        compare_frame = ttk.LabelFrame(results_row, text="Comparacao e highlights")
        compare_frame.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        compare_frame.rowconfigure(0, weight=1)
        compare_frame.columnconfigure(0, weight=1)
        self._text_widgets["compare"] = self._make_text_box(compare_frame, height=18)

        status = ttk.Label(container, textvariable=self.status_var, anchor="w")
        status.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 8))

    def _make_text_box(self, parent, height):
        text = tk.Text(parent, height=height, wrap="word", padx=10, pady=10)
        text.grid(row=0, column=0, sticky="nsew")
        text.configure(state="disabled")
        return text

    def _set_text(self, key, content):
        widget = self._text_widgets[key]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _load_file(self):
        # Escolhe e carrega o arquivo de palavras.
        # Depois disso, o sistema ainda nao cria o indice.
        # Ele apenas guarda as palavras na memoria.
        initial_dir = self.default_data_dir if os.path.exists(self.default_data_dir) else self.base_dir
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

        # Ao carregar novo arquivo, limpamos resultados antigos.
        self.records = list(loaded_records)
        self.dataset = None
        self.index = None
        self.build_stats = None
        self.last_index_result = None
        self.last_scan_result = None

        self.file_path_var.set(selected)
        self.record_count_var.set(f"NR: {len(self.records):,}".replace(",", "."))

        self._render_dataset_summary()
        self._render_page_summary()
        self._render_index_result()
        self._render_scan_result()
        self._render_comparison()
        self.status_var.set("Arquivo carregado.")

    def _build_index(self):
        # Cria as paginas e monta o indice hash.
        #
        # Aqui acontece a parte principal do trabalho:
        # 1. divide os dados em paginas
        # 2. calcula NB
        # 3. cria os buckets
        # 4. percorre todas as palavras para montar o indice
        if not self.records:
            messagebox.showwarning("Arquivo", "Carregue um arquivo TXT antes de construir o indice.")
            return

        try:
            page_size = int(self.page_size_var.get())
            fr = int(self.fr_var.get())
        except ValueError:
            messagebox.showwarning("Parametros", "Tamanho da pagina e FR devem ser inteiros.")
            return

        if page_size <= 0:
            messagebox.showwarning("Parametros", "Tamanho da pagina deve ser maior que zero.")
            return

        if fr <= 0:
            messagebox.showwarning("Parametros", "FR deve ser maior que zero.")
            return

        hash_algorithm = self.hash_var.get()

        try:
            dataset = create_dataset(self.records, page_size)
            bucket_count = calculate_bucket_count(dataset["nr"], fr)
            if not validate_bucket_count(bucket_count, dataset["nr"], fr):
                raise ValueError("NB calculado nao atende a validacao NB > NR/FR.")
            index = create_hash_index(fr, bucket_count, hash_algorithm)
            stats = build_index(index, dataset)
        except Exception as error:
            self.status_var.set("Falha ao construir indice.")
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
        self.status_var.set("Indice construido.")

    def _search_by_index(self):
        # Busca usando o indice hash.
        # Esta opcao usa a hash para ir direto ao bucket mais provavel.
        if self.index is None or self.dataset is None:
            messagebox.showwarning("Indice", "Construa o indice antes de buscar.")
            return

        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Busca", "Informe uma palavra para pesquisar.")
            return

        self.last_index_result = search_in_index(self.index, query, self.dataset)
        self._render_index_result()
        self._render_comparison()
        self.status_var.set("Busca via indice concluida.")

    def _run_table_scan(self):
        # Busca sequencial, pagina por pagina.
        # Esta opcao ignora o indice e vai lendo os dados na ordem.
        if self.dataset is None:
            messagebox.showwarning("Dados", "Construa o indice para preparar as paginas antes do table scan.")
            return

        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Busca", "Informe uma palavra para pesquisar.")
            return

        self.last_scan_result = table_scan(self.dataset, query)
        self._render_scan_result()
        self._render_comparison()
        self.status_var.set("Table scan concluido.")

    def _render_dataset_summary(self):
        # Atualiza o painel da esquerda com os numeros gerais do projeto.
        # Aqui mostramos os dados mais importantes da construcao do indice.
        lines = [
            "Arquivo selecionado:",
            self.file_path_var.get() or "-",
            "",
            self.record_count_var.get(),
        ]

        if self.dataset is None or self.build_stats is None:
            lines.extend(
                [
                    "",
                    "Defina tamanho da pagina e FR, depois clique em 'Construir indice'.",
                ]
            )
        else:
            ratio = self.build_stats["record_count"] / self.build_stats["bucket_capacity"]
            validation = validate_bucket_count(
                self.build_stats["bucket_count"],
                self.build_stats["record_count"],
                self.build_stats["bucket_capacity"],
            )
            lines.extend(
                [
                    "",
                    f"Tamanho da pagina: {self.dataset['page_size']}",
                    f"Paginas de dados: {self.dataset['page_count']}",
                    f"FR: {self.build_stats['bucket_capacity']}",
                    f"NB calculado: {self.build_stats['bucket_count']}",
                    f"Validacao NB > NR/FR: {self.build_stats['bucket_count']} > {ratio:.2f} -> {'OK' if validation else 'FALHOU'}",
                    f"Hash: {self.index['hash_algorithm'] if self.index else '-'}",
                    "",
                    f"Tempo de construcao: {format_seconds(self.build_stats['build_seconds'])}",
                    f"Colisoes: {self.build_stats['collision_count']:,}".replace(",", "."),
                    f"Taxa de colisoes: {self.build_stats['collision_rate']:.3f}%",
                    f"Buckets com overflow: {self.build_stats['overflow_bucket_count']:,}".replace(",", "."),
                    f"Paginas de overflow criadas: {self.build_stats['overflow_page_count']:,}".replace(",", "."),
                    f"Taxa de overflow: {self.build_stats['overflow_rate']:.3f}%",
                ]
            )

        self._set_text("dataset", "\n".join(lines))

    def _render_page_summary(self):
        # Mostra apenas a primeira e a ultima pagina.
        # O objetivo eh ilustrar como os dados foram divididos.
        if self.dataset is None:
            self._set_text(
                "pages",
                "As paginas serao exibidas apos a construcao do indice.\n\n"
                "A interface mostra apenas a primeira e a ultima pagina para evitar renderizacao pesada.",
            )
            return

        first_preview = preview_page(self.dataset, 1)
        last_preview = preview_page(self.dataset, self.dataset["page_count"])
        lines = [
            f"Quantidade total de paginas: {self.dataset['page_count']}",
            "",
            self._format_page_preview("Primeira pagina", first_preview),
            "",
            self._format_page_preview("Ultima pagina", last_preview),
        ]
        self._set_text("pages", "\n".join(lines))

    def _render_index_result(self):
        # Mostra o resultado da busca pelo indice hash.
        # Alem do resultado, tambem mostra o bucket acessado.
        if self.last_index_result is None:
            self._set_text(
                "index",
                "Execute 'Buscar via indice' para ver:\n"
                "- bucket acessado\n"
                "- pagina encontrada\n"
                "- custo estimado em leituras\n"
                "- tempo de busca",
            )
            return

        result = self.last_index_result
        lines = [
            f"Busca: {result['query']}",
            f"Status: {'ACHOU' if result['found'] else 'NAO ACHOU'}",
            f"Bucket calculado: {result['bucket_index']}",
            f"Leituras de bucket/overflow: {result['bucket_pages_read']}",
            f"Leituras de pagina de dados: {result['data_pages_read']}",
            f"Custo total estimado: {result['total_page_reads']}",
            f"Entradas examinadas no bucket: {result['bucket_entries_examined']}",
            f"Tempo: {format_seconds(result['elapsed_seconds'])}",
            f"Pagina encontrada: {result['page_number'] if result['page_number'] is not None else '-'}",
            "",
            self._format_bucket_snapshot(result["bucket_snapshot"]),
        ]

        if result["page_preview"] is not None:
            lines.extend(["", self._format_page_preview("Pagina confirmada", result["page_preview"])])

        self._set_text("index", "\n".join(lines))

    def _render_scan_result(self):
        # Mostra o resultado da busca sequencial.
        # Aqui o foco eh mostrar custo e quantidade de leitura.
        if self.last_scan_result is None:
            self._set_text(
                "scan",
                "Execute 'Table scan' para ver:\n"
                "- paginas lidas\n"
                "- registros lidos\n"
                "- pagina encontrada\n"
                "- custo e tempo",
            )
            return

        result = self.last_scan_result
        visited = ", ".join(str(page) for page in result["visited_pages_preview"]) or "-"
        if result["preview_truncated"]:
            visited = f"{visited}, ..."

        lines = [
            f"Busca: {result['query']}",
            f"Status: {'ACHOU' if result['found'] else 'NAO ACHOU'}",
            f"Paginas lidas: {result['pages_read']}",
            f"Registros lidos: {result['records_read']:,}".replace(",", "."),
            f"Custo total: {result['pages_read']}",
            f"Tempo: {format_seconds(result['elapsed_seconds'])}",
            f"Pagina encontrada: {result['page_number'] if result['page_number'] is not None else '-'}",
            "",
            "Paginas visitadas (amostra):",
            visited,
        ]

        if result["page_preview"] is not None:
            lines.extend(["", self._format_page_preview("Pagina encontrada", result["page_preview"])])

        self._set_text("scan", "\n".join(lines))

    def _render_comparison(self):
        # Junta os resultados das duas buscas para comparar custo e tempo.
        # Este painel existe para deixar clara a diferenca entre indice e scan.
        comparison = compare_searches(self.last_index_result, self.last_scan_result)
        lines = [
            "Comparacao entre indice e table scan:",
        ]

        if comparison is None:
            lines.extend(
                [
                    "",
                    "Execute as duas buscas para comparar tempo e custo.",
                ]
            )
        elif not comparison["same_query"]:
            lines.extend(
                [
                    "",
                    "As duas buscas foram feitas com termos diferentes.",
                    "Repita as duas operacoes com a mesma palavra para uma comparacao valida.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    f"Palavra: {comparison['query']}",
                    f"Diferenca de tempo (scan - indice): {format_seconds(comparison['time_saved_seconds'])}",
                    f"Diferenca de custo (scan - indice): {comparison['page_reads_saved']}",
                ]
            )

        if self.last_index_result is not None:
            lines.extend(
                [
                    "",
                    "Highlight do bucket acessado:",
                    self._format_bucket_snapshot(self.last_index_result["bucket_snapshot"]),
                ]
            )

        preview = None
        preview_title = "Ultima pagina relevante"
        if self.last_index_result is not None and self.last_index_result["page_preview"] is not None:
            preview = self.last_index_result["page_preview"]
            preview_title = "Pagina relevante da busca via indice"
        elif self.last_scan_result is not None and self.last_scan_result["page_preview"] is not None:
            preview = self.last_scan_result["page_preview"]
            preview_title = "Pagina relevante do table scan"

        if preview is not None:
            lines.extend(["", self._format_page_preview(preview_title, preview)])

        self._set_text("compare", "\n".join(lines))

    def _format_page_preview(self, title, preview):
        # Transforma o resumo de uma pagina em texto simples.
        # Este metodo so formata texto; ele nao faz calculo.
        if preview is None:
            return f"{title}\nSem registros."

        records = ", ".join(preview["first_records"]) if preview["first_records"] else "-"
        return (
            f"{title}\n"
            f"Pagina #{preview['page_number']}\n"
            f"Registros na pagina: {preview['record_count']}\n"
            f"Primeiros registros: {records}"
        )

    def _format_bucket_snapshot(self, snapshot):
        # Transforma o bucket encontrado em texto para a interface.
        # Isso ajuda a visualizar se a palavra ficou no primario ou no overflow.
        primary = self._format_entries(snapshot["primary_entries"])
        lines = [
            f"Bucket #{snapshot['bucket_index']}",
            f"Entradas totais no bucket: {snapshot['total_entries']}",
            f"Primario ({len(snapshot['primary_entries'])}): {primary}",
        ]

        if not snapshot["overflow_pages"]:
            lines.append("Overflow: nenhum")
            return "\n".join(lines)

        lines.append(f"Overflow: {len(snapshot['overflow_pages'])} pagina(s)")
        for overflow_number, entries in enumerate(snapshot["overflow_pages"], start=1):
            lines.append(f"Pagina overflow {overflow_number} ({len(entries)}): {self._format_entries(entries)}")
        return "\n".join(lines)

    def _format_entries(self, entries):
        # Mostra poucas entradas para o texto ficar legivel.
        # Se houver muitas entradas, a interface mostra so as primeiras.
        if not entries:
            return "-"

        preview = [f"{entry['key']}->{entry['page_number']}" for entry in entries[:5]]
        if len(entries) > 5:
            preview.append("...")
        return ", ".join(preview)


def launch_app():
    app = HashIndexApp()
    app.mainloop()
