# Runbook: atualização, promoção e recuperação de dados/ML

## Estado seguro

O estado seguro é `OBSERVATION_ONLY`: nenhuma recomendação pode aumentar exposição. Se qualquer gate falhar, preserve o último artefato aprovado, marque o candidato como rejeitado e não tente “corrigir” o resultado removendo períodos.

## Atualização controlada

1. Desative promoção/recalibração automática no scheduler durante a janela de manutenção.
2. Atualize dados em área de staging, sem sobrescrever o snapshot aprovado.
3. Valide schema, timezone, sessões, duplicidade, OHLCV, missing, outliers, frescor e divergência entre fontes.
4. Gere manifesto com provider, período, `fetched_at`, `available_at`, hashes, commit e configuração.
5. Execute a auditoria de release. Um retorno diferente de zero bloqueia a sequência.
6. Treine como candidato. O script deve produzir `data/probability_model.candidate.json`; rejeição nunca altera o ativo.
7. Revise métricas por fold/regime e compare hashes. Registre aprovação humana antes de promover.
8. Faça deploy em shadow e monitore parity, latência, missing e drift antes de paper trading.

## Incidente de dados

1. Acione o kill switch externo e force `OBSERVATION_ONLY`.
2. Registre início, símbolos, campos, provider e versões afetadas.
3. Quarentene o snapshot suspeito; não o apague nem o misture ao histórico aprovado.
4. Reconcilie com uma segunda fonte e determine o primeiro timestamp incorreto.
5. Recrie features, labels, modelos e decisões derivadas a partir do último snapshot íntegro.
6. Execute todos os gates e compare o impacto antes/depois.
7. Só restaure o serviço após aprovação; mantenha o relatório do incidente e hashes.

## Rollback de modelo

O repositório ainda não possui registry de artefatos completo. Até ele existir, não promova modelo para capital. O desenho mínimo deve manter versões imutáveis `candidate`, `approved` e `retired`, seus hashes, quem aprovou, quando, dataset/config/commit e um alias atômico `current`. O rollback deve trocar apenas o alias e ser ensaiado trimestralmente.

## Critérios de bloqueio imediato

- dado além do SLA, timezone ambíguo, schema novo ou fonte divergente;
- hash divergente do manifesto;
- feature ausente, NaN/inf inesperado ou drift acima do threshold;
- candidato sem teste final, abaixo do baseline ou sem calibração;
- erro de parity treino/inferência;
- perda, drawdown ou exposição acima dos limites;
- ausência de logs, registry, responsável ou aprovação.
