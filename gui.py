from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from data_pages import PagePreview, PagedDataSet, load_words_from_txt
from hash_index import (
    FNV1A_NAME,
    BuildStats,
    BucketSnapshot,
    HashIndex,
    IndexSearchResult,
    available_hash_algorithms,
    calculate_bucket_count,
    validate_bucket_count,
)
from metrics import SearchComparison, TableScanResult, compare_searches, format_seconds, table_scan


class HashIndexApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Projeto 1 - Indice HASH")
        self.geometry("1280x860")
        self.minsize(1080, 720)

        self.base_dir = Path(__file__).resolve().parent
        self.default_data_dir = self.base_dir / "english-words-master"

        self.records: list[str] = []
        self.dataset: PagedDataSet | None = None
        self.index: HashIndex | None = None
        self.build_stats: BuildStats | None = None
        self.last_index_result: IndexSearchResult | None = None
        self.last_scan_result: TableScanResult | None = None

        self.file_path_var = tk.StringVar()
        self.record_count_var = tk.StringVar(value="NR: -")
        self.page_size_var = tk.StringVar(value="128")
        self.fr_var = tk.StringVar(value="4")
        self.hash_var = tk.StringVar(value=FNV1A_NAME)
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Carregue um arquivo TXT com uma palavra por linha.")

        self._busy = False
        self._buttons: list[ttk.Button] = []
        self._text_widgets: dict[str, tk.Text] = {}

        self._configure_style()
        self._build_layout()
        self._render_dataset_summary()
        self._render_page_summary()
        self._render_index_result()
        self._render_scan_result()
        self._render_comparison()

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", padding=6)
        style.configure("TLabelframe", padding=8)
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(10, 6))
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))

    def _build_layout(self) -> None:
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
        self._buttons.append(load_button)

        path_entry = ttk.Entry(controls, textvariable=self.file_path_var, state="readonly")
        path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        record_label = ttk.Label(controls, textvariable=self.record_count_var, style="Header.TLabel")
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
        self._buttons.append(build_button)

        search = ttk.LabelFrame(container, text="3. Buscas")
        search.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        search.columnconfigure(1, weight=1)

        ttk.Label(search, text="Palavra").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(search, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        search_entry.bind("<Return>", lambda _event: self._search_by_index())

        index_button = ttk.Button(search, text="Buscar via indice", command=self._search_by_index)
        index_button.grid(row=0, column=2, sticky="w", padx=(0, 8))
        self._buttons.append(index_button)

        scan_button = ttk.Button(search, text="Table scan", command=self._run_table_scan)
        scan_button.grid(row=0, column=3, sticky="w")
        self._buttons.append(scan_button)

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

    def _make_text_box(self, parent: ttk.LabelFrame, height: int) -> tk.Text:
        text = tk.Text(parent, height=height, wrap="word", padx=10, pady=10)
        text.grid(row=0, column=0, sticky="nsew")
        text.configure(state="disabled")
        return text

    def _set_text(self, key: str, content: str) -> None:
        widget = self._text_widgets[key]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _set_busy(self, value: bool, status_text: str | None = None) -> None:
        self._busy = value
        for button in self._buttons:
            if value:
                button.state(["disabled"])
            else:
                button.state(["!disabled"])
        if status_text:
            self.status_var.set(status_text)

    def _run_task(
        self,
        task_label: str,
        worker: Callable[[], object],
        on_success: Callable[[object], None],
    ) -> None:
        if self._busy:
            return

        self._set_busy(True, f"{task_label}...")

        def job() -> None:
            try:
                result = worker()
            except Exception as exc:
                self.after(0, lambda exc=exc: self._handle_task_error(task_label, exc))
                return

            self.after(0, lambda result=result: self._handle_task_success(task_label, result, on_success))

        threading.Thread(target=job, daemon=True).start()

    def _handle_task_error(self, task_label: str, error: Exception) -> None:
        self._set_busy(False, f"Falha ao executar: {task_label}.")
        messagebox.showerror("Erro", str(error))

    def _handle_task_success(
        self,
        task_label: str,
        result: object,
        on_success: Callable[[object], None],
    ) -> None:
        on_success(result)
        self._set_busy(False, f"{task_label} concluido.")

    def _load_file(self) -> None:
        initial_dir = self.default_data_dir if self.default_data_dir.exists() else self.base_dir
        selected = filedialog.askopenfilename(
            title="Selecione um arquivo TXT",
            initialdir=initial_dir,
            filetypes=[("Arquivos TXT", "*.txt"), ("Todos os arquivos", "*.*")],
        )
        if not selected:
            return

        self.file_path_var.set(selected)
        self._run_task(
            "Carregando arquivo",
            worker=lambda: load_words_from_txt(selected),
            on_success=lambda result: self._on_file_loaded(selected, result),
        )

    def _on_file_loaded(self, selected: str, loaded_records: object) -> None:
        self.records = loaded_records if isinstance(loaded_records, list) else list(loaded_records)
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

    def _build_index(self) -> None:
        if not self.records:
            messagebox.showwarning("Arquivo", "Carregue um arquivo TXT antes de construir o indice.")
            return

        try:
            page_size = self._parse_positive_int(self.page_size_var.get(), "Tamanho da pagina")
            fr = self._parse_positive_int(self.fr_var.get(), "FR")
        except ValueError as exc:
            messagebox.showwarning("Parametros", str(exc))
            return

        hash_algorithm = self.hash_var.get()

        def worker() -> tuple[PagedDataSet, HashIndex, BuildStats]:
            dataset = PagedDataSet(self.records, page_size)
            bucket_count = calculate_bucket_count(dataset.nr, fr)
            if not validate_bucket_count(bucket_count, dataset.nr, fr):
                raise ValueError("NB calculado nao atende a validacao NB > NR/FR.")
            index = HashIndex(bucket_capacity=fr, bucket_count=bucket_count, hash_algorithm=hash_algorithm)
            stats = index.build(dataset)
            return dataset, index, stats

        self._run_task("Construindo indice", worker=worker, on_success=self._on_index_built)

    def _on_index_built(self, payload: object) -> None:
        dataset, index, stats = payload
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

    def _search_by_index(self) -> None:
        if self.index is None or self.dataset is None:
            messagebox.showwarning("Indice", "Construa o indice antes de buscar.")
            return

        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Busca", "Informe uma palavra para pesquisar.")
            return

        self._run_task(
            "Executando busca via indice",
            worker=lambda: self.index.search(query, self.dataset),
            on_success=self._on_index_search_complete,
        )

    def _on_index_search_complete(self, result: object) -> None:
        self.last_index_result = result
        self._render_index_result()
        self._render_comparison()

    def _run_table_scan(self) -> None:
        if self.dataset is None:
            messagebox.showwarning("Dados", "Construa o indice para preparar as paginas antes do table scan.")
            return

        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Busca", "Informe uma palavra para pesquisar.")
            return

        self._run_task(
            "Executando table scan",
            worker=lambda: table_scan(self.dataset, query),
            on_success=self._on_table_scan_complete,
        )

    def _on_table_scan_complete(self, result: object) -> None:
        self.last_scan_result = result
        self._render_scan_result()
        self._render_comparison()

    def _parse_positive_int(self, value: str, label: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"{label} deve ser um inteiro positivo.") from exc

        if parsed <= 0:
            raise ValueError(f"{label} deve ser maior que zero.")
        return parsed

    def _render_dataset_summary(self) -> None:
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
            ratio = self.build_stats.record_count / self.build_stats.bucket_capacity
            validation = validate_bucket_count(
                self.build_stats.bucket_count,
                self.build_stats.record_count,
                self.build_stats.bucket_capacity,
            )
            lines.extend(
                [
                    "",
                    f"Tamanho da pagina: {self.dataset.page_size}",
                    f"Paginas de dados: {self.dataset.page_count}",
                    f"FR: {self.build_stats.bucket_capacity}",
                    f"NB calculado: {self.build_stats.bucket_count}",
                    f"Validacao NB > NR/FR: {self.build_stats.bucket_count} > {ratio:.2f} -> {'OK' if validation else 'FALHOU'}",
                    f"Hash: {self.index.hash_algorithm if self.index else '-'}",
                    "",
                    f"Tempo de construcao: {format_seconds(self.build_stats.build_seconds)}",
                    f"Colisoes: {self.build_stats.collision_count:,}".replace(",", "."),
                    f"Taxa de colisoes: {self.build_stats.collision_rate:.3f}%",
                    f"Buckets com overflow: {self.build_stats.overflow_bucket_count:,}".replace(",", "."),
                    f"Paginas de overflow criadas: {self.build_stats.overflow_page_count:,}".replace(",", "."),
                    f"Taxa de overflow: {self.build_stats.overflow_rate:.3f}%",
                ]
            )

        self._set_text("dataset", "\n".join(lines))

    def _render_page_summary(self) -> None:
        if self.dataset is None:
            self._set_text(
                "pages",
                "As paginas serao exibidas apos a construcao do indice.\n\n"
                "A interface mostra apenas a primeira e a ultima pagina para evitar renderizacao pesada.",
            )
            return

        first_preview = self.dataset.first_preview()
        last_preview = self.dataset.last_preview()
        lines = [
            f"Quantidade total de paginas: {self.dataset.page_count}",
            "",
            self._format_page_preview("Primeira pagina", first_preview),
            "",
            self._format_page_preview("Ultima pagina", last_preview),
        ]
        self._set_text("pages", "\n".join(lines))

    def _render_index_result(self) -> None:
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
            f"Busca: {result.query}",
            f"Status: {'ACHOU' if result.found else 'NAO ACHOU'}",
            f"Bucket calculado: {result.bucket_index}",
            f"Leituras de bucket/overflow: {result.bucket_pages_read}",
            f"Leituras de pagina de dados: {result.data_pages_read}",
            f"Custo total estimado: {result.total_page_reads}",
            f"Entradas examinadas no bucket: {result.bucket_entries_examined}",
            f"Tempo: {format_seconds(result.elapsed_seconds)}",
            f"Pagina encontrada: {result.page_number if result.page_number is not None else '-'}",
            "",
            self._format_bucket_snapshot(result.bucket_snapshot),
        ]

        if result.page_preview is not None:
            lines.extend(["", self._format_page_preview("Pagina confirmada", result.page_preview)])

        self._set_text("index", "\n".join(lines))

    def _render_scan_result(self) -> None:
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
        visited = ", ".join(str(page) for page in result.visited_pages_preview) or "-"
        if result.preview_truncated:
            visited = f"{visited}, ..."

        lines = [
            f"Busca: {result.query}",
            f"Status: {'ACHOU' if result.found else 'NAO ACHOU'}",
            f"Paginas lidas: {result.pages_read}",
            f"Registros lidos: {result.records_read:,}".replace(",", "."),
            f"Custo total: {result.pages_read}",
            f"Tempo: {format_seconds(result.elapsed_seconds)}",
            f"Pagina encontrada: {result.page_number if result.page_number is not None else '-'}",
            "",
            "Paginas visitadas (amostra):",
            visited,
        ]

        if result.page_preview is not None:
            lines.extend(["", self._format_page_preview("Pagina encontrada", result.page_preview)])

        self._set_text("scan", "\n".join(lines))

    def _render_comparison(self) -> None:
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
        elif not comparison.same_query:
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
                    f"Palavra: {comparison.query}",
                    f"Diferenca de tempo (scan - indice): {format_seconds(comparison.time_saved_seconds)}",
                    f"Diferenca de custo (scan - indice): {comparison.page_reads_saved}",
                ]
            )

        if self.last_index_result is not None:
            lines.extend(
                [
                    "",
                    "Highlight do bucket acessado:",
                    self._format_bucket_snapshot(self.last_index_result.bucket_snapshot),
                ]
            )

        preview = None
        preview_title = "Ultima pagina relevante"
        if self.last_index_result is not None and self.last_index_result.page_preview is not None:
            preview = self.last_index_result.page_preview
            preview_title = "Pagina relevante da busca via indice"
        elif self.last_scan_result is not None and self.last_scan_result.page_preview is not None:
            preview = self.last_scan_result.page_preview
            preview_title = "Pagina relevante do table scan"

        if preview is not None:
            lines.extend(["", self._format_page_preview(preview_title, preview)])

        self._set_text("compare", "\n".join(lines))

    def _format_page_preview(self, title: str, preview: PagePreview | None) -> str:
        if preview is None:
            return f"{title}\nSem registros."

        records = ", ".join(preview.first_records) if preview.first_records else "-"
        return (
            f"{title}\n"
            f"Pagina #{preview.page_number}\n"
            f"Registros na pagina: {preview.record_count}\n"
            f"Primeiros registros: {records}"
        )

    def _format_bucket_snapshot(self, snapshot: BucketSnapshot) -> str:
        primary = self._format_entries(snapshot.primary_entries)
        lines = [
            f"Bucket #{snapshot.bucket_index}",
            f"Entradas totais no bucket: {snapshot.total_entries}",
            f"Primario ({len(snapshot.primary_entries)}): {primary}",
        ]

        if not snapshot.overflow_pages:
            lines.append("Overflow: nenhum")
            return "\n".join(lines)

        lines.append(f"Overflow: {len(snapshot.overflow_pages)} pagina(s)")
        for overflow_number, entries in enumerate(snapshot.overflow_pages, start=1):
            lines.append(f"Pagina overflow {overflow_number} ({len(entries)}): {self._format_entries(entries)}")
        return "\n".join(lines)

    def _format_entries(self, entries: tuple) -> str:
        if not entries:
            return "-"

        preview = [f"{entry.key}->{entry.page_number}" for entry in entries[:5]]
        if len(entries) > 5:
            preview.append("...")
        return ", ".join(preview)


def launch_app() -> None:
    app = HashIndexApp()
    app.mainloop()
