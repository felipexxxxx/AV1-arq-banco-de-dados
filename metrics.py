from time import perf_counter

from data_pages import preview_page


def format_seconds(seconds):
    # Mostra em ms e em s para evitar confusao de leitura.
    ms = seconds * 1000.0
    if seconds < 1:
        text = f"{ms:.3f} ms ({seconds:.4f} s)"
    else:
        text = f"{seconds:.3f} s ({ms:.1f} ms)"
    return text.replace(".", ",")


def table_scan(dataset, query, preview_limit=20):
    # Le pagina por pagina ate encontrar a palavra.
    #
    # Diferenca para a busca por indice:
    # aqui nao usamos hash nem bucket.
    # O programa simplesmente vai lendo na ordem: pagina 1, pagina 2, pagina 3...
    start_time = perf_counter()

    pages_read = 0
    records_read = 0
    visited_pages = []
    preview_truncated = False
    found = False
    page_number = None
    page_result = None

    # Este contador existe so porque as paginas na interface comecam em 1.
    current_page_number = 1

    for page in dataset["pages"]:
        pages_read += 1

        # Guardamos so uma amostra das paginas visitadas para a tela nao ficar gigante.
        if len(visited_pages) < preview_limit:
            visited_pages.append(current_page_number)
        else:
            preview_truncated = True

        # Aqui a busca eh registro por registro.
        for word in page:
            records_read += 1

            if word == query:
                found = True
                page_number = current_page_number
                page_result = preview_page(dataset, current_page_number)
                break

        if found:
            break

        current_page_number += 1

    # Tempo gasto no table scan.
    search_time = perf_counter() - start_time

    return {
        "query": query,
        "found": found,
        "page_number": page_number,
        "pages_read": pages_read,
        "records_read": records_read,
        "elapsed_seconds": search_time,
        "visited_pages_preview": visited_pages,
        "preview_truncated": preview_truncated,
        "page_preview": page_result,
    }


def compare_searches(index_result, scan_result):
    # Compara o resultado da busca por indice com o table scan.
    if index_result is None or scan_result is None:
        return None

    if index_result["query"] != scan_result["query"]:
        # Se as palavras forem diferentes, nao faz sentido comparar.
        return {
            "same_query": False,
            "query": index_result["query"],
            "time_saved_seconds": 0.0,
            "page_reads_saved": 0,
        }

    # Se a palavra for a mesma, mostramos:
    # - diferenca de tempo
    # - diferenca de custo em leituras
    return {
        "same_query": True,
        "query": index_result["query"],
        "time_saved_seconds": scan_result["elapsed_seconds"] - index_result["elapsed_seconds"],
        "page_reads_saved": scan_result["pages_read"] - index_result["total_page_reads"],
    }
