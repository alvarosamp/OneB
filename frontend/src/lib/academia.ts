import type { CourseDetail, CourseSummary, LessonSummary } from '../types';
import { readJson, writeJson } from './storage';

export type TrackStatus = 'nao-iniciada' | 'andamento' | 'concluida';

export const TRACK_STATUS_LABEL: Record<TrackStatus, string> = {
  'nao-iniciada': 'Não iniciada',
  andamento: 'Em andamento',
  concluida: 'Concluída',
};

export function trackStatus(c: Pick<CourseSummary, 'completed_count' | 'lesson_count'>): TrackStatus {
  if (c.completed_count <= 0) return 'nao-iniciada';
  if (c.completed_count >= c.lesson_count) return 'concluida';
  return 'andamento';
}

export function allLessons(course: CourseDetail): (LessonSummary & { moduleTitle: string; moduleIndex: number })[] {
  return course.modules.flatMap((m, mi) => m.lessons.map((l) => ({ ...l, moduleTitle: m.title, moduleIndex: mi })));
}

export function totalMinutes(course: CourseDetail): number {
  return allLessons(course).reduce((sum, l) => sum + (l.duration_minutes || 0), 0);
}

export function formatMinutes(min: number): string {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}h ${m}min` : `${h}h`;
}

/** Encontra a aula por id ou por título (links do terminal usam o título). */
export function findLesson(course: CourseDetail, key: string | null): LessonSummary | null {
  const lessons = allLessons(course);
  if (!key) return null;
  const byId = lessons.find((l) => String(l.id) === key);
  if (byId) return byId;
  const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  return lessons.find((l) => norm(l.title) === norm(key)) ?? null;
}

export function firstIncomplete(course: CourseDetail): LessonSummary | null {
  const lessons = allLessons(course);
  return lessons.find((l) => !l.completed) ?? lessons[0] ?? null;
}

// ---- Progresso local (só neste navegador) ----

interface LastLesson {
  slug: string;
  lessonId: number;
  at: string;
}

const LAST_KEY = 'oneb.academia.ultima-aula';

export function rememberLesson(slug: string, lessonId: number) {
  writeJson(LAST_KEY, { slug, lessonId, at: new Date().toISOString() } satisfies LastLesson);
}

export function lastLesson(): LastLesson | null {
  return readJson<LastLesson | null>(LAST_KEY, null);
}

const noteKey = (lessonId: number) => `oneb.academia.anotacoes.${lessonId}`;
const videoKey = (lessonId: number) => `oneb.academia.video.${lessonId}`;
const exerciseKey = (lessonId: number) => `oneb.academia.exercicio.${lessonId}`;

export function readNote(lessonId: number): string {
  return readJson<string>(noteKey(lessonId), '');
}

export function writeNote(lessonId: number, text: string): boolean {
  return writeJson(noteKey(lessonId), text);
}

export function readVideoPosition(lessonId: number): number {
  return readJson<number>(videoKey(lessonId), 0);
}

export function writeVideoPosition(lessonId: number, seconds: number) {
  writeJson(videoKey(lessonId), Math.floor(seconds));
}

export function exercisePassed(lessonId: number): boolean {
  return readJson<boolean>(exerciseKey(lessonId), false);
}

export function markExercisePassed(lessonId: number) {
  writeJson(exerciseKey(lessonId), true);
}

/** Vídeo em arquivo direto (permite retomada e atalhos); YouTube/Vimeo não. */
export function isFileVideo(url: string): boolean {
  return /\.(mp4|webm|m3u8|mov)(\?|$)/i.test(url);
}
