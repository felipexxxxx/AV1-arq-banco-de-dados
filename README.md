# Projeto 1 - Indice HASH

Implementacao em Python com interface grafica `Tkinter` para:

- carregar um arquivo TXT (uma palavra por linha);
- paginar os dados pelo tamanho de pagina informado;
- construir um indice hash com funcao deterministica;
- tratar colisoes com paginas de overflow encadeadas por bucket;
- buscar por indice;
- executar `table scan`;
- comparar custo e tempo entre indice e varredura sequencial.

## Estrutura

- `main.py`: ponto de entrada da aplicacao.
- `gui.py`: interface grafica e fluxo principal.
- `data_pages.py`: leitura do TXT, paginacao e previews de pagina.
- `hash_index.py`: hash deterministica, calculo de `NB`, buckets e overflow.
- `metrics.py`: `table scan`, comparacao entre buscas e utilitarios de tempo.

## Como rodar

No Windows, abra um terminal na pasta do projeto e execute um destes comandos:

```powershell
python main.py
```

Se o alias `python` do Windows Store estiver ativo e nao funcionar, use o interpretador real:

```powershell
& "C:\Users\felip\AppData\Local\Python\bin\python.exe" .\main.py
```

Tambem e possivel dar duplo clique em `main.py` se a associacao de arquivos `.py` estiver configurada.

## Fluxo de uso na interface

1. Clique em `Carregar TXT` e selecione o arquivo de palavras.
2. Informe `Tamanho da pagina` (maior que zero).
3. Informe `FR` (capacidade primaria do bucket, maior que zero).
4. Escolha `Fator de carga NB` (`0.5` a `1.0`).
5. Escolha a hash deterministica (`FNV-1a` ou `Polinomial`).
6. Clique em `Construir indice`.
7. Digite uma palavra e use `Buscar via indice` e `Table scan`.
8. Veja os paineis de metricas, paginas, resultados e comparacao.

## Observacoes de implementacao

- `NB` e calculado automaticamente com fator ajustavel na GUI: `NB = (NR // alvo) + 1`, onde `alvo = int(FR * fator)` (minimo 1).
- Se `fator = 1.0`, o calculo fica equivalente ao formato `NB = (NR // FR) + 1`.
- Valores menores (ex.: `0.5`, `0.6`) aumentam `NB` e tendem a reduzir overflow.
- Colisao so e contabilizada quando o bucket primario (`FR`) ja esta cheio e e necessario inserir fora dele.
- Overflow usa encadeamento de paginas por bucket, cada pagina de overflow com capacidade `FR`.
- A interface mostra apenas resumos, o bucket acessado e previews de paginas, evitando renderizacao de estruturas gigantes.
- O sistema foi pensado para arquivos grandes (como o dataset incluso), mantendo os registros em memoria e exibindo somente amostras.

## Dataset incluso

O repositorio ja contem exemplos em `english-words-master`, incluindo `words_alpha.txt`.
