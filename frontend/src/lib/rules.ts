import { RULE_META } from '../hooks/useRuleConditions';
import type { RuleType } from '../types';

/** Nome legível de um tipo de regra, incluindo rótulos compostos ("RSI_OVERBOUGHT+VOLUME_SPIKE"). */
export function ruleTypeLabel(ruleType: string): string {
  return ruleType
    .split('+')
    .map((part) => RULE_META[part as RuleType]?.name ?? part.replaceAll('_', ' ').toLowerCase())
    .join(' + ');
}
