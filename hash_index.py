from time import perf_counter

from data_pages import get_page, preview_page


FNV1A_NAME = "FNV-1a"
POLYNOMIAL_NAME = "Polinomial"


def available_hash_algorithms():
    # A interface usa esta lista para preencher o campo de escolha de hash.
    return [FNV1A_NAME, POLYNOMIAL_NAME]


def fnv1a_hash(word, bucket_count):
    # Esta eh uma hash deterministica.
    # "Deterministica" significa:
    # a mesma palavra sempre cai no mesmo bucket.
    #
    # No final, ela sempre devolve um numero entre 0 e bucket_count - 1.
    value = 2166136261

    # A palavra eh lida byte por byte.
    # Cada byte altera o valor final.
    for byte in word.encode("utf-8"):
        value = value ^ byte
        value = (value * 16777619) & 0xFFFFFFFF

    # O operador % limita o resultado ao intervalo valido de buckets.
    return value % bucket_count


def polynomial_hash(word, bucket_count):
    # Outra hash simples e deterministica.
    # Em vez de trabalhar com bytes, ela trabalha letra por letra.
    value = 0

    # ord(char) transforma a letra em numero.
    for char in word:
        value = (value * 53 + ord(char)) % 2147483647

    return value % bucket_count


def calculate_bucket_count(record_count, bucket_capacity):
    # Regra do trabalho:
    # NB > NR / FR
    #
    # A forma mais simples de garantir isso eh:
    # NB = (NR // FR) + 1
    if bucket_capacity <= 0:
        raise ValueError("FR deve ser maior que zero.")

    return (record_count // bucket_capacity) + 1


def validate_bucket_count(bucket_count, record_count, bucket_capacity):
    # Esta funcao apenas confere se o NB calculado respeita a regra.
    if bucket_capacity <= 0:
        return False

    return bucket_count > (record_count / bucket_capacity)


def create_hash_index(bucket_capacity, bucket_count, hash_algorithm=FNV1A_NAME):
    # Esta funcao cria o indice vazio.
    #
    # Estrutura usada:
    # - o indice todo eh um dicionario
    # - dentro dele existe uma lista de buckets
    # - cada bucket tem:
    #   - "primary": area principal
    #   - "overflow": paginas extras
    if bucket_capacity <= 0:
        raise ValueError("FR deve ser maior que zero.")

    if bucket_count <= 0:
        raise ValueError("NB deve ser maior que zero.")

    if hash_algorithm == POLYNOMIAL_NAME:
        hash_function = polynomial_hash
    else:
        hash_function = fnv1a_hash

    # Aqui criamos todos os buckets vazios.
    buckets = []
    i = 0
    while i < bucket_count:
        buckets.append(
            {
                "primary": [],
                "overflow": [],
            }
        )
        i += 1

    return {
        "bucket_capacity": bucket_capacity,
        "bucket_count": bucket_count,
        "hash_algorithm": hash_algorithm,
        "hash_function": hash_function,
        "buckets": buckets,
        "collision_count": 0,
        "overflow_pages_created": 0,
        "overflow_bucket_indexes": [],
    }


def build_index(index, dataset):
    # Esta funcao monta o indice completo.
    #
    # Ela percorre:
    # 1. cada pagina
    # 2. cada palavra da pagina
    # 3. calcula o bucket pela hash
    # 4. guarda (palavra -> numero_da_pagina)
    #
    # Se o bucket principal lotar, entra em overflow.

    # Primeiro, limpamos o indice para reconstruir tudo do zero.
    buckets = []
    i = 0
    while i < index["bucket_count"]:
        buckets.append(
            {
                "primary": [],
                "overflow": [],
            }
        )
        i += 1

    index["buckets"] = buckets
    index["collision_count"] = 0
    index["overflow_pages_created"] = 0
    index["overflow_bucket_indexes"] = []

    start_time = perf_counter()

    # page_number comeca em 1 porque a interface mostra paginas assim.
    page_number = 1
    for page in dataset["pages"]:
        for word in page:
            # A hash diz qual bucket essa palavra deve usar.
            bucket_number = index["hash_function"](word, index["bucket_count"])
            bucket = index["buckets"][bucket_number]

            # O indice guarda:
            # - a chave (palavra)
            # - a pagina onde a palavra esta
            item = {
                "key": word,
                "page_number": page_number,
            }

            # Se ainda cabe no bucket principal, colocamos ali.
            if len(bucket["primary"]) < index["bucket_capacity"]:
                bucket["primary"].append(item)
            else:
                # So contamos colisao quando o bucket principal ja esta cheio.
                index["collision_count"] += 1

                # Guardamos o numero do bucket que entrou em overflow.
                # Isso eh usado depois para calcular a taxa de overflow.
                if bucket_number not in index["overflow_bucket_indexes"]:
                    index["overflow_bucket_indexes"].append(bucket_number)

                # Se ainda nao existe overflow, criamos a primeira pagina extra.
                if len(bucket["overflow"]) == 0:
                    bucket["overflow"].append([])
                    index["overflow_pages_created"] += 1

                # Pegamos a ultima pagina de overflow criada.
                last_page = bucket["overflow"][-1]

                # Se essa ultima pagina ja lotou, criamos outra.
                if len(last_page) >= index["bucket_capacity"]:
                    bucket["overflow"].append([])
                    index["overflow_pages_created"] += 1
                    last_page = bucket["overflow"][-1]

                # Finalmente colocamos a palavra na ultima pagina de overflow.
                last_page.append(item)

        page_number += 1

    # Medimos o tempo total da construcao do indice.
    build_time = perf_counter() - start_time

    if dataset["nr"] == 0:
        collision_rate = 0.0
    else:
        # Taxa de colisao = colisoes / total de registros.
        collision_rate = (index["collision_count"] / dataset["nr"]) * 100.0

    if index["bucket_count"] == 0:
        overflow_rate = 0.0
    else:
        # Taxa de overflow = buckets com overflow / total de buckets.
        overflow_rate = (len(index["overflow_bucket_indexes"]) / index["bucket_count"]) * 100.0

    return {
        "record_count": dataset["nr"],
        "page_count": dataset["page_count"],
        "bucket_count": index["bucket_count"],
        "bucket_capacity": index["bucket_capacity"],
        "collision_count": index["collision_count"],
        "overflow_bucket_count": len(index["overflow_bucket_indexes"]),
        "overflow_page_count": index["overflow_pages_created"],
        "build_seconds": build_time,
        "collision_rate": collision_rate,
        "overflow_rate": overflow_rate,
    }


def search_in_index(index, word, dataset):
    # Esta funcao faz a busca pelo indice.
    #
    # Passos:
    # 1. aplica a hash na palavra
    # 2. vai ao bucket calculado
    # 3. procura no bucket principal
    # 4. se precisar, procura no overflow
    # 5. pega a pagina encontrada
    # 6. le a pagina para confirmar a palavra
    bucket_number = index["hash_function"](word, index["bucket_count"])
    bucket = index["buckets"][bucket_number]

    start_time = perf_counter()

    # Sempre lemos pelo menos 1 estrutura do indice:
    # o bucket principal.
    bucket_pages_read = 1

    # Conta quantas entradas foram comparadas.
    entries_checked = 0

    # Aqui vamos guardar a pagina encontrada no indice.
    page_number = None

    # Primeiro, olhamos o bucket principal.
    for item in bucket["primary"]:
        entries_checked += 1
        if item["key"] == word:
            page_number = item["page_number"]
            break

    # Se nao achou no principal, percorremos as paginas de overflow.
    if page_number is None:
        for overflow_page in bucket["overflow"]:
            # Cada pagina de overflow visitada conta como mais uma leitura.
            bucket_pages_read += 1

            for item in overflow_page:
                entries_checked += 1
                if item["key"] == word:
                    page_number = item["page_number"]
                    break

            if page_number is not None:
                break

    data_pages_read = 0
    found = False
    page_result = None

    # Se o indice apontou uma pagina, lemos essa pagina de dados.
    # Isso simula o acesso ao "disco" no trabalho.
    if page_number is not None:
        data_pages_read = 1
        page = get_page(dataset, page_number)

        # Confirmamos se a palavra realmente esta nessa pagina.
        if word in page:
            found = True
            page_result = preview_page(dataset, page_number)

    # Este bloco prepara uma copia simples do bucket para mostrar na interface.
    total_entries = len(bucket["primary"])
    overflow_copy = []

    for overflow_page in bucket["overflow"]:
        overflow_copy.append(list(overflow_page))
        total_entries += len(overflow_page)

    # Medimos o tempo gasto so nesta busca.
    search_time = perf_counter() - start_time

    return {
        "query": word,
        "found": found,
        "page_number": page_number if found else None,
        "bucket_index": bucket_number,
        "bucket_pages_read": bucket_pages_read,
        "data_pages_read": data_pages_read,
        "total_page_reads": data_pages_read, # Corrigido: o custo total não considera a leitura nos buckets, somente na página
        "bucket_entries_examined": entries_checked,
        "elapsed_seconds": search_time,
        "bucket_snapshot": {
            "bucket_index": bucket_number,
            "primary_entries": list(bucket["primary"]),
            "overflow_pages": overflow_copy,
            "total_entries": total_entries,
        },
        "page_preview": page_result,
    }
