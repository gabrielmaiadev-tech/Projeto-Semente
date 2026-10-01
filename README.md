# Vigia

API de observabilidade que recebe erros de aplicações, agrupa ocorrências repetidas e transforma logs em métricas consultáveis. Projeto de portfólio com FastAPI, SQLite, testes automatizados e execução em Docker.

## O problema

Logs de erro costumam se repetir e dificultam perceber quais falhas estão se espalhando. O Vigia recebe eventos de diferentes serviços e consolida mensagens equivalentes em incidentes, contando cada nova ocorrência sem perder o histórico.

## Comece aqui

Requisitos: Python 3.11 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn vigia.main:app --reload
```

A documentação interativa fica em `http://127.0.0.1:8000/docs`. O banco SQLite é criado automaticamente em `data/vigia.db`. Para mudar o local, defina `VIGIA_DB_PATH`.

## Exemplo

Envie o mesmo erro mais de uma vez. O Vigia retorna o mesmo incidente com `occurrences` incrementado.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/events \
	-H 'Content-Type: application/json' \
	-d '{"service":"checkout","level":"error","message":"Timeout connecting to payment provider"}'
```

Consulte incidentes e métricas:

```bash
curl 'http://127.0.0.1:8000/api/v1/incidents?level=error&service=checkout'
curl http://127.0.0.1:8000/api/v1/metrics
```

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/health` | Verifica a aplicação e a conexão com o banco |
| `POST` | `/api/v1/events` | Registra uma ocorrência e agrupa erros equivalentes |
| `GET` | `/api/v1/incidents` | Lista incidentes; aceita `level`, `service`, `limit` e `offset` |
| `GET` | `/api/v1/metrics` | Retorna incidentes, ocorrências, distribuição por nível e serviços mais afetados |

Níveis aceitos: `debug`, `info`, `warning`, `error` e `critical`. A impressão digital considera serviço, nível e mensagem normalizada (maiúsculas/minúsculas e espaços não alteram o agrupamento).

## Docker

```bash
docker build -t vigia-api .
docker run --rm -p 8000:8000 -v vigia-data:/app/data vigia-api
```

## Desenvolvimento

```bash
pytest
```

Os testes usam um banco temporário e cobrem agrupamento, filtros, métricas e health check. O GitHub Actions executa a suíte em cada push e pull request.

## Decisões técnicas

- SQLite mantém o projeto fácil de executar, enquanto o acesso ao banco fica isolado para permitir uma migração futura.
- A deduplicação acontece no banco com uma restrição única e `UPSERT`, evitando uma janela entre leitura e gravação.
- A API valida a entrada, limita paginação e expõe documentação OpenAPI automaticamente.

## Próximos passos

- Autenticação por chave de API para ingestão multi-tenant.
- Retenção configurável e resolução de incidentes.
- Alertas por limiar e exportação para Prometheus.