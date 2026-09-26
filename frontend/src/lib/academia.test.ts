import { describe, expect, it } from 'vitest';
import { findLesson, firstIncomplete, formatMinutes, totalMinutes, trackStatus } from './academia';
import type { CourseDetail } from '../types';

const course = {
  id: 1,
  slug: 'x',
  title: 'X',
  description: '',
  order: 1,
  lesson_count: 3,
  completed_count: 1,
  modules: [
    { id: 1, title: 'M1', order: 1, lessons: [{ id: 10, title: 'Tendencia, faixa e reversao', duration_minutes: 16, completed: true }, { id: 11, title: 'B', duration_minutes: 14, completed: false }] },
    { id: 2, title: 'M2', order: 2, lessons: [{ id: 12, title: 'C', duration_minutes: 40, completed: false }] },
  ],
} as unknown as CourseDetail;

describe('academia', () => {
  it('status da trilha a partir do progresso real', () => {
    expect(trackStatus({ completed_count: 0, lesson_count: 5 })).toBe('nao-iniciada');
    expect(trackStatus({ completed_count: 2, lesson_count: 5 })).toBe('andamento');
    expect(trackStatus({ completed_count: 5, lesson_count: 5 })).toBe('concluida');
  });

  it('duração total e formatação', () => {
    expect(totalMinutes(course)).toBe(70);
    expect(formatMinutes(70)).toBe('1h 10min');
    expect(formatMinutes(45)).toBe('45 min');
  });

  it('acha aula por id ou título (com ou sem acento)', () => {
    expect(findLesson(course, '11')?.title).toBe('B');
    expect(findLesson(course, 'Tendência, faixa e reversão')?.id).toBe(10);
    expect(findLesson(course, 'nada')).toBeNull();
  });

  it('continua da primeira aula não concluída', () => {
    expect(firstIncomplete(course)?.id).toBe(11);
  });
});
