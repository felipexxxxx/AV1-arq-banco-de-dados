import os


def load_words_from_txt(file_path):
    # Esta funcao abre o arquivo .txt e devolve uma lista de palavras.
    # Cada linha do arquivo vira um registro.
    if not os.path.exists(file_path):
        raise FileNotFoundError("Arquivo nao encontrado: " + str(file_path))

    words = []

    # "errors=ignore" evita que o programa pare se alguma linha tiver
    # caractere estranho no arquivo.
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
        for raw_line in file_handle:
            # strip() remove espacos e a quebra de linha do final.
            word = raw_line.strip()

            # So adicionamos linhas que realmente tenham conteudo.
            if word:
                words.append(word)

    if len(words) == 0:
        raise ValueError("O arquivo esta vazio ou nao possui palavras validas.")

    return words


def create_dataset(records, page_size):
    # Esta funcao cria a estrutura principal dos dados.
    # Em vez de usar classe, usamos um dicionario simples.
    #
    # O dicionario final guarda:
    # - "records": lista completa de palavras
    # - "pages": lista de paginas
    # - "page_size": quantos registros cabem em cada pagina
    # - "nr": numero total de registros
    # - "page_count": numero total de paginas
    if page_size <= 0:
        raise ValueError("O tamanho da pagina deve ser maior que zero.")

    pages = []
    all_records = list(records)
    start = 0

    # Quebra a lista grande em paginas menores.
    # Exemplo:
    # se page_size = 3, a lista vira blocos de 3 em 3.
    while start < len(all_records):
        end = start + page_size
        pages.append(all_records[start:end])
        start = end

    return {
        "records": all_records,
        "pages": pages,
        "page_size": page_size,
        "nr": len(all_records),
        "page_count": len(pages),
    }


def get_page(dataset, page_number):
    # Na tela a pagina comeca em 1.
    # Mas na lista do Python a primeira posicao eh 0.
    # Por isso usamos page_number - 1.
    if page_number < 1 or page_number > dataset["page_count"]:
        raise IndexError("Numero de pagina fora do intervalo.")

    return list(dataset["pages"][page_number - 1])


def preview_page(dataset, page_number, preview_limit=5):
    # Esta funcao monta um pequeno resumo da pagina.
    # Ela existe so para a interface nao tentar mostrar tudo.
    #
    # O resumo mostra:
    # - numero da pagina
    # - quantos registros ela tem
    # - os primeiros registros da pagina
    page = get_page(dataset, page_number)

    return {
        "page_number": page_number,
        "record_count": len(page),
        "first_records": list(page[:preview_limit]),
    }
