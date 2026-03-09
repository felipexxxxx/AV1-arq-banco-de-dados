from time import perf_counter

from data_pages import get_page, preview_page


# Nomes exibidos na interface.
FNV1A_NAME = "FNV-1a"
POLYNOMIAL_NAME = "Polinomial"


def available_hash_algorithms():
    # A interface usa essa lista para preencher o combobox.
    return [FNV1A_NAME, POLYNOMIAL_NAME]


def fnv1a_hash(word, bucket_count):
    # Hash deterministica:
    # mesma palavra -> mesmo bucket.
    value = 2166136261

    # Mistura os bytes da palavra para gerar um numero.
    for byte in word.encode("utf-8"):
        value = value ^ byte
        value = (value * 16777619) & 0xFFFFFFFF

    # Limita o resultado para o intervalo de buckets [0..NB-1].
    return value % bucket_count


def polynomial_hash(word, bucket_count):
    # Segunda opcao de hash, tambem deterministica.
    value = 0
    for char in word:
        value = (value * 53 + ord(char)) % 2147483647
    return value % bucket_count


def calculate_bucket_count(record_count, bucket_capacity, load_factor=0.5):
    # Regra do trabalho:
    # NB > NR / FR
    if bucket_capacity <= 0:
        raise ValueError("FR deve ser maior que zero.")

    # Fator ajustavel (0 < fator <= 1):
    # - 1.0  -> alvo = FR (equivalente a usar FR completo no divisor)
    # - 0.5  -> alvo = FR/2 (mais buckets, menos overflow)
    # - 0.6  -> alvo = 60% de FR
    if load_factor <= 0 or load_factor > 1:
        raise ValueError("Fator de carga deve estar entre 0 e 1.")

    # Define quantos registros por bucket queremos em media.
    target_records_per_bucket = int(bucket_capacity * load_factor)
    if target_records_per_bucket < 1:
        target_records_per_bucket = 1

    # Ainda respeita NB > NR/FR, porque o divisor ficou menor.
    return (record_count // target_records_per_bucket) + 1


def validate_bucket_count(bucket_count, record_count, bucket_capacity):
    if bucket_capacity <= 0:
        return False
    return bucket_count > (record_count / bucket_capacity)


def create_hash_index(bucket_capacity, bucket_count, hash_algorithm=FNV1A_NAME):
    # Cria o indice vazio com NB buckets.
    if bucket_capacity <= 0:
        raise ValueError("FR deve ser maior que zero.")
    if bucket_count <= 0:
        raise ValueError("NB deve ser maior que zero.")

    if hash_algorithm == POLYNOMIAL_NAME:
        hash_function = polynomial_hash
    else:
        hash_function = fnv1a_hash

    buckets = []
    i = 0
    while i < bucket_count:
        # Cada bucket tem:
        # - primary: area principal (capacidade FR)
        # - overflow: lista de paginas de bucket overflow
        buckets.append({"primary": [], "overflow": []})
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
    # Reconstrui o indice do zero para os dados atuais.
    buckets = []
    i = 0
    while i < index["bucket_count"]:
        buckets.append({"primary": [], "overflow": []})
        i += 1

    index["buckets"] = buckets
    index["collision_count"] = 0
    index["overflow_pages_created"] = 0
    index["overflow_bucket_indexes"] = []

    start_time = perf_counter()

    # Percorre pagina por pagina e palavra por palavra.
    page_number = 1
    for page in dataset["pages"]:
        for word in page:
            bucket_number = index["hash_function"](word, index["bucket_count"])
            bucket = index["buckets"][bucket_number]
            item = {"key": word, "page_number": page_number}

            # Se cabe no primario, insere no primario.
            if len(bucket["primary"]) < index["bucket_capacity"]:
                bucket["primary"].append(item)
            else:
                # Colisao: so conta quando o primario esta cheio.
                index["collision_count"] += 1

                # Marca que esse bucket entrou em overflow.
                if bucket_number not in index["overflow_bucket_indexes"]:
                    index["overflow_bucket_indexes"].append(bucket_number)

                # Cria a primeira pagina de bucket overflow, se necessario.
                if len(bucket["overflow"]) == 0:
                    bucket["overflow"].append([])
                    index["overflow_pages_created"] += 1

                # Se a ultima pagina de overflow encheu, cria outra.
                last_overflow_page = bucket["overflow"][-1]
                if len(last_overflow_page) >= index["bucket_capacity"]:
                    bucket["overflow"].append([])
                    index["overflow_pages_created"] += 1
                    last_overflow_page = bucket["overflow"][-1]

                # Insere na pagina de overflow atual.
                last_overflow_page.append(item)

        page_number += 1

    build_time = perf_counter() - start_time

    if dataset["nr"] == 0:
        collision_rate = 0.0
    else:
        collision_rate = (index["collision_count"] / dataset["nr"]) * 100.0

    if index["bucket_count"] == 0:
        overflow_rate = 0.0
    else:
        overflow_rate = (len(index["overflow_bucket_indexes"]) / index["bucket_count"]) * 100.0

    overflow_page_count = index["overflow_pages_created"]

    return {
        "record_count": dataset["nr"],
        "page_count": dataset["page_count"],
        "bucket_count": index["bucket_count"],
        "bucket_capacity": index["bucket_capacity"],
        "collision_count": index["collision_count"],
        "overflow_bucket_count": len(index["overflow_bucket_indexes"]),
        "overflow_page_count": overflow_page_count,
        "build_seconds": build_time,
        "collision_rate": collision_rate,
        "overflow_rate": overflow_rate,
    }


def search_in_index(index, word, dataset):
    # Busca por indice:
    # 1) acha bucket pela hash
    # 2) procura no primario
    # 3) se precisar, procura no bucket overflow
    # 4) confirma a palavra na pagina de dados
    bucket_number = index["hash_function"](word, index["bucket_count"])
    bucket = index["buckets"][bucket_number]

    start_time = perf_counter()

    bucket_pages_read = 1
    entries_checked = 0
    page_number = None

    for item in bucket["primary"]:
        entries_checked += 1
        if item["key"] == word:
            page_number = item["page_number"]
            break

    if page_number is None:
        for overflow_page in bucket["overflow"]:
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

    if page_number is not None:
        data_pages_read = 1
        page = get_page(dataset, page_number)
        if word in page:
            found = True
            page_result = preview_page(dataset, page_number)

    total_entries = len(bucket["primary"])
    overflow_copy = []
    for overflow_page in bucket["overflow"]:
        overflow_copy.append(list(overflow_page))
        total_entries += len(overflow_page)

    search_time = perf_counter() - start_time

    return {
        "query": word,
        "found": found,
        "page_number": page_number if found else None,
        "bucket_index": bucket_number,
        "bucket_pages_read": bucket_pages_read,
        "data_pages_read": data_pages_read,
        # Regra solicitada pelo professor:
        # custo = apenas leitura da pagina de dados.
        "total_page_reads": data_pages_read,
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
