import { useEffect, useRef } from 'react';
import { Film } from 'lucide-react';
import { readVideoPosition, writeVideoPosition } from '../../lib/academia';
import { ICON_LG } from '../ui';
import { isFileVideo } from '../../lib/academia';
import styles from './Player.module.css';

function embedUrl(url: string): string | null {
  const yt = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([\w-]{6,})/);
  if (yt) return `https://www.youtube-nocookie.com/embed/${yt[1]}?rel=0`;
  const vimeo = url.match(/vimeo\.com\/(?:video\/)?(\d+)/);
  if (vimeo) return `https://player.vimeo.com/video/${vimeo[1]}`;
  return null;
}


/**
 * Vídeo da aula (16:9). Arquivo direto: <video> com retomada do ponto exato e atalhos
 * (espaço, ← →). YouTube/Vimeo: embed (sem retomada, o iframe não expõe a posição).
 * Sem vídeo: estado vazio honesto.
 */
export function VideoArea({ url, title, lessonId }: { url: string; title: string; lessonId: number }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const saved = readVideoPosition(lessonId);
    const onLoaded = () => {
      if (saved > 0 && saved < v.duration - 5) v.currentTime = saved;
    };
    let last = 0;
    const onTime = () => {
      if (Math.abs(v.currentTime - last) >= 5) {
        last = v.currentTime;
        writeVideoPosition(lessonId, v.currentTime);
      }
    };
    v.addEventListener('loadedmetadata', onLoaded);
    v.addEventListener('timeupdate', onTime);
    v.addEventListener('pause', () => writeVideoPosition(lessonId, v.currentTime));
    return () => {
      v.removeEventListener('loadedmetadata', onLoaded);
      v.removeEventListener('timeupdate', onTime);
    };
  }, [lessonId, url]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const v = videoRef.current;
      if (!v) return;
      const t = e.target as HTMLElement;
      if (t.closest('input, textarea, select, button, [contenteditable="true"], [role="dialog"]')) return;
      if (e.key === ' ') {
        e.preventDefault();
        if (v.paused) void v.play();
        else v.pause();
      } else if (e.key === 'ArrowRight') {
        v.currentTime = Math.min(v.duration || Infinity, v.currentTime + 5);
      } else if (e.key === 'ArrowLeft') {
        v.currentTime = Math.max(0, v.currentTime - 5);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (url && isFileVideo(url)) {
    return (
      <div className={styles.video}>
        <video ref={videoRef} src={url} controls preload="metadata" aria-label={`Vídeo da aula ${title}`} />
      </div>
    );
  }
  const embed = url ? embedUrl(url) : null;
  if (embed) {
    return (
      <div className={styles.video}>
        <iframe src={embed} title={`Vídeo da aula ${title}`} allow="encrypted-media; picture-in-picture; fullscreen" allowFullScreen />
      </div>
    );
  }
  return (
    <div className={[styles.video, styles.videoEmpty].join(' ')}>
      <Film {...ICON_LG} aria-hidden="true" />
      <p>Vídeo em produção. O resumo e o exercício já estão disponíveis.</p>
    </div>
  );
}
