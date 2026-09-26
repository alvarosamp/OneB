import { Plus, X } from 'lucide-react';
import type { RuleType } from '../types';
import { RULE_META, type RuleConditionsBuilder } from '../hooks/useRuleConditions';
import { Button, ICON, Input, Select } from './ui';
import styles from './RuleConditionBuilder.module.css';

/** Editor de condições de uma regra de alerta (lógica E/OU, parâmetros e intervalo mínimo). */
export function RuleConditionBuilder({ builder }: { builder: RuleConditionsBuilder }) {
  return (
    <div className={styles.builder}>
      <Select label="Disparar quando" className={styles.logic} value={builder.logic} onChange={(e) => builder.setLogic(e.target.value as 'ALL' | 'ANY')}>
        <option value="ALL">todas as condições forem verdadeiras (E)</option>
        <option value="ANY">qualquer condição for verdadeira (OU)</option>
      </Select>

      <ol className={styles.rows}>
        {builder.rows.map((row, i) => {
          const meta = RULE_META[row.rule_type];
          return (
            <li key={row.key} className={styles.row}>
              <span className={styles.index}>{i + 1}</span>
              <Select label="Condição" hideLabel={i > 0} value={row.rule_type} onChange={(e) => builder.updateCondition(row.key, { rule_type: e.target.value as RuleType })} className={styles.type}>
                {Object.entries(RULE_META).map(([value, m]) => (
                  <option key={value} value={value}>
                    {m.name}
                  </option>
                ))}
              </Select>
              {meta.threshold && (
                <Input
                  label={meta.threshold}
                  type="number"
                  step="0.01"
                  value={row.threshold}
                  onChange={(e) => builder.updateCondition(row.key, { threshold: parseFloat(e.target.value) || 0 })}
                  className={styles.param}
                />
              )}
              {meta.a && (
                <Input label={meta.a} type="number" value={row.param_a} onChange={(e) => builder.updateCondition(row.key, { param_a: parseInt(e.target.value, 10) || 0 })} className={styles.param} />
              )}
              {meta.b && (
                <Input label={meta.b} type="number" value={row.param_b} onChange={(e) => builder.updateCondition(row.key, { param_b: parseInt(e.target.value, 10) || 0 })} className={styles.param} />
              )}
              <Button
                variant="ghost"
                size="sm"
                iconOnly
                icon={<X {...ICON} />}
                aria-label={`Remover condição ${i + 1}`}
                onClick={() => builder.removeCondition(row.key)}
                disabled={builder.rows.length <= 1}
                className={styles.remove}
              />
            </li>
          );
        })}
      </ol>

      <div className={styles.footer}>
        <Button size="sm" variant="ghost" icon={<Plus {...ICON} />} onClick={builder.addCondition}>
          Adicionar condição
        </Button>
        <Input
          label="Intervalo mínimo entre alertas (min)"
          type="number"
          min="1"
          value={builder.cooldownMinutes}
          onChange={(e) => builder.setCooldownMinutes(parseInt(e.target.value, 10) || 60)}
          className={styles.cooldown}
        />
      </div>
    </div>
  );
}
